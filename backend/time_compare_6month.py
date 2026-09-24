"""
~6-month Time Compare routes (/api/compare/6month/*).

Serves the already-built, verified Jun 19 2025 vs Dec 17 2025 SPHEREx pair
from data/time_compare_6month/ (produced by build_6month_difference.py).
Nothing here re-aligns, re-differences, or re-validates anything: scientific
values come from metadata.json and the FITS headers, and the only processing
is display rendering of the already-aligned 1057x468 crops to PNG.

Why render previews instead of serving epoch_A.png / epoch_B_aligned.png
directly: those are annotated matplotlib figures (title, axes, colorbar), so
their pixels are not the image grid and cannot be pixel-registered for the
Slider / Blink / Overlay modes. They are still served, unchanged, under
/figure/{name} as reference figures.

Independent of the A/C/B 31-day routes in main.py; reads none of their data.
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

import numpy as np
from astropy.io import fits
from astropy.time import Time
from astropy.wcs import WCS
from astropy.wcs.utils import proj_plane_pixel_scales
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from PIL import Image

from data_access import BASE_DIR
import images

router = APIRouter(prefix="/api/compare/6month", tags=["time-compare-6month"])

DATA_DIR = BASE_DIR / "data" / "time_compare_6month"
METADATA_JSON = DATA_DIR / "metadata.json"
EPOCH_FITS = {
    "A": DATA_DIR / "epoch_A_2025-06-19.fits",
    "B": DATA_DIR / "epoch_B_2025-12-17_aligned.fits",
}
DIFFERENCE_FITS = DATA_DIR / "difference_B_minus_A.fits"
OVERLAP_MASK_FITS = DATA_DIR / "overlap_mask.fits"

# Annotated reference figures from build_6month_difference.py, served as-is.
FIGURES = {
    "epoch_A.png",
    "epoch_B_aligned.png",
    "difference_B_minus_A.png",
}

PREVIEW_DIR = images.PREVIEW_DIR / "6month"
PREVIEW_DIR.mkdir(exist_ok=True)

DAYS_PER_MONTH = 365.25 / 12


def _read_json(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _load(path: Path) -> np.ndarray:
    with fits.open(path) as hdul:
        return hdul[0].data.astype(np.float32)


def _overlap_mask() -> np.ndarray:
    return _load(OVERLAP_MASK_FITS) > 0


def _outside_footprint(valid: np.ndarray) -> np.ndarray:
    """Invalid pixels connected to the array border (4-connectivity): the
    area outside the common footprint. Invalid pixels NOT reached from the
    border are isolated interior holes (individual NaN pixels in one epoch)."""
    invalid = ~valid
    reached = np.zeros_like(invalid)
    reached[0, :] = invalid[0, :]
    reached[-1, :] = invalid[-1, :]
    reached[:, 0] |= invalid[:, 0]
    reached[:, -1] |= invalid[:, -1]
    while True:
        grown = reached.copy()
        grown[1:, :] |= reached[:-1, :]
        grown[:-1, :] |= reached[1:, :]
        grown[:, 1:] |= reached[:, :-1]
        grown[:, :-1] |= reached[:, 1:]
        grown &= invalid
        if np.array_equal(grown, reached):
            return reached
        reached = grown


def _largest_rectangle(ok: np.ndarray) -> tuple[int, int, int, int]:
    """Largest axis-aligned rectangle of True pixels (histogram/stack
    method). Returns (x0, x1, y0, y1) as half-open numpy slice bounds."""
    height, width = ok.shape
    heights = [0] * width
    best_area, best = 0, (0, width, 0, height)
    for y, row in enumerate(ok.tolist()):
        heights = [h + 1 if v else 0 for h, v in zip(heights, row)]
        stack: list[tuple[int, int]] = []
        for x in range(width + 1):
            cur = heights[x] if x < width else 0
            start = x
            while stack and stack[-1][1] >= cur:
                start, h = stack.pop()
                if h * (x - start) > best_area:
                    best_area = h * (x - start)
                    best = (start, x, y - h + 1, y + 1)
            stack.append((start, cur))
    return best


@lru_cache(maxsize=1)
def _display_region() -> dict[str, Any]:
    """The one rectangle every browser preview (A, aligned B, B - A) is cut
    to. The aligned crop is the bounding box of the common overlap, so its
    corners contain area outside the footprint; this picks the largest
    rectangle lying entirely inside the footprint. Isolated interior NaN
    pixels are not allowed to fragment it -- they are drawn neutral."""
    valid = _overlap_mask()
    outside = _outside_footprint(valid)
    x0, x1, y0, y1 = _largest_rectangle(~outside)
    region_valid = valid[y0:y1, x0:x1]
    return {
        "x0": x0, "x1": x1, "y0": y0, "y1": y1,
        "width": x1 - x0,
        "height": y1 - y0,
        "valid_pixels": int(region_valid.sum()),
        "invalid_pixels": int((~region_valid).sum()),
        "valid_fraction": float(region_valid.mean()),
    }


def _display_slice() -> tuple[slice, slice]:
    r = _display_region()
    return slice(r["y0"], r["y1"]), slice(r["x0"], r["x1"])


def _source_header(filename: Optional[str]) -> Optional[fits.Header]:
    """IMAGE header of the original level-2 file named in metadata.json
    (for DETECTOR / PSF_FWHM, which the crop headers don't carry)."""
    if not filename:
        return None
    path = BASE_DIR / filename
    if not path.is_file():
        return None
    try:
        with fits.open(path) as hdul:
            return hdul["IMAGE"].header.copy()
    except Exception:  # noqa: BLE001 - optional enrichment only
        return None


def _missing() -> list[str]:
    required = [METADATA_JSON, *EPOCH_FITS.values(), DIFFERENCE_FITS, OVERLAP_MASK_FITS]
    return [p.name for p in required if not p.is_file()]


@lru_cache(maxsize=1)
def _dataset() -> dict[str, Any]:
    missing = _missing()
    if missing:
        raise FileNotFoundError(", ".join(missing))

    meta = _read_json(METADATA_JSON)
    crop_header = fits.getheader(EPOCH_FITS["A"])
    crop_wcs = WCS(crop_header)
    overlap_pixels = int(_overlap_mask().sum())

    # Everything shown in the browser is the display region, so the
    # coordinate reported with the images is ITS centre -- the frame
    # centre, which is not the target used to select this pair.
    region = _display_region()
    width, height = region["width"], region["height"]
    center_ra, center_dec = crop_wcs.pixel_to_world_values(
        (region["x0"] + region["x1"] - 1) / 2, (region["y0"] + region["y1"] - 1) / 2
    )

    target = meta["target"]
    tx, ty = (float(v) for v in crop_wcs.world_to_pixel_values(target["ra_deg"], target["dec_deg"]))
    # distance (px) from the target to the nearest display-region pixel; 0 if inside
    dx = max(region["x0"] - tx, 0.0, tx - (region["x1"] - 1))
    dy = max(region["y0"] - ty, 0.0, ty - (region["y1"] - 1))
    # CUNIT is deg, so this is deg/px
    pixel_scale_arcsec = float(np.mean(proj_plane_pixel_scales(crop_wcs.celestial)) * 3600)
    target_in_display = dx == 0 and dy == 0

    def side(key: str) -> dict[str, Any]:
        epoch_meta = meta[f"epoch_{key}"]
        src = _source_header(epoch_meta.get("file"))
        detector = src.get("DETECTOR") if src is not None else None
        return {
            "epoch": key,
            "preview_url": f"/api/compare/6month/preview/{key}",
            "figure_url": f"/api/compare/6month/figure/"
                          f"{'epoch_A.png' if key == 'A' else 'epoch_B_aligned.png'}",
            "wavelength_um": epoch_meta.get("wavelength_um"),
            "psf_fwhm_arcsec": src.get("PSF_FWHM") if src is not None else None,
            "source_file": epoch_meta.get("file"),
            # Same shape as the 31-day Observation records so the existing
            # Compare panels can render it unchanged.
            "observation": {
                "epoch": key,
                "filename": EPOCH_FITS[key].name,
                "obs_id": src.get("OBSID") if src is not None else None,
                "detector": detector,
                "mjd_obs": float(Time(epoch_meta["date"], scale="utc").mjd),
                "date_obs": epoch_meta["date"],
                "naxis1": width,
                "naxis2": height,
                "ra_center_deg": float(center_ra),
                "dec_center_deg": float(center_dec),
                "bunit": crop_header.get("BUNIT"),
            },
        }

    gap_days = float(meta["time_gap_days"])
    return {
        "dataset": "6month",
        "title": "~6-Month Comparison",
        "target": {
            **target,
            "crop_pixel": {"x": tx, "y": ty},
            "in_display_region": target_in_display,
            # top-left-origin fractions within the displayed frame (FITS y is up)
            "x_frac": (tx - region["x0"] + 0.5) / width if target_in_display else None,
            "y_frac": 1 - (ty - region["y0"] + 0.5) / height if target_in_display else None,
            "offset_from_display_px": float(np.hypot(dx, dy)),
            "offset_from_display_arcsec": float(np.hypot(dx, dy) * pixel_scale_arcsec),
        },
        "frame_center": {"ra_deg": float(center_ra), "dec_deg": float(center_dec)},
        "display_region": {**region, "pixel_scale_arcsec": pixel_scale_arcsec},
        "epoch_a": side("A"),
        "epoch_b": side("B"),
        "time_gap_days": gap_days,
        "time_gap_months": gap_days / DAYS_PER_MONTH,
        "wavelength_delta_um": meta["wavelength_delta_um"],
        "delta_over_bandwidth": meta.get("delta_over_bandwidth"),
        "bunit": crop_header.get("BUNIT"),
        "crop": meta["crop"],
        "overlap_pixels": overlap_pixels,
        "pixel_aligned": True,
        "alignment_note": (
            "Epoch B was reprojected onto Epoch A's pixel grid. Every view "
            "shows the same rectangle cut from that shared grid, lying "
            "entirely inside the common footprint, so this pair is "
            "pixel-registered for Slider, Blink, Overlay and Difference."
        ),
        "difference_primary": meta["difference_primary"],
        "difference_meaning": meta["difference_meaning"],
        "difference_available": True,
        "difference_preview_url": "/api/compare/6month/preview/difference",
        "difference_figure_url": "/api/compare/6month/figure/difference_B_minus_A.png",
    }


def _preview_name(kind: str) -> str:
    # region bounds in the name so a changed region never serves stale PNGs
    r = _display_region()
    return f"{kind}_x{r['x0']}-{r['x1']}_y{r['y0']}-{r['y1']}.png"


def _region_arrays() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """A, aligned B, B - A and the validity mask, all cut with the SAME
    slice from the same aligned grid (no re-reprojection or resampling)."""
    ys, xs = _display_slice()
    valid = _overlap_mask()[ys, xs]
    a = _load(EPOCH_FITS["A"])[ys, xs]
    b = _load(EPOCH_FITS["B"])[ys, xs]
    diff = _load(DIFFERENCE_FITS)[ys, xs]
    return a, b, diff, valid


def _render_epoch_previews() -> None:
    """Both epochs share one display stretch computed over the valid pixels
    of the displayed region, so brightness differences between the previews
    reflect the data rather than per-image scaling. The few isolated invalid
    pixels inside the region (invalid in either epoch) are drawn at each
    epoch's median sky level in BOTH previews, so they read as neutral and
    don't flicker in Blink. Rendered at native resolution (1 px = 1 px)."""
    a, b, _, valid = _region_arrays()
    both = np.concatenate([a[valid], b[valid]])
    lo, hi = np.percentile(both, [0.5, 99.5])
    for key, data in (("A", a), ("B", b)):
        data = data.copy()
        data[~valid] = np.median(data[valid])
        stretched = images._stretch_to_uint8(data, lo=float(lo), hi=float(hi))
        img = Image.fromarray(np.flipud(stretched), mode="L")
        img.save(PREVIEW_DIR / _preview_name(key), format="PNG", optimize=True)


def _preview_path(kind: str) -> Path:
    out = PREVIEW_DIR / _preview_name(kind)
    if out.exists():
        return out
    if kind in ("A", "B"):
        _render_epoch_previews()
        return out

    _, _, diff, valid = _region_arrays()
    diff = diff.copy()
    diff[~valid] = 0.0  # neutral: no change
    # B - A: positive (brighter in later epoch) -> red, negative -> blue
    images._save_diverging(diff, out, max_size=None)
    return out


def _dataset_or_503() -> dict[str, Any]:
    try:
        return _dataset()
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"~6-month Time Compare data missing in data/time_compare_6month: {exc}",
        )


@router.get("")
def six_month_pair() -> dict[str, Any]:
    """Metadata plus preview URLs for the ~6-month pair (from metadata.json
    and FITS headers; no pixel data)."""
    return _dataset_or_503()


@router.get("/preview/{kind}")
def six_month_preview(kind: str) -> FileResponse:
    """Pixel-registered PNG preview: A, B (aligned) or difference (B - A)."""
    kind = kind if kind == "difference" else kind.upper()
    if kind not in ("A", "B", "difference"):
        raise HTTPException(status_code=404, detail=f"Unknown preview: {kind!r}")
    _dataset_or_503()
    try:
        path = _preview_path(kind)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Could not render preview: {exc}")
    return FileResponse(path, media_type="image/png")


@router.get("/figure/{name}")
def six_month_figure(name: str) -> FileResponse:
    """The annotated reference figures written by build_6month_difference.py."""
    if name not in FIGURES:
        raise HTTPException(status_code=404, detail=f"Unknown figure: {name!r}")
    path = DATA_DIR / name
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"{name} not found")
    return FileResponse(path, media_type="image/png")
