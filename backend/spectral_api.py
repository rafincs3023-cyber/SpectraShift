"""
Spectral View API routes (/api/spectral/*).

Serves the 102-channel SPHEREx mosaic cubes via spectral_data.service. This
router is independent of the A/C/B Time Compare routes in main.py and does
not read or modify any of their data.

Heavy endpoints are plain `def` so FastAPI runs them in its threadpool and
slow first-time reads never block the event loop.
"""

from typing import Any, Literal, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from spectral_data import (
    DEFAULT_MAX_SIZE,
    DEFAULT_PHIGH,
    DEFAULT_PLOW,
    DEFAULT_STRETCH,
    ChannelOutOfRange,
    OutsideFootprint,
    SpectralDataMissing,
    SpectralError,
    service,
)

router = APIRouter(prefix="/api/spectral", tags=["spectral"])

_STATUS = {
    ChannelOutOfRange: 404,
    OutsideFootprint: 404,
    SpectralDataMissing: 503,
}


def _http_error(exc: SpectralError) -> HTTPException:
    return HTTPException(status_code=_STATUS.get(type(exc), 500), detail=exc.as_dict())


@router.get("/status")
def spectral_status() -> dict[str, Any]:
    """Source-file presence and access-cache state. Cheap: headers only."""
    return service.status()


@router.get("/metadata")
def spectral_metadata() -> dict[str, Any]:
    """All 102 channels (detector, subchannel, wavelength, bandwidth, source
    file mapping), image size/WCS and the overall wavelength range."""
    try:
        return service.metadata()
    except SpectralError as exc:
        raise _http_error(exc)


def _check_percentiles(plow: float, phigh: float) -> None:
    if not plow < phigh:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_stretch", "message": "plow must be less than phigh"},
        )


@router.get("/channels/{channel}")
def spectral_channel(
    channel: int,
    stretch: Literal["asinh", "linear"] = DEFAULT_STRETCH,
    plow: float = Query(DEFAULT_PLOW, ge=0.0, le=50.0),
    phigh: float = Query(DEFAULT_PHIGH, ge=50.0, le=100.0),
    max_size: int = Query(DEFAULT_MAX_SIZE, ge=128, le=4096),
) -> dict[str, Any]:
    """One channel's metadata plus the display limits (vmin/vmax, in the
    data unit) used for its preview with the same query parameters."""
    _check_percentiles(plow, phigh)
    try:
        service.layout.source_for(channel)
        meta = next(c for c in service.channels() if c["channel"] == channel)
        _, info = service.preview(channel, stretch, plow, phigh, max_size)
    except SpectralError as exc:
        raise _http_error(exc)
    query = f"stretch={stretch}&plow={plow:g}&phigh={phigh:g}&max_size={max_size}"
    return {
        **meta,
        "unit": service.layout.unit,
        "preview": {**info, "url": f"/api/spectral/channels/{channel}/preview?{query}"},
    }


@router.get("/channels/{channel}/preview")
def spectral_channel_preview(
    channel: int,
    stretch: Literal["asinh", "linear"] = DEFAULT_STRETCH,
    plow: float = Query(DEFAULT_PLOW, ge=0.0, le=50.0),
    phigh: float = Query(DEFAULT_PHIGH, ge=50.0, le=100.0),
    max_size: int = Query(DEFAULT_MAX_SIZE, ge=128, le=4096),
    format: Literal["png", "jpeg"] = "png",
) -> FileResponse:
    """Grayscale preview of one channel's real IMAGE plane (percentile
    stretch; north up, east left). PNG has an alpha channel: no-data
    pixels are transparent. Rendered once, then served from disk cache."""
    _check_percentiles(plow, phigh)
    try:
        path, _ = service.preview(channel, stretch, plow, phigh, max_size, fmt=format)
    except SpectralError as exc:
        raise _http_error(exc)
    return FileResponse(
        path,
        media_type="image/png" if format == "png" else "image/jpeg",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.get("/spectrum")
def spectral_spectrum(
    ra: Optional[float] = Query(None, ge=0.0, le=360.0, description="Right ascension, ICRS degrees"),
    dec: Optional[float] = Query(None, ge=-90.0, le=90.0, description="Declination, ICRS degrees"),
    x: Optional[int] = Query(None, description="0-based pixel x (alternative to ra/dec)"),
    y: Optional[int] = Query(None, description="0-based pixel y (alternative to ra/dec)"),
) -> dict[str, Any]:
    """The value of every channel (up to 102) at one sky position, read from
    the nearest mosaic pixel. Pass either ra+dec or x+y. Non-finite samples
    are returned as value=null, valid=false."""
    has_sky = ra is not None or dec is not None
    has_pix = x is not None or y is not None
    if has_sky == has_pix or (has_sky and (ra is None or dec is None)) or (has_pix and (x is None or y is None)):
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_position", "message": "provide either both ra and dec, or both x and y"},
        )
    try:
        return service.spectrum(ra=ra, dec=dec, x=x, y=y)
    except SpectralError as exc:
        raise _http_error(exc)
