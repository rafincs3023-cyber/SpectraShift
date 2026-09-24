"""
SpectraShift API -- SPHEREx Planet-X-challenge candidate API.

Read-only FastAPI service over already-completed scientific pipeline
outputs (three-epoch motion detection, scientific validation, catalogue
cross-match). This backend does not run or re-run any detection, matching,
validation, or catalogue-cross-match logic, and it never writes to the
original FITS files or the scientific CSV outputs -- it only reads them.

No candidate returned by this API is ever labelled "Planet X", a
"discovery", a "new planet", or a "confirmed unknown object". Catalogue
status is always one of exactly: KNOWN_OBJECT, UNMATCHED_AFTER_CHECKS,
UNCERTAIN.
"""

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from data_access import (
    VALID_CATALOGUE_STATUSES,
    clean_record,
    df_records,
    store,
)
import images
import spectrum
from spectral_api import router as spectral_router

app = FastAPI(
    title="SpectraShift API",
    description=(
        "SpectraShift -- a SPHEREx Spectral & Multi-Epoch Sky Explorer. "
        "Read-only API over completed SPHEREx three-epoch motion detection, "
        "scientific validation, and catalogue cross-match results. "
        "Candidates are preliminary and unconfirmed; nothing here is a "
        "confirmed discovery."
    ),
    version="1.0.0",
)

# CORS: permissive, local-frontend-development configuration only.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Spectral View (102-channel SPHEREx mosaic cubes) -- separate from the
# A/C/B Time Compare routes below; see spectral_api.py.
app.include_router(spectral_router)


def _candidate_summary_records() -> list[dict[str, Any]]:
    """Merge validated_candidates_with_catalogue with final_ranked_candidates
    (if present) into one summary row per candidate, for GET /api/candidates.
    """

    base_df = store.get("validated_with_catalogue")
    if base_df is None:
        base_df = store.get("validated_candidates")
    if base_df is None:
        return []

    summary_cols = [
        "candidate_id",
        "rank",
        "A_ra", "A_dec", "C_ra", "C_dec", "B_ra", "B_dec",
        "total_motion_arcsec",
        "motion_arcsec_per_day",
        "direction_diff_deg",
        "C_prediction_error_arcsec",
        "flux_variation",
        "validation_score",
    ]
    if "final_catalogue_status" in base_df.columns:
        summary_cols.append("final_catalogue_status")
        summary_cols.append("best_match_catalogue")
        summary_cols.append("best_match_separation_arcsec")

    available_cols = [c for c in summary_cols if c in base_df.columns]
    merged = base_df[available_cols].copy()

    ranked_df = store.get("final_ranked")
    if ranked_df is not None and "candidate_id" in ranked_df.columns:
        extra = ranked_df[["candidate_id", "final_rank", "final_priority_score"]].copy()
        merged = merged.merge(extra, on="candidate_id", how="left")
        merged = merged.sort_values(
            by=["final_rank"] if "final_rank" in merged.columns else ["rank"]
        )
    elif "rank" in merged.columns:
        merged = merged.sort_values(by=["rank"])

    return df_records(merged)


