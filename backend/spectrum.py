"""
Minimal, read-only per-candidate spectral sampling for the Explore page.

SPHEREx uses a linear-variable-filter detector: wavelength varies smoothly
across the detector's pixel grid (see the WCS-WAVE table in each FITS
file), so a single exposure does NOT contain a continuous spectrum for a
fixed sky position -- it samples that position at whatever single
wavelength corresponds to the pixel the source happened to fall on in
that exposure. Because our 22 candidates moved across the detector between
epochs A, C and B, each epoch's detection sampled the source at a
DIFFERENT wavelength. This module reads that real, already-computed
per-epoch position + flux (from validated_candidates_with_catalogue.csv)
and looks up:
  - the real wavelength (and wavelength bandpass) at that exact detector
    pixel, via the FITS file's own WCS-WAVE calibration table
    (bilinear interpolation over the instrument's real calibration grid
    -- not invented or extrapolated beyond the detector edge), and
  - a flux uncertainty from the same file's VARIANCE extension, using the
    identical aperture-sum method already used for flux in
    three_epoch_compare.py (not a new detection/validation step -- just
    the statistical error for a flux value that was already measured).

Any epoch where the candidate's pixel position falls outside the detector,
or where the required HDUs are unavailable, returns null values rather
than an invented number.
"""

from typing import Optional

import numpy as np
from astropy.io import fits
from astropy.wcs import WCS
from scipy.interpolate import RegularGridInterpolator
from photutils.aperture import CircularAperture, aperture_photometry

from data_access import BASE_DIR, store

NATIVE_FITS = {
    "A": BASE_DIR / "level2_2025W19_2B_0166_3D3_spx_l2b-v20-2025-247.fits",
    "C": BASE_DIR / "level2_2025W22_1B_0226_1D3_spx_l2b-v20-2025-250.fits",
    "B": BASE_DIR / "level2_2025W24_1A_0099_1D3_spx_l2b-v20-2025-252.fits",
}

APERTURE_RADIUS = 3.0  # same radius used for flux in three_epoch_compare.py

_wave_grid_cache: dict[str, RegularGridInterpolator] = {}


def _get_wave_interpolator(epoch: str) -> RegularGridInterpolator:
    if epoch in _wave_grid_cache:
        return _wave_grid_cache[epoch]

    with fits.open(NATIVE_FITS[epoch]) as hdul:
        table = hdul["WCS-WAVE"].data
        x_grid = np.asarray(table["X"][0], dtype=float)   # (9,)
        y_grid = np.asarray(table["Y"][0], dtype=float)   # (14,)
        values = np.asarray(table["VALUES"][0], dtype=float)  # (14, 9, 2)

    # RegularGridInterpolator wants axes in increasing-coordinate order,
    # indexed [y, x, component] to match the table's own (14, 9, 2) layout.
    interp = RegularGridInterpolator(
        (y_grid, x_grid),
        values,
        method="linear",
        bounds_error=False,
        fill_value=None,  # extrapolate defensively; we clip inputs anyway
    )
    _wave_grid_cache[epoch] = interp
    return interp


def _wavelength_at_pixel(epoch: str, x: float, y: float) -> tuple[Optional[float], Optional[float]]:
    interp = _get_wave_interpolator(epoch)

    with fits.open(NATIVE_FITS[epoch]) as hdul:
        naxis1 = hdul["IMAGE"].header.get("NAXIS1")
        naxis2 = hdul["IMAGE"].header.get("NAXIS2")

    if not (0 <= x <= naxis1 and 0 <= y <= naxis2):
        return None, None

    # clip to the calibration grid's own coverage to avoid extrapolation
    x_grid, y_grid = interp.grid
    x_c = float(np.clip(x, x_grid.min(), x_grid.max()))
    y_c = float(np.clip(y, y_grid.min(), y_grid.max()))

    wavelength, bandwidth = interp([[y_c, x_c]])[0]
    if not np.isfinite(wavelength):
        return None, None

    return float(wavelength), (float(bandwidth) if np.isfinite(bandwidth) else None)


def _flux_uncertainty_at_pixel(epoch: str, x: float, y: float) -> Optional[float]:
    try:
        with fits.open(NATIVE_FITS[epoch]) as hdul:
            variance = hdul["VARIANCE"].data.astype(np.float32)
    except Exception:
        return None

    h, w = variance.shape
    if not (0 <= x <= w and 0 <= y <= h):
        return None

    aperture = CircularAperture([(x, y)], r=APERTURE_RADIUS)
    safe_variance = np.where(np.isfinite(variance) & (variance >= 0), variance, 0.0)
    phot = aperture_photometry(safe_variance, aperture)
    summed_variance = float(phot["aperture_sum"][0])

    if not np.isfinite(summed_variance) or summed_variance < 0:
        return None

    return float(np.sqrt(summed_variance))


def _pixel_for_epoch(epoch: str, ra: float, dec: float) -> tuple[float, float]:
    with fits.open(NATIVE_FITS[epoch]) as hdul:
        header = hdul["IMAGE"].header.copy()
    wcs = WCS(header)
    x, y = wcs.world_to_pixel_values(ra, dec)
    return float(x), float(y)


def get_candidate_spectrum(candidate_id: str) -> Optional[list[dict]]:
    df = store.get("validated_with_catalogue")
    if df is None:
        df = store.get("validated_candidates")
    if df is None:
        return None

    mask = df["candidate_id"].astype(str).str.upper() == candidate_id.strip().upper()
    matches = df[mask]
    if len(matches) == 0:
        return None

    row = matches.iloc[0]

    points = []
    for epoch in ["A", "C", "B"]:
        ra = row.get(f"{epoch}_ra")
        dec = row.get(f"{epoch}_dec")
        flux = row.get(f"flux_{epoch}")

        if ra is None or dec is None:
            points.append({
                "epoch": epoch,
                "mjd": None,
                "wavelength_um": None,
                "wavelength_bandwidth_um": None,
                "flux": None,
                "flux_uncertainty": None,
            })
            continue

        x, y = _pixel_for_epoch(epoch, float(ra), float(dec))

        try:
            wavelength_um, bandwidth_um = _wavelength_at_pixel(epoch, x, y)
        except Exception:
            wavelength_um, bandwidth_um = None, None

        try:
            flux_uncertainty = _flux_uncertainty_at_pixel(epoch, x, y)
        except Exception:
            flux_uncertainty = None

        with fits.open(NATIVE_FITS[epoch]) as hdul:
            mjd = hdul["IMAGE"].header.get("MJD-OBS")

        points.append({
            "epoch": epoch,
            "mjd": mjd,
            "wavelength_um": wavelength_um,
            "wavelength_bandwidth_um": bandwidth_um,
            "flux": float(flux) if flux is not None else None,
            "flux_uncertainty": flux_uncertainty,
        })

    return points
