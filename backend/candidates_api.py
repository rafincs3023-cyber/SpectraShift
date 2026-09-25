"""
Two-epoch candidate routes (/api/candidates/*).

Serves the results of two_epoch_candidates.py for the verified ~6-month pair
(earlier observation 2025-06-19, later observation 2025-12-17). The results
are read from data/time_compare_6month/two_epoch_candidates.json (written by
`python backend/two_epoch_candidates.py`); if that file is missing or from a
different pipeline version, the pipeline is run once in memory instead.

Candidates are possible position or brightness changes that passed the
current checks. None is a confirmed moving object or discovery, and two
observations cannot establish a trajectory or orbit.
"""

import json
from functools import lru_cache
from typing import Any, Optional

import numpy as np
from astropy.io import fits
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from PIL import Image

import images
import time_compare_6month as tc
import two_epoch_candidates as pipeline

router = APIRouter(prefix="/api/candidates", tags=["candidates"])

CUTOUT_DIR = images.PREVIEW_DIR / "6month" / "cutouts"
CUTOUT_HALF_PX = 12      # 25 x 25 px (~2.6 arcmin) around the position
CUTOUT_SCALE = 8         # nearest-neighbour upscale so pixels stay visible

KIND_LABELS = {
    "possible_position_change": "Possible position change",
    "shifted_match": "Small position shift",
    "seen_only_earlier": "Seen only in the earlier image",
    "seen_only_later": "Seen only in the later image",
}


@lru_cache(maxsize=1)
def _result() -> dict[str, Any]:
    path = pipeline.RESULT_JSON
    if path.is_file():
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("pipeline") == pipeline.PIPELINE_VERSION:
            return data
    return pipeline.run_real_pair()


def _result_or_503() -> dict[str, Any]:
    if tc._missing():
        raise HTTPException(status_code=503,
                            detail=f"~6-month data missing in data/time_compare_6month: {', '.join(tc._missing())}")
    return _result()


def _find(candidate_id: str) -> Optional[dict[str, Any]]:
    key = candidate_id.strip().upper()
    return next((c for c in _result_or_503()["candidates"] if c["candidate_id"] == key), None)


def _with_label(c: dict[str, Any]) -> dict[str, Any]:
    return {**c, "kind_label": KIND_LABELS.get(c["kind"], c["kind"])}


@router.get("")
def candidates() -> dict[str, Any]:
    """All two-epoch candidates plus how many detections each check
    rejected, the thresholds used and the method's limitations."""
    r = _result_or_503()
    return {
        "pipeline": r["pipeline"],
        "earlier_date": r["inputs"]["earlier"]["date"],
        "later_date": r["inputs"]["later"]["date"],
        "time_baseline_days": r["inputs"]["time_baseline_days"],
        "count": r["counts"]["total"],
        "counts": r["counts"],
        "kind_labels": KIND_LABELS,
        "candidates": [_with_label(c) for c in r["candidates"]],
        "rejected_by_reason": r["rejected_by_reason"],
        "rejection_reasons": r["rejection_reasons"],
        "measured": r["measured"],
        "thresholds": r["thresholds"],
        "inputs": r["inputs"],
        "flag_notes": r["flag_notes"],
        "limitations": r["limitations"],
    }


def _marker_frac(x: float, y: float) -> Optional[tuple[float, float]]:
    """Top-left-origin fractions within the displayed Time Compare frame
    (FITS y is up), or None if the position lies outside it."""
    reg = tc._display_region()
    if not (reg["x0"] - 0.5 <= x <= reg["x1"] - 0.5 and reg["y0"] - 0.5 <= y <= reg["y1"] - 0.5):
        return None
    return (x - reg["x0"] + 0.5) / reg["width"], 1 - (y - reg["y0"] + 0.5) / reg["height"]


@router.get("/markers")
def candidate_markers(image: str = Query("earlier", pattern="^(earlier|later)$")) -> dict[str, Any]:
    """Marker positions for the earlier or later ~6-month preview (the same
    display frame Time Compare and Explore show). A candidate seen in only
    one image is still marked at that position in the other image, with
    detected_here = false, so its absence can be inspected."""
    r = _result_or_503()
    markers, outside = [], []
    for c in r["candidates"]:
        here = c[image]
        pos = here or c["later" if image == "earlier" else "earlier"]
        frac = _marker_frac(pos["x"], pos["y"])
        if frac is None:
            outside.append(c["candidate_id"])
            continue
        markers.append({"candidate_id": c["candidate_id"], "kind": c["kind"],
                        "x_frac": frac[0], "y_frac": frac[1], "detected_here": here is not None})
    return {"image": image, "count": len(markers), "markers": markers,
            "outside_display": outside}