def _candidate_detail(candidate_id: str) -> Optional[dict[str, Any]]:
    row = store.find_candidate_row("validated_with_catalogue", candidate_id)
    if row is None:
        row = store.find_candidate_row("validated_candidates", candidate_id)
    if row is None:
        return None

    ranked_row = store.find_candidate_row("final_ranked", candidate_id)

    def g(key: str) -> Any:
        return row.get(key)

    detail: dict[str, Any] = {
        "candidate_id": row.get("candidate_id"),
        "rank": g("rank"),
        "final_rank": (ranked_row or {}).get("final_rank"),
        "final_priority_score": (ranked_row or {}).get("final_priority_score"),
        "positions": {
            "A": {
                "ra_deg": g("A_ra"), "dec_deg": g("A_dec"),
                "source_id": g("A_source"), "flux": g("flux_A"),
            },
            "C": {
                "ra_deg": g("C_ra"), "dec_deg": g("C_dec"),
                "source_id": g("C_source"), "flux": g("flux_C"),
            },
            "B": {
                "ra_deg": g("B_ra"), "dec_deg": g("B_dec"),
                "source_id": g("B_source"), "flux": g("flux_B"),
            },
        },
        "motion": {
            "total_motion_arcsec": g("total_motion_arcsec"),
            "motion_arcsec_per_day": g("motion_arcsec_per_day"),
            "motion_AC_arcsec": g("motion_AC_arcsec"),
            "motion_CB_arcsec": g("motion_CB_arcsec"),
            "rate_AC_arcsec_per_day": g("rate_AC_arcsec_per_day"),
            "rate_CB_arcsec_per_day": g("rate_CB_arcsec_per_day"),
            "position_angle_AC_deg": g("position_angle_AC_deg"),
            "position_angle_CB_deg": g("position_angle_CB_deg"),
            "direction_diff_deg": g("direction_diff_deg"),
        },
        "validation": {
            "trajectory_score": g("trajectory_score"),
            "rate_consistency_score": g("rate_consistency_score"),
            "c_error_score": g("c_error_score"),
            "flux_consistency_score": g("flux_consistency_score"),
            "validation_score": g("validation_score"),
            "C_prediction_error_arcsec": g("C_prediction_error_arcsec"),
            "flux_variation": g("flux_variation"),
            "flux_mean": g("flux_mean"),
        },
        "catalogue": {
            "final_catalogue_status": g("final_catalogue_status"),
            "best_match_catalogue": g("best_match_catalogue"),
            "best_match_object": g("best_match_object"),
            "best_match_separation_arcsec": g("best_match_separation_arcsec"),
            "best_match_epoch": g("best_match_epoch"),
            "services_succeeded": (
                g("services_succeeded").split(";")
                if isinstance(g("services_succeeded"), str) and g("services_succeeded")
                else []
            ),
            "services_failed": (
                g("services_failed").split(";")
                if isinstance(g("services_failed"), str) and g("services_failed")
                else []
            ),
            "notes": g("catalogue_notes"),
        },
        "ranking_reason": (ranked_row or {}).get("reason"),
    }
    return clean_record_deep(detail)


def clean_record_deep(obj: Any) -> Any:
    """clean_record only handles one flat dict level; this walks nested
    dicts/lists so every leaf value is JSON-safe."""
    if isinstance(obj, dict):
        return {k: clean_record_deep(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [clean_record_deep(v) for v in obj]
    return clean_record({"_": obj})["_"]


@app.get("/api/health")
def health() -> dict[str, Any]:
    """Service + data-availability health check."""

    csv_status = {
        key: {
            "loaded": store.is_loaded(key),
            "rows": int(len(df)) if (df := store.get(key)) is not None else 0,
            "error": store.load_errors.get(key),
        }
        for key in ("validated_candidates", "catalogue_crossmatch",
                    "validated_with_catalogue", "final_ranked")
    }

    fits_status = {
        epoch: {
            "found": any(o["epoch"] == epoch for o in store.observations),
            "error": store.observation_errors.get(epoch),
        }
        for epoch in ("A", "C", "B")
    }

    required_ok = (
        csv_status["validated_candidates"]["loaded"]
        and csv_status["catalogue_crossmatch"]["loaded"]
        and csv_status["validated_with_catalogue"]["loaded"]
        and all(fits_status[e]["found"] for e in ("A", "C", "B"))
    )

    return {
        "status": "ok" if required_ok else "degraded",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "csv_files": csv_status,
        "fits_files": fits_status,
        "note": (
            "Preliminary, unconfirmed candidate data only. No candidate is "
            "labelled Planet X, a discovery, or a confirmed unknown object."
        ),
    }


@app.get("/api/observations")
def observations() -> dict[str, Any]:
    """Metadata (headers only, no pixel data) for the three SPHEREx epochs used."""

    return {
        "count": len(store.observations),
        "observations": clean_record_deep(store.observations),
        "errors": store.observation_errors or None,
    }


@app.get("/api/candidates")
def candidates() -> dict[str, Any]:
    """Summary list of all validated three-epoch motion candidates."""

    records = _candidate_summary_records()
    return {
        "count": len(records),
        "candidates": records,
        "valid_catalogue_statuses": sorted(VALID_CATALOGUE_STATUSES),
    }


@app.get("/api/candidates/{candidate_id}")
def candidate_detail(candidate_id: str) -> dict[str, Any]:
    """Full detail for a single candidate: positions, motion, validation
    scores, ranking, and catalogue cross-match summary."""

    detail = _candidate_detail(candidate_id)
    if detail is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown candidate_id: {candidate_id!r}"
        )
    return detail


@app.get("/api/catalogue-crossmatch/{candidate_id}")
def catalogue_crossmatch(candidate_id: str) -> dict[str, Any]:
    """Full per-epoch, per-catalogue cross-match audit trail for one candidate."""

    rows = store.find_crossmatch_rows(candidate_id)
    summary_row = store.find_candidate_row("validated_with_catalogue", candidate_id)

    if not rows and summary_row is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown candidate_id: {candidate_id!r}"
        )

    final_status = (summary_row or {}).get("final_catalogue_status")

    return {
        "candidate_id": candidate_id.strip().upper(),
        "final_catalogue_status": final_status,
        "record_count": len(rows),
        "records": rows,
        "summary": {
            "best_match_catalogue": (summary_row or {}).get("best_match_catalogue"),
            "best_match_object": (summary_row or {}).get("best_match_object"),
            "best_match_separation_arcsec": (summary_row or {}).get("best_match_separation_arcsec"),
            "best_match_epoch": (summary_row or {}).get("best_match_epoch"),
            "services_succeeded": (summary_row or {}).get("services_succeeded"),
            "services_failed": (summary_row or {}).get("services_failed"),
            "notes": (summary_row or {}).get("catalogue_notes"),
        } if summary_row else None,
    }


# ---------------------------------------------------------------------------
# Compare page support
#
# Renders PNG previews from already-completed FITS products only (the
# original per-epoch images, and the already-computed A-vs-B alignment and
# difference products from process_spherex.py). No new detection, alignment,
# or validation is performed here -- only image rendering and a WCS
# coordinate projection for candidate markers, both read-only operations on
# already-completed data.
# ---------------------------------------------------------------------------

VALID_EPOCHS = {"A", "C", "B"}


@app.get("/api/observations/{epoch}/preview")
def observation_preview(epoch: str) -> FileResponse:
    """Grayscale PNG preview of one epoch's native (un-aligned) IMAGE HDU."""

    epoch = epoch.upper()
    if epoch not in VALID_EPOCHS:
        raise HTTPException(status_code=404, detail=f"Unknown epoch: {epoch!r}")

    try:
        path = images.get_native_preview_path(epoch)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Could not render preview: {exc}")

    return FileResponse(path, media_type="image/png")


@app.get("/api/observations/B/preview-aligned")
def observation_b_preview_aligned() -> FileResponse:
    """Grayscale PNG preview of Epoch B reprojected onto Epoch A's WCS grid
    (observation_B_aligned.fits, already computed by process_spherex.py)."""

    path = images.get_aligned_b_preview_path()
    if path is None:
        raise HTTPException(
            status_code=404,
            detail="observation_B_aligned.fits not found; aligned B preview unavailable."
        )
    return FileResponse(path, media_type="image/png")


@app.get("/api/compare/difference-preview")
def compare_difference_preview() -> FileResponse:
    """Diverging-color PNG of the precomputed Epoch A minus Epoch B
    difference product (difference_A_minus_B.fits). Red = A brighter,
    blue = B brighter. This is the ONLY epoch pair with a precomputed
    difference product; no other pair's difference is invented."""

    path = images.get_difference_preview_path()
    if path is None:
        raise HTTPException(
            status_code=404,
            detail="difference_A_minus_B.fits not found; difference preview unavailable."
        )
    return FileResponse(path, media_type="image/png")


@app.get("/api/compare/candidate-markers")
def compare_candidate_markers(epoch: str) -> dict[str, Any]:
    """Candidate marker positions (top-left-origin fractions, 0..1) for one
    epoch's pixel grid, so the frontend can overlay markers on that epoch's
    preview image regardless of its rendered size.

    `epoch` is one of A, B, C (that epoch's own native WCS) or B_aligned
    (Epoch B's real sky position projected onto Epoch A's pixel grid, i.e.
    the same grid as observation_B_aligned.fits)."""

    epoch_key = epoch.upper() if epoch.upper() != "B_ALIGNED" else "B_aligned"
    if epoch_key not in ({"A", "B", "C"} | {"B_aligned"}):
        raise HTTPException(status_code=404, detail=f"Unknown epoch: {epoch!r}")

    try:
        markers = images.compute_candidate_markers(epoch_key)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Could not compute markers: {exc}")

    return {"epoch": epoch_key, "count": len(markers), "markers": clean_record_deep(markers)}