@router.get("/{candidate_id}")
def candidate_detail(candidate_id: str) -> dict[str, Any]:
    c = _find(candidate_id)
    if c is None:
        raise HTTPException(status_code=404, detail=f"Unknown candidate_id: {candidate_id!r}")
    r = _result()
    base = f"/api/candidates/{c['candidate_id']}/cutout"
    at_positions = [k for k in ("earlier", "later") if c[k]]
    # a second set of cutouts only when the later position is off the first
    if len(at_positions) == 2 and max(abs(c["earlier"]["x"] - c["later"]["x"]),
                                       abs(c["earlier"]["y"] - c["later"]["y"])) <= CUTOUT_HALF_PX - 2:
        at_positions = ["earlier"]
    return {
        **_with_label(c),
        "cutouts": [
            {"at": at, "earlier": f"{base}/earlier?at={at}", "later": f"{base}/later?at={at}",
             "difference": f"{base}/difference?at={at}"}
            for at in at_positions
        ],
        "cutout_size_arcsec": round((2 * CUTOUT_HALF_PX + 1) * r["inputs"]["pixel_scale_arcsec"], 1),
        "rejection_reasons": r["rejection_reasons"],
        "limitations": r["limitations"],
    }


@lru_cache(maxsize=1)
def _arrays() -> dict[str, np.ndarray]:
    valid = fits.getdata(tc.OVERLAP_MASK_FITS) > 0
    out = {"valid": valid}
    for key, path in (("earlier", tc.EPOCH_FITS["A"]), ("later", tc.EPOCH_FITS["B"]),
                      ("difference", tc.DIFFERENCE_FITS)):
        out[key] = np.where(valid, fits.getdata(path).astype(np.float64), np.nan)
    return out


def _stamp(data: np.ndarray, x: float, y: float) -> np.ndarray:
    """25 x 25 px around (x, y), NaN-padded where it leaves the grid."""
    h = CUTOUT_HALF_PX
    ix, iy = int(round(x)), int(round(y))
    out = np.full((2 * h + 1, 2 * h + 1), np.nan)
    ny, nx = data.shape
    y0, y1, x0, x1 = max(iy - h, 0), min(iy + h + 1, ny), max(ix - h, 0), min(ix + h + 1, nx)
    if y0 < y1 and x0 < x1:
        out[y0 - (iy - h):y1 - (iy - h), x0 - (ix - h):x1 - (ix - h)] = data[y0:y1, x0:x1]
    return out


def _render_cutouts(c: dict[str, Any], at: str) -> None:
    pos = c[at]
    arr = _arrays()
    ea, eb, diff = (_stamp(arr[k], pos["x"], pos["y"]) for k in ("earlier", "later", "difference"))
    both = np.concatenate([ea[np.isfinite(ea)], eb[np.isfinite(eb)]])
    lo, hi = (np.percentile(both, [1, 99.7]) if both.size else (0.0, 1.0))
    for kind, data in (("earlier", ea), ("later", eb)):
        img = images._stretch_to_uint8(data, lo=float(lo), hi=float(hi))
        pil = Image.fromarray(np.flipud(img), mode="L")
        pil.resize((pil.width * CUTOUT_SCALE, pil.height * CUTOUT_SCALE), Image.NEAREST).save(
            _cutout_path(c, kind, at), format="PNG", optimize=True)
    tmp = _cutout_path(c, "difference", at)
    images._save_diverging(diff, tmp, max_size=None)
    pil = Image.open(tmp)
    pil.resize((pil.width * CUTOUT_SCALE, pil.height * CUTOUT_SCALE), Image.NEAREST).save(tmp, format="PNG")


def _cutout_path(c: dict[str, Any], kind: str, at: str):
    return CUTOUT_DIR / f"{_result()['pipeline']}_{c['candidate_id']}_{at}_{kind}.png"


@router.get("/{candidate_id}/cutout/{kind}")
def candidate_cutout(candidate_id: str, kind: str,
                     at: Optional[str] = Query(None, pattern="^(earlier|later)$")) -> FileResponse:
    """Real-pixel cutout from the earlier image, the later (aligned) image
    or the later - earlier difference, centred on the candidate's earlier
    or later position. Earlier and later share one display stretch."""
    if kind not in ("earlier", "later", "difference"):
        raise HTTPException(status_code=404, detail=f"Unknown cutout: {kind!r}")
    c = _find(candidate_id)
    if c is None:
        raise HTTPException(status_code=404, detail=f"Unknown candidate_id: {candidate_id!r}")
    at = at or ("earlier" if c["earlier"] else "later")
    if c[at] is None:
        raise HTTPException(status_code=404, detail=f"{c['candidate_id']} has no {at} position")
    path = _cutout_path(c, kind, at)
    if not path.exists():
        CUTOUT_DIR.mkdir(parents=True, exist_ok=True)
        try:
            _render_cutouts(c, at)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=500, detail=f"Could not render cutout: {exc}")
    return FileResponse(path, media_type="image/png")