@app.get("/api/compare/pair")
def compare_pair(epoch_a: str, epoch_b: str) -> dict[str, Any]:
    """Everything the Compare page needs for one epoch pair: which preview
    URLs to use (automatically preferring the precomputed A<->B alignment
    when that exact pair is selected), whether a precomputed difference
    product applies, and an honest note about pixel-alignment limitations
    for any pair that was never scientifically reprojected onto a common
    grid (i.e. anything involving Epoch C)."""

    a = epoch_a.upper()
    b = epoch_b.upper()
    if a not in VALID_EPOCHS or b not in VALID_EPOCHS:
        raise HTTPException(status_code=404, detail="epoch_a/epoch_b must be one of A, C, B")
    if a == b:
        raise HTTPException(status_code=400, detail="epoch_a and epoch_b must differ")

    obs_by_epoch = {o["epoch"]: o for o in store.observations}
    pair_set = {a, b}
    is_ab_pair = pair_set == {"A", "B"}

    def obs_meta(epoch_label: str) -> Optional[dict]:
        return clean_record_deep(obs_by_epoch.get(epoch_label))

    b_uses_aligned = is_ab_pair  # only the A<->B pair has a precomputed alignment
    epoch_a_info = {
        "epoch": a,
        "observation": obs_meta(a),
        "preview_url": f"/api/observations/{a}/preview",
        "markers_url": f"/api/compare/candidate-markers?epoch={a}",
    }
    epoch_b_info = {
        "epoch": b,
        "observation": obs_meta(b),
        "preview_url": (
            "/api/observations/B/preview-aligned"
            if (b == "B" and b_uses_aligned)
            else f"/api/observations/{b}/preview"
        ),
        "markers_url": (
            "/api/compare/candidate-markers?epoch=B_aligned"
            if (b == "B" and b_uses_aligned)
            else f"/api/compare/candidate-markers?epoch={b}"
        ),
    }
    # if A is the "B" slot (i.e. user picked B then A), mirror the same logic
    if a == "B" and is_ab_pair:
        epoch_a_info["preview_url"] = "/api/observations/B/preview-aligned"
        epoch_a_info["markers_url"] = "/api/compare/candidate-markers?epoch=B_aligned"

    if is_ab_pair:
        alignment_note = (
            "Epoch B is shown reprojected onto Epoch A's pixel grid "
            "(precomputed by the alignment step), so this pair is "
            "pixel-registered for slider, overlay, and difference modes."
        )
    else:
        alignment_note = (
            "This epoch pair has not been reprojected onto a common pixel "
            "grid (only Epoch A vs Epoch B was aligned in the scientific "
            "pipeline). Images are shown in their own native pointing; "
            "Slider and Overlay may show a field-pointing offset in "
            "addition to any apparent object motion. Difference mode is "
            "not available for this pair."
        )

    return {
        "epoch_a": epoch_a_info,
        "epoch_b": epoch_b_info,
        "pixel_aligned": is_ab_pair,
        "alignment_note": alignment_note,
        "difference_available": is_ab_pair,
        "difference_preview_url": "/api/compare/difference-preview" if is_ab_pair else None,
    }


# ---------------------------------------------------------------------------
# Explore page support
# ---------------------------------------------------------------------------

@app.get("/api/candidates/{candidate_id}/spectrum")
def candidate_spectrum(candidate_id: str) -> dict[str, Any]:
    """Real, per-epoch (wavelength, flux) sample points for one candidate,
    derived from the already-computed epoch positions/flux plus each FITS
    file's own WCS-WAVE calibration table and VARIANCE extension. This is
    NOT a continuous spectrum (SPHEREx's linear-variable-filter detector
    only samples one wavelength per exposure per sky position) -- each
    epoch contributes at most one (wavelength, flux) point. Any value that
    cannot be determined (e.g. the candidate's pixel position falls
    outside a detector, or a required FITS extension is unavailable) is
    returned as null, never invented or interpolated beyond the
    instrument's own calibration grid."""

    points = spectrum.get_candidate_spectrum(candidate_id)
    if points is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown candidate_id: {candidate_id!r}"
        )

    return {
        "candidate_id": candidate_id.strip().upper(),
        "points": clean_record_deep(points),
        "note": (
            "Each point is the single wavelength sampled at this "
            "candidate's real detector position in that epoch (SPHEREx's "
            "linear-variable-filter detector maps position to wavelength); "
            "this is not a continuous/interpolated spectrum. Null values "
            "mean that quantity could not be determined for that epoch, "
            "not that it is zero."
        ),
    }


@app.get("/api/candidates/{candidate_id}/cutout/{epoch}")
def candidate_cutout(candidate_id: str, epoch: str) -> FileResponse:
    """A small real-pixel cutout of one candidate's detected position in
    one epoch, cropped directly from that epoch's native FITS data (see
    images.get_candidate_cutout_path for the exact, non-invented method).
    404 if the epoch is invalid or the candidate has no real position
    within that epoch's detector."""

    epoch = epoch.upper()
    if epoch not in images.NATIVE_FITS:
        raise HTTPException(status_code=404, detail=f"Unknown epoch: {epoch!r}")

    try:
        path = images.get_candidate_cutout_path(candidate_id, epoch)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Could not render cutout: {exc}")

    if path is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No cutout available for {candidate_id!r} at epoch "
                f"{epoch!r} (unknown candidate, or its position falls "
                "outside this epoch's detector)."
            )
        )

    return FileResponse(path, media_type="image/png")
