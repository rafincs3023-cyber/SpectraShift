"""
Two-epoch motion/change candidate pipeline for the ~6-month SPHEREx pair.

Inputs are ONLY the verified ~6-month products in data/time_compare_6month/
(earlier observation 2025-06-19, later observation 2025-12-17 reprojected
onto the earlier grid, their overlap mask and B - A difference) plus the
FLAGS extension of the two Level-2 source frames named in metadata.json.
No other observation, source list or earlier candidate result is read.

What two epochs can and cannot tell us
--------------------------------------
With two observations there is no third point to test a trajectory, so a
result here is only a *possible* position change or brightness change that
passed the checks below. It is never a confirmed moving object, orbit or
discovery. Every candidate is for further inspection.

Stages
------
1. Load both epochs on the shared grid; valid = overlap & finite in both.
2. Background and noise: sigma-clipped median / std in 32 x 32 px boxes
   (a box counts if >= 50 % of its pixels are valid), smoothed over 3 x 3
   boxes and interpolated to every pixel.
3. Detection, independently per epoch: matched filter (Gaussian with the
   FWHM measured from this epoch's own stars), significance = filtered
   value / local robust std of the filtered image (so the correlated noise
   of the reprojected later image is measured, not assumed). Local maxima
   >= DETECTION_SNR are sources. Centroids from a 3-point Gaussian fit.
4. Cross-match on the shared pixel grid (mutual nearest neighbours within
   1 FWHM). The epoch-to-epoch position error is MEASURED from the
   thousands of matched sources as sigma^2 = sigma_sys^2 + k^2 / SNR^2
   (alignment residual + centroiding of the undersampled PSF + noise).
   The stationary tolerance is 5 sigma of that error: with ~7,000 matched
   sources a 3-sigma cut would let ~70 noise pairs through (2-D Gaussian
   tail exp(-t^2/2)), 5 sigma leaves an expected ~0.03.
5. Unmatched sources are checked with forced photometry at the same
   position in the other epoch; >= FORCED_PRESENT_SNR there means the
   source is present in both (stationary, just not detected or blended).
6. Quality vetoes (see VETO_*): footprint edge, SPHEREx pixel flags,
   non-finite pixels, single-pixel (cosmic-ray / hot-pixel) morphology,
   bright-star halo, crowding / blends, poor centroid, inconsistent
   difference-image sign.
7. Survivors seen in only one epoch are "single-epoch changes". Pairs of
   an earlier-only and a later-only survivor within MAX_PAIR_SEPARATION_PX
   and with compatible brightness become "possible position change"
   candidates; matched sources whose offset is significant but still
   within the match radius become "shifted match" candidates.

Run as a script to (re)write two_epoch_candidates.json:

    python backend/two_epoch_candidates.py
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import numpy as np
from scipy import ndimage
from scipy.spatial import cKDTree

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "time_compare_6month"
RESULT_JSON = DATA_DIR / "two_epoch_candidates.json"

PIPELINE_VERSION = "two-epoch-1.0"

# --- detection ---------------------------------------------------------
BOX_PX = 32                 # background box
DETECTION_SNR = 5.0         # matched-filter significance for a detection
FORCED_PRESENT_SNR = 3.0    # "present in the other epoch" at this significance
APERTURE_RADIUS_PX = 2.0    # aperture brightness radius

# --- matching ----------------------------------------------------------
# Search radius for pairing a source with its counterpart in the other
# epoch, in units of the measured FWHM. Beyond ~1 FWHM two detections are
# resolved from one another, so they are separate sources, not one source
# with a centroid error.
MATCH_RADIUS_FWHM = 1.0
STATIONARY_NSIGMA = 5.0     # stationary tolerance, trials-corrected (see 4.)
MIN_SHIFT_SNR = 10.0        # a sub-PSF shift is only measurable on bright sources

# --- vetoes ------------------------------------------------------------
EDGE_MARGIN_PX = 4          # keep candidates this far inside the footprint
FLAG_RADIUS_PX = 1          # SPHEREx-flagged pixel within this radius
HALO_PEAK_SNR = 200.0       # a "bright star" for the halo veto
HALO_RADIUS_PX = 8.0        # ... and the radius of its halo / PSF wings
CROWDING_RADIUS_FWHM = 2.0  # another source this close = blend caution
MAX_CENTROID_ERROR_PX = 0.5 # poor centroid
EXTREME_NEGATIVE_SIGMA = 10.0  # a pixel this far BELOW the sky is corrupted
# The change itself must be as significant in the difference image as a
# detection is in a single image.
DIFF_SUPPORT_SNR = 5.0

# --- pairing -----------------------------------------------------------
# An earlier-only and a later-only source are paired only if they could be
# one object: separation up to MAX_PAIR_SEPARATION_PX and brightness within
# a factor PAIR_FLUX_RATIO_MAX (the two images are 0.0032 um apart, 8 % of
# the channel width, so real brightness should agree well; the factor 2
# allows for noise at low SNR).
MAX_PAIR_SEPARATION_PX = 300.0
PAIR_FLUX_RATIO_MAX = 2.0

# SPHEREx Level-2 FLAGS bits treated as bad (FLAGS header MP_* keywords):
# TRANSIENT, OVERFLOW, SUR_ERROR, PHANTOM, REFERENCE, NONFUNC, MISSING_DATA,
# HOT, COLD, NONLINEAR, PERSIST, OUTLIER.
BAD_FLAG_BITS = (0, 1, 2, 4, 5, 6, 9, 10, 11, 15, 17, 19)
BAD_FLAG_MASK = sum(1 << b for b in BAD_FLAG_BITS)

# Rejection reasons (stable identifiers used in the API)
VETO_STATIONARY = "stationary"              # matched within tolerance
VETO_PRESENT_BOTH = "present_in_both"       # forced photometry finds it
VETO_EDGE = "footprint_edge"
VETO_FLAGGED = "flagged_pixel"
VETO_NONFINITE = "non_finite_pixels"
VETO_MORPHOLOGY = "not_star_like"
VETO_HALO = "bright_star_halo"
VETO_BLEND = "crowded_or_blended"
VETO_CENTROID = "poor_centroid"
VETO_DIFFERENCE = "difference_disagrees"
VETO_EXTREME = "corrupted_pixel"
VETO_SHAPE_MISMATCH = "shape_mismatch"

VETO_TEXT = {
    VETO_STATIONARY: "Same position in both observations (a stationary source).",
    VETO_PRESENT_BOTH: "Also visible at the same position in the other observation.",
    VETO_EDGE: "Too close to the edge of the shared image area.",
    VETO_FLAGGED: "On or next to a pixel SPHEREx flagged as unreliable.",
    VETO_NONFINITE: "Missing pixels around the source.",
    VETO_MORPHOLOGY: "Shape unlike a star (e.g. a single-pixel spike).",
    VETO_HALO: "Inside the glare of a bright star.",
    VETO_BLEND: "Too close to another source to measure separately.",
    VETO_CENTROID: "Position too uncertain.",
    VETO_DIFFERENCE: "The difference image does not show a clear change of the expected sign.",
    VETO_EXTREME: "Next to a corrupted (strongly negative) pixel in one of the images.",
    VETO_SHAPE_MISMATCH: "Looks different in the two images (e.g. a blend), so the positions are not comparable.",
}


# ---------------------------------------------------------------------------
# Image statistics
# ---------------------------------------------------------------------------

def _clipped_stats(values: np.ndarray, sigma: float = 3.0, iters: int = 5) -> tuple[float, float]:
    """Sigma-clipped median and MAD-based std."""
    v = values[np.isfinite(values)]
    for _ in range(iters):
        med = float(np.median(v))
        std = float(1.4826 * np.median(np.abs(v - med)))
        if std <= 0:
            break
        keep = np.abs(v - med) <= sigma * std
        if keep.all():
            break
        v = v[keep]
    med = float(np.median(v))
    return med, float(1.4826 * np.median(np.abs(v - med)))


def background_maps(img: np.ndarray, valid: np.ndarray, box: int = BOX_PX) -> tuple[np.ndarray, np.ndarray]:
    """Per-pixel background and robust noise from sigma-clipped box stats."""
    ny, nx = img.shape
    gy, gx = math.ceil(ny / box), math.ceil(nx / box)
    med = np.full((gy, gx), np.nan)
    std = np.full((gy, gx), np.nan)
    for j in range(gy):
        for i in range(gx):
            sl = (slice(j * box, (j + 1) * box), slice(i * box, (i + 1) * box))
            ok = valid[sl]
            if ok.mean() < 0.5:
                continue
            med[j, i], std[j, i] = _clipped_stats(img[sl][ok])
    if not np.isfinite(med).any():
        raise ValueError("no box has enough valid pixels for a background estimate")
    # fill empty boxes from the nearest measured box, then smooth 3 x 3
    for grid in (med, std):
        missing = ~np.isfinite(grid)
        if missing.any():
            idx = ndimage.distance_transform_edt(missing, return_distances=False, return_indices=True)
            grid[missing] = grid[tuple(idx[:, missing])]
    med = ndimage.median_filter(med, size=3, mode="nearest")
    std = ndimage.median_filter(std, size=3, mode="nearest")
    # bilinear interpolation of box centres to every pixel
    yy = (np.arange(ny) + 0.5) / box - 0.5
    xx = (np.arange(nx) + 0.5) / box - 0.5
    Y, X = np.meshgrid(np.clip(yy, 0, gy - 1), np.clip(xx, 0, gx - 1), indexing="ij")
    coords = np.array([Y, X])
    return (ndimage.map_coordinates(med, coords, order=1, mode="nearest"),
            ndimage.map_coordinates(std, coords, order=1, mode="nearest"))


def _gaussian_kernel(fwhm_px: float) -> np.ndarray:
    sigma = fwhm_px / 2.3548
    r = max(2, int(math.ceil(3 * sigma)))
    y, x = np.mgrid[-r:r + 1, -r:r + 1]
    k = np.exp(-(x * x + y * y) / (2 * sigma * sigma))
    return k / k.sum()


def significance_map(sub: np.ndarray, valid: np.ndarray, fwhm_px: float) -> np.ndarray:
    """Matched-filter significance: the filtered image divided by the local
    robust std of the filtered image itself."""
    filtered = ndimage.convolve(np.where(valid, sub, 0.0), _gaussian_kernel(fwhm_px), mode="constant")
    # pixels whose kernel footprint touches invalid pixels are not trusted
    touched = ndimage.binary_dilation(~valid, iterations=2)
    ok = valid & ~touched
    _, noise = background_maps(filtered, ok)
    snr = filtered / np.where(noise > 0, noise, np.nan)
    snr[~ok] = np.nan
    return snr


def measure_fwhm(sub: np.ndarray, peaks: list[tuple[int, int]]) -> float:
    """Median FWHM (px) of isolated bright stars from second moments of a
    7 x 7 stamp (background-subtracted)."""
    values = []
    y, x = np.mgrid[-3:4, -3:4]
    for py, px in peaks:
        st = sub[py - 3:py + 4, px - 3:px + 4]
        if st.shape != (7, 7) or not np.isfinite(st).all():
            continue
        w = np.clip(st, 0, None)
        tot = w.sum()
        if tot <= 0:
            continue
        cx, cy = (w * x).sum() / tot, (w * y).sum() / tot
        var = (w * ((x - cx) ** 2 + (y - cy) ** 2)).sum() / tot / 2
        if var > 0:
            values.append(2.3548 * math.sqrt(var))
    if not values:
        raise ValueError("no star suitable for measuring the FWHM")
    return float(np.median(values))


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

@dataclass
class EpochImage:
    sub: np.ndarray          # background-subtracted image (NaN outside valid)
    noise: np.ndarray        # per-pixel robust noise
    snr: np.ndarray          # matched-filter significance map
    fwhm_px: float
    median_noise: float


def _centroid_1d(m: float, c: float, p: float) -> float:
    """Sub-pixel offset of a peak from three samples (Gaussian fit when all
    are positive, else parabolic)."""
    if m > 0 and c > 0 and p > 0:
        lm, lc, lp = math.log(m), math.log(c), math.log(p)
        den = lm - 2 * lc + lp
        if den < 0:
            return float(np.clip(0.5 * (lm - lp) / den, -0.5, 0.5))
    den = m - 2 * c + p
    if den < 0:
        return float(np.clip(0.5 * (m - p) / den, -0.5, 0.5))
    return 0.0


def psf_match(img: np.ndarray, valid: np.ndarray, fwhm_from: float, fwhm_to: float) -> np.ndarray:
    """Convolve with the Gaussian that turns FWHM `fwhm_from` into
    `fwhm_to` (normalised over valid pixels; invalid pixels stay NaN)."""
    k = _gaussian_kernel(math.sqrt(max(fwhm_to ** 2 - fwhm_from ** 2, 1e-6)))
    num = ndimage.convolve(np.where(valid, img, 0.0), k, mode="constant")
    den = ndimage.convolve(valid.astype(float), k, mode="constant")
    out = np.where(valid & (den > 0), num / np.where(den > 0, den, 1.0), np.nan)
    return out


def prepare_epoch(img: np.ndarray, valid: np.ndarray, fwhm_px: Optional[float] = None) -> EpochImage:
    bkg, noise = background_maps(img, valid)
    sub = np.where(valid, img - bkg, np.nan)
    if fwhm_px is None:
        # first pass with a nominal kernel to find bright stars for the FWHM
        snr0 = significance_map(np.nan_to_num(sub), valid, 1.5)
        pk = _local_maxima(snr0, 50.0)
        fwhm_px = measure_fwhm(sub, pk[:300])
    snr = significance_map(np.nan_to_num(sub), valid, fwhm_px)
    return EpochImage(sub=sub, noise=noise, snr=snr, fwhm_px=fwhm_px,
                      median_noise=float(np.median(noise[valid])))


def _local_maxima(snr: np.ndarray, threshold: float) -> list[tuple[int, int]]:
    s = np.nan_to_num(snr, nan=-np.inf)
    peak = (s == ndimage.maximum_filter(s, size=3, mode="constant", cval=-np.inf)) & (s >= threshold)
    ys, xs = np.nonzero(peak)
    order = np.argsort(-s[ys, xs])
    return [(int(ys[i]), int(xs[i])) for i in order]


def detect(ep: EpochImage, threshold: float = DETECTION_SNR) -> list[dict[str, Any]]:
    """Sources in one epoch: position, SNR, brightness and shape."""
    out = []
    ny, nx = ep.sub.shape
    yy, xx = np.mgrid[-2:3, -2:3]
    aperture = (xx * xx + yy * yy) <= APERTURE_RADIUS_PX ** 2
    for py, px in _local_maxima(ep.snr, threshold):
        if py < 2 or px < 2 or py > ny - 3 or px > nx - 3:
            continue
        st = ep.sub[py - 2:py + 3, px - 2:px + 3]
        finite = bool(np.isfinite(st).all())
        s = np.nan_to_num(st)
        dx = _centroid_1d(s[2, 1], s[2, 2], s[2, 3])
        dy = _centroid_1d(s[1, 2], s[2, 2], s[3, 2])
        core = s[1:4, 1:4]
        core_sum = float(core.sum())
        w = np.clip(s, 0, None)
        tot = float(w.sum())
        if tot > 0:
            mx, my = (w * xx).sum() / tot, (w * yy).sum() / tot
            vx = (w * (xx - mx) ** 2).sum() / tot
            vy = (w * (yy - my) ** 2).sum() / tot
            roundness = float((vx - vy) / (vx + vy)) if vx + vy > 0 else 0.0
        else:
            roundness = 0.0
        snr = float(ep.snr[py, px])
        out.append({
            "x": px + dx,
            "y": py + dy,
            "snr": snr,
            "peak": float(s[2, 2]),
            "flux": float(s[aperture].sum()),
            # fraction of the 3 x 3 core light in the brightest pixel;
            # ~1 for a single-pixel spike, lower for a real PSF
            "sharpness": float(s[2, 2] / core_sum) if core_sum > 0 else float("nan"),
            "roundness": roundness,
            "centroid_error_px": ep.fwhm_px / (2.3548 * snr),
            # the 3-point fit wanted to move past the neighbouring pixel:
            # an asymmetric (blended or flat-topped) profile
            "centroid_clipped": max(abs(dx), abs(dy)) >= 0.499,
            "all_finite": finite,
        })
    return out


def forced_snr(ep: EpochImage, x: float, y: float, radius: int = 1) -> float:
    """Highest matched-filter significance within `radius` px of (x, y)."""
    ix, iy = int(round(x)), int(round(y))
    st = ep.snr[max(iy - radius, 0):iy + radius + 1, max(ix - radius, 0):ix + radius + 1]
    return float(np.nanmax(st)) if np.isfinite(st).any() else float("nan")


# ---------------------------------------------------------------------------
# Positional error model, measured from the data
# ---------------------------------------------------------------------------

def calibrate_position_scatter(pairs: list[tuple[float, float, np.ndarray]]) -> dict[str, Any]:
    """Fit sigma(snr)^2 = sigma_sys^2 + k^2 (1/snr_A^2 + 1/snr_B^2) per axis
    to the offsets of mutually matched sources. Uses robust (MAD) scatter
    in SNR bins, so the few real movers or blends among thousands of
    stationary stars do not inflate it. This measures alignment residuals,
    centroiding of the undersampled PSF and noise together instead of
    assuming a formula."""
    if len(pairs) < 30:
        return {"sigma_sys_px": 0.1, "k_px": 1.0, "bins": []}
    inv = np.array([1 / p[0] ** 2 + 1 / p[1] ** 2 for p in pairs])
    off = np.array([p[2] for p in pairs])
    order = np.argsort(inv)
    bins = []
    for chunk in np.array_split(order, max(3, min(12, len(pairs) // 150))):
        sig = 1.4826 * np.median(np.abs(off[chunk] - np.median(off[chunk], axis=0)), axis=0)
        bins.append((float(np.median(inv[chunk])), float(np.sqrt(np.mean(sig ** 2))), len(chunk)))
    x = np.array([b[0] for b in bins])
    y = np.array([b[1] ** 2 for b in bins])
    coef, *_ = np.linalg.lstsq(np.c_[np.ones_like(x), x], y, rcond=None)
    s2, k2 = max(coef[0], 0.05 ** 2), max(coef[1], 0.0)
    return {"sigma_sys_px": float(math.sqrt(s2)), "k_px": float(math.sqrt(k2)),
            "bins": [{"snr_eff": float(1 / math.sqrt(b[0])), "sigma_px": b[1], "n": b[2]} for b in bins]}


def position_sigma(model: dict[str, Any], snr_a: float, snr_b: float) -> float:
    """1-sigma per-axis offset expected between the two epochs' positions."""
    inv = 1 / snr_a ** 2 + 1 / snr_b ** 2
    return math.sqrt(model["sigma_sys_px"] ** 2 + model["k_px"] ** 2 * inv)


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def _xy(sources: list[dict]) -> np.ndarray:
    return np.array([[s["x"], s["y"]] for s in sources]) if sources else np.zeros((0, 2))


def _mutual_matches(pa: np.ndarray, pb: np.ndarray, radius: float) -> list[tuple[int, int, float]]:
    if len(pa) == 0 or len(pb) == 0:
        return []
    da, ia = cKDTree(pb).query(pa)
    db, ib = cKDTree(pa).query(pb)
    return [(i, int(ia[i]), float(da[i])) for i in range(len(pa))
            if da[i] <= radius and ib[ia[i]] == i]


def find_candidates(
    a: np.ndarray,
    b: np.ndarray,
    valid: np.ndarray,
    *,
    difference: Optional[np.ndarray] = None,
    bad_a: Optional[np.ndarray] = None,
    bad_b: Optional[np.ndarray] = None,
    fwhm_px: Optional[float] = None,
) -> dict[str, Any]:
    """Run the full two-epoch pipeline on two images on the same grid.

    `bad_a` / `bad_b` are boolean maps of SPHEREx-flagged pixels on the
    shared grid (None = flags unavailable). `difference` defaults to b - a.
    Positions are 0-indexed pixel coordinates of the shared grid."""
    valid = valid & np.isfinite(a) & np.isfinite(b)
    if difference is None:
        difference = b - a
    ea = prepare_epoch(a, valid, fwhm_px)
    eb = prepare_epoch(b, valid, fwhm_px)
    native_fwhm = {"A": ea.fwhm_px, "B": eb.fwhm_px}
    # PSF matching: blur the sharper image to the other's resolution, so a
    # source (or an unflagged single-pixel artifact) looks the same in both
    # and detection depth, shape tests and centroid biases are symmetric
    fwhm = max(ea.fwhm_px, eb.fwhm_px)
    if ea.fwhm_px < fwhm:
        ea = prepare_epoch(psf_match(a, valid, ea.fwhm_px, fwhm), valid, fwhm)
    elif eb.fwhm_px < fwhm:
        eb = prepare_epoch(psf_match(b, valid, eb.fwhm_px, fwhm), valid, fwhm)

    src = {"A": detect(ea), "B": detect(eb)}
    ep = {"A": ea, "B": eb}
    pts = {k: _xy(v) for k, v in src.items()}

    # --- 4. cross-match and calibrate the stationary tolerance ---------
    match_radius = MATCH_RADIUS_FWHM * fwhm
    matches = _mutual_matches(pts["A"], pts["B"], match_radius)
    bright = [(i, j) for i, j, _ in matches if src["A"][i]["snr"] >= 50 and src["B"][j]["snr"] >= 50]
    if len(bright) >= 10:
        off = np.array([pts["B"][j] - pts["A"][i] for i, j in bright])
        shift = np.median(off, axis=0)
    else:
        shift = np.zeros(2)
    scatter = calibrate_position_scatter(
        [(src["A"][i]["snr"], src["B"][j]["snr"], pts["B"][j] - shift - pts["A"][i]) for i, j, _ in matches])
    sigma_sys = scatter["sigma_sys_px"]
    # per-source centroid error from the measured model (not a formula)
    for key in ("A", "B"):
        for s in src[key]:
            s["centroid_error_px"] = scatter["k_px"] / s["snr"]

    def tolerance(sa: dict, sb: dict) -> float:
        return STATIONARY_NSIGMA * position_sigma(scatter, sa["snr"], sb["snr"])

    # --- star-likeness calibrated on stationary stars, per epoch -------
    matched_a = {i for i, _, _ in matches}
    matched_b = {j for _, j, _ in matches}
    sharp_limit = {}
    for key, idx in (("A", matched_a), ("B", matched_b)):
        s = np.array([src[key][i]["sharpness"] for i in idx if src[key][i]["snr"] >= 10])
        s = s[np.isfinite(s)]
        sharp_limit[key] = float(np.percentile(s, 99)) if len(s) >= 20 else 0.9
    # how much the same stationary star's shape differs between the epochs
    dsharp = np.array([abs(src["A"][i]["sharpness"] - src["B"][j]["sharpness"]) for i, j, _ in matches
                       if min(src["A"][i]["snr"], src["B"][j]["snr"]) >= MIN_SHIFT_SNR])
    dsharp = dsharp[np.isfinite(dsharp)]
    shape_limit = float(np.percentile(dsharp, 99)) if len(dsharp) >= 20 else 0.2

    # bright stars (either epoch) for the halo veto; all sources for crowding
    halo_pts = np.array([[s["x"], s["y"]] for k in ("A", "B") for s in src[k] if s["snr"] >= HALO_PEAK_SNR]).reshape(-1, 2)
    halo_tree = cKDTree(halo_pts) if len(halo_pts) else None
    trees = {k: cKDTree(pts[k]) if len(pts[k]) else None for k in ("A", "B")}
    # distance to the nearest invalid pixel or the array border
    edge_dist = ndimage.distance_transform_edt(np.pad(valid, 1))[1:-1, 1:-1]
    # significance of the B - A difference, with its noise measured from the
    # filtered difference image itself (the reprojected later image has
    # correlated noise, so a white-noise formula would overstate it)
    diff_bkg, _ = background_maps(difference, valid)
    diff_snr_map = np.nan_to_num(significance_map(np.nan_to_num(np.where(valid, difference - diff_bkg, 0.0)),
                                                  valid, fwhm))

    def diff_snr_at(x: float, y: float) -> float:
        ix, iy = int(round(x)), int(round(y))
        st = diff_snr_map[max(iy - 1, 0):iy + 2, max(ix - 1, 0):ix + 2]
        # the extreme value with its sign
        return float(st.flat[np.argmax(np.abs(st))])

    def vetoes(key: str, s: dict, expect_sign: int, partner: Optional[dict] = None) -> list[str]:
        """Quality checks for a source in epoch `key`. expect_sign: +1
        later-only (B - A positive), -1 earlier-only, 0 skips the
        difference test. `partner` is ignored by the crowding test."""
        reasons = []
        x, y = s["x"], s["y"]
        ix, iy = int(round(x)), int(round(y))
        if edge_dist[iy, ix] < EDGE_MARGIN_PX:
            reasons.append(VETO_EDGE)
        if not s["all_finite"]:
            reasons.append(VETO_NONFINITE)
        box = (slice(max(iy - 2, 0), iy + 3), slice(max(ix - 2, 0), ix + 3))
        if any(np.any(np.nan_to_num(e.sub[box]) < -EXTREME_NEGATIVE_SIGMA * e.noise[box]) for e in (ea, eb)):
            reasons.append(VETO_EXTREME)
        bad = bad_a if key == "A" else bad_b
        if bad is not None:
            r = FLAG_RADIUS_PX
            if bad[max(iy - r, 0):iy + r + 1, max(ix - r, 0):ix + r + 1].any():
                reasons.append(VETO_FLAGGED)
        if not np.isfinite(s["sharpness"]) or s["sharpness"] > sharp_limit[key]:
            reasons.append(VETO_MORPHOLOGY)
        if halo_tree is not None:
            # the source itself (and its counterpart) are not their own halo
            own = [(x, y)] + ([(partner["x"], partner["y"])] if partner else [])
            near = halo_tree.query_ball_point([x, y], HALO_RADIUS_PX)
            if any(all(math.hypot(*(halo_pts[n] - o)) > 0.5 for o in own) for n in near):
                reasons.append(VETO_HALO)
        crowd = CROWDING_RADIUS_FWHM * fwhm
        n_near = 0
        for k in ("A", "B"):
            if trees[k] is not None:
                n_near += sum(1 for n in trees[k].query_ball_point([x, y], crowd)
                              if src[k][n] is not s and src[k][n] is not partner)
        if n_near:
            reasons.append(VETO_BLEND)
        if s["centroid_error_px"] > MAX_CENTROID_ERROR_PX or s["centroid_clipped"]:
            reasons.append(VETO_CENTROID)
        if expect_sign:
            d = diff_snr_at(x, y)
            if not (np.sign(d) == expect_sign and abs(d) >= DIFF_SUPPORT_SNR):
                reasons.append(VETO_DIFFERENCE)
        return reasons

    rejected: dict[str, int] = {}

    def reject(reasons: list[str]) -> None:
        # count each rejected source once, under its first (most basic) reason
        rejected[reasons[0]] = rejected.get(reasons[0], 0) + 1

    # --- matched pairs: stationary or shifted ---------------------------
    shifted = []
    beyond_tolerance = 0
    for i, j, _ in matches:
        sa, sb = src["A"][i], src["B"][j]
        d = pts["B"][j] - shift - pts["A"][i]
        sep = float(np.hypot(*d))
        tol = tolerance(sa, sb)
        if sep <= tol:
            reject([VETO_STATIONARY])
            continue
        beyond_tolerance += 1
        if min(sa["snr"], sb["snr"]) < MIN_SHIFT_SNR:
            reject([VETO_CENTROID])
            continue
        # a shift smaller than the PSF shows as a +/- dipole in the
        # difference image, so the sign test does not apply (expect_sign 0)
        reasons = list(dict.fromkeys(vetoes("A", sa, 0, sb) + vetoes("B", sb, 0, sa)))
        if not abs(sa["sharpness"] - sb["sharpness"]) <= shape_limit:
            reasons.append(VETO_SHAPE_MISMATCH)
        if reasons:
            reject(reasons)
            continue
        shifted.append({"kind": "shifted_match", "A": sa, "B": sb,
                        "separation_px": sep, "tolerance_px": tol,
                        "significance": sep / (tol / STATIONARY_NSIGMA)})

    # --- single-epoch sources ------------------------------------------
    singles: dict[str, list[dict]] = {"A": [], "B": []}
    for key, matched, sign in (("A", matched_a, -1), ("B", matched_b, +1)):
        other = ep["B" if key == "A" else "A"]
        for n, s in enumerate(src[key]):
            if n in matched:
                continue
            # same sky position in the other epoch (B = A + residual shift)
            sgn = 1 if key == "A" else -1
            forced = forced_snr(other, s["x"] + sgn * shift[0], s["y"] + sgn * shift[1])
            s["forced_other_snr"] = forced
            if np.isfinite(forced) and forced >= FORCED_PRESENT_SNR:
                reject([VETO_PRESENT_BOTH])
                continue
            reasons = vetoes(key, s, sign)
            if reasons:
                reject(reasons)
                continue
            s["difference_snr"] = diff_snr_at(s["x"], s["y"])
            singles[key].append(s)

    # --- pairing earlier-only with later-only --------------------------
    pairs = []
    used_a: set[int] = set()
    used_b: set[int] = set()
    if singles["A"] and singles["B"]:
        pb_ = _xy(singles["B"])
        tb = cKDTree(pb_)
        options = []
        for i, sa in enumerate(singles["A"]):
            for j in tb.query_ball_point([sa["x"], sa["y"]], MAX_PAIR_SEPARATION_PX):
                sb = singles["B"][j]
                if sa["flux"] <= 0 or sb["flux"] <= 0:
                    continue
                ratio = sb["flux"] / sa["flux"]
                if 1 / PAIR_FLUX_RATIO_MAX <= ratio <= PAIR_FLUX_RATIO_MAX:
                    options.append((float(np.hypot(sb["x"] - sa["x"], sb["y"] - sa["y"])), i, j))
        alternatives_a = {i: sum(1 for _, a_, _ in options if a_ == i) for i in range(len(singles["A"]))}
        alternatives_b = {j: sum(1 for _, _, b_ in options if b_ == j) for j in range(len(singles["B"]))}
        for sep, i, j in sorted(options):
            if i in used_a or j in used_b:
                continue
            used_a.add(i)
            used_b.add(j)
            pairs.append({"kind": "possible_position_change", "A": singles["A"][i], "B": singles["B"][j],
                          "separation_px": sep,
                          "alternative_partners": alternatives_a[i] + alternatives_b[j] - 2})

    single_changes = (
        [{"kind": "seen_only_earlier", "A": s, "B": None} for n, s in enumerate(singles["A"]) if n not in used_a]
        + [{"kind": "seen_only_later", "A": None, "B": s} for n, s in enumerate(singles["B"]) if n not in used_b]
    )

    return {
        "fwhm_px": native_fwhm,
        "matched_fwhm_px": fwhm,
        "median_noise": {"A": ea.median_noise, "B": eb.median_noise},
        "detections": {"A": len(src["A"]), "B": len(src["B"])},
        "matched": len(matches),
        "alignment": {"shift_px": [float(shift[0]), float(shift[1])], "sigma_sys_px": sigma_sys,
                      "bright_stars_used": len(bright)},
        "position_scatter": scatter,
        # how many matched sources lie beyond the stationary tolerance, vs.
        # how many a purely Gaussian error of the fitted size would give
        "shift_tail": {"observed": beyond_tolerance,
                       "gaussian_expectation": len(matches) * math.exp(-STATIONARY_NSIGMA ** 2 / 2)},
        "match_radius_px": match_radius,
        "sharpness_limit": sharp_limit,
        "shape_mismatch_limit": shape_limit,
        "rejected": rejected,
        "candidates": pairs + shifted + single_changes,
    }


# ---------------------------------------------------------------------------
# Real ~6-month pair: load, run, convert to sky coordinates
# ---------------------------------------------------------------------------

def _load_real_pair() -> dict[str, Any]:
    from astropy.io import fits
    from astropy.wcs import WCS

    meta = json.loads((DATA_DIR / "metadata.json").read_text(encoding="utf-8"))
    with fits.open(DATA_DIR / "epoch_A_2025-06-19.fits") as h:
        a = h[0].data.astype(np.float64)
        header = h[0].header.copy()
    b = fits.getdata(DATA_DIR / "epoch_B_2025-12-17_aligned.fits").astype(np.float64)
    valid = fits.getdata(DATA_DIR / "overlap_mask.fits") > 0
    diff = fits.getdata(DATA_DIR / "difference_B_minus_A.fits").astype(np.float64)
    wcs = WCS(header)
    crop = meta["crop"]
    bad_a = bad_b = None
    flag_notes = []

    # earlier observation: the shared grid IS a crop of its native grid
    src_a = BASE_DIR / meta["epoch_A"]["file"]
    if src_a.is_file():
        with fits.open(src_a) as h:
            flags = h["FLAGS"].data[crop["y0"]:crop["y1"], crop["x0"]:crop["x1"]].astype(np.int64)
        bad_a = (flags & BAD_FLAG_MASK) != 0
    else:
        flag_notes.append(f"{src_a.name} not found: earlier-epoch pixel flags not checked")

    # later observation: map every shared-grid pixel to its native pixel
    src_b = BASE_DIR / meta["epoch_B"]["file"]
    if src_b.is_file():
        with fits.open(src_b) as h:
            flags = h["FLAGS"].data.astype(np.int64)
            wb = WCS(h["IMAGE"].header).celestial
        ny, nx = a.shape
        yy, xx = np.mgrid[0:ny, 0:nx]
        ra, dec = wcs.pixel_to_world_values(xx.ravel(), yy.ravel())
        bx, by = wb.world_to_pixel_values(ra, dec)
        bx = np.rint(bx).astype(int)
        by = np.rint(by).astype(int)
        inside = (bx >= 0) & (by >= 0) & (bx < flags.shape[1]) & (by < flags.shape[0])
        bad = np.zeros(ny * nx, dtype=bool)
        bad[inside] = (flags[by[inside], bx[inside]] & BAD_FLAG_MASK) != 0
        # bilinear reprojection spreads a native pixel over its neighbours
        bad_b = ndimage.binary_dilation(bad.reshape(ny, nx))
    else:
        flag_notes.append(f"{src_b.name} not found: later-epoch pixel flags not checked")

    return {"meta": meta, "a": a, "b": b, "valid": valid, "diff": diff,
            "wcs": wcs, "bad_a": bad_a, "bad_b": bad_b, "flag_notes": flag_notes}


def _sky(wcs, s: Optional[dict]) -> Optional[dict]:
    if s is None:
        return None
    ra, dec = wcs.pixel_to_world_values(s["x"], s["y"])
    return {"ra": float(ra), "dec": float(dec), "x": s["x"], "y": s["y"]}


def _position_angle_deg(ra1: float, dec1: float, ra2: float, dec2: float) -> float:
    """East of north, from (ra1, dec1) towards (ra2, dec2)."""
    r1, d1, r2, d2 = map(math.radians, (ra1, dec1, ra2, dec2))
    dra = r2 - r1
    pa = math.atan2(math.sin(dra), math.cos(d1) * math.tan(d2) - math.sin(d1) * math.cos(dra))
    return math.degrees(pa) % 360.0


def _angular_sep_arcsec(ra1: float, dec1: float, ra2: float, dec2: float) -> float:
    r1, d1, r2, d2 = map(math.radians, (ra1, dec1, ra2, dec2))
    h = math.sin((d2 - d1) / 2) ** 2 + math.cos(d1) * math.cos(d2) * math.sin((r2 - r1) / 2) ** 2
    return math.degrees(2 * math.asin(min(1.0, math.sqrt(h)))) * 3600.0


def _r(v: Optional[float], nd: int = 4) -> Optional[float]:
    if v is None or not np.isfinite(v):
        return None
    return round(float(v), nd)


def run_real_pair() -> dict[str, Any]:
    """Run the pipeline on the verified ~6-month pair and return a
    JSON-ready result with sky coordinates."""
    from astropy.wcs.utils import proj_plane_pixel_scales

    d = _load_real_pair()
    meta = d["meta"]
    res = find_candidates(d["a"], d["b"], d["valid"], difference=d["diff"],
                          bad_a=d["bad_a"], bad_b=d["bad_b"])
    wcs = d["wcs"]
    scale = float(np.mean(proj_plane_pixel_scales(wcs.celestial)) * 3600)
    gap = float(meta["time_gap_days"])
    date_a = meta["epoch_A"]["date"]
    date_b = meta["epoch_B"]["date"]

    order = {"possible_position_change": 0, "shifted_match": 1, "seen_only_earlier": 2, "seen_only_later": 3}
    cands = sorted(res["candidates"], key=lambda c: (order[c["kind"]], -max(
        (c["A"] or {}).get("snr", 0), (c["B"] or {}).get("snr", 0))))

    out = []
    for n, c in enumerate(cands, start=1):
        pa, pb = _sky(wcs, c["A"]), _sky(wcs, c["B"])
        rec: dict[str, Any] = {
            "candidate_id": f"SX6M-{n:03d}",
            "kind": c["kind"],
            "earlier_date": date_a,
            "later_date": date_b,
            "time_baseline_days": gap,
            "earlier": None,
            "later": None,
            "angular_displacement_arcsec": None,
            "apparent_motion_arcsec_per_day": None,
            "position_angle_deg": None,
            "brightness_ratio_later_over_earlier": None,
        }
        for key, p, s in (("earlier", pa, c["A"]), ("later", pb, c["B"])):
            if p is None:
                continue
            rec[key] = {
                "ra": _r(p["ra"], 6), "dec": _r(p["dec"], 6),
                "x": _r(p["x"], 2), "y": _r(p["y"], 2),
                "snr": _r(s["snr"], 1),
                "brightness": _r(s["flux"], 4),
                "peak": _r(s["peak"], 4),
                "sharpness": _r(s["sharpness"], 3),
                "roundness": _r(s["roundness"], 3),
                "centroid_error_arcsec": _r(s["centroid_error_px"] * scale, 2),
                "forced_snr_in_other_image": _r(s.get("forced_other_snr"), 1),
                "difference_snr": _r(s.get("difference_snr"), 1),
            }
        if pa and pb:
            disp = _angular_sep_arcsec(pa["ra"], pa["dec"], pb["ra"], pb["dec"])
            rec["angular_displacement_arcsec"] = _r(disp, 2)
            rec["apparent_motion_arcsec_per_day"] = _r(disp / gap, 4)
            rec["position_angle_deg"] = _r(_position_angle_deg(pa["ra"], pa["dec"], pb["ra"], pb["dec"]), 1)
            if c["A"]["flux"] > 0:
                rec["brightness_ratio_later_over_earlier"] = _r(c["B"]["flux"] / c["A"]["flux"], 3)
        if c["kind"] == "possible_position_change":
            rec["alternative_partners"] = c["alternative_partners"]
        if c["kind"] == "shifted_match":
            rec["shift_significance_sigma"] = _r(c["significance"], 1)
            rec["stationary_tolerance_arcsec"] = _r(c["tolerance_px"] * scale, 2)
        rec["status"] = "passed_current_checks"
        rec["caveats"] = _caveats(c["kind"])
        out.append(rec)

    fwhm = max(res["fwhm_px"].values())
    stationary_tol_min = STATIONARY_NSIGMA * res["alignment"]["sigma_sys_px"] * scale
    counts = {k: sum(1 for c in out if c["kind"] == k) for k in order}
    return {
        "pipeline": PIPELINE_VERSION,
        "inputs": {
            "earlier": {"date": date_a, "file": meta["epoch_A"]["file"],
                        "grid_file": "epoch_A_2025-06-19.fits",
                        "wavelength_um": meta["epoch_A"]["wavelength_um"]},
            "later": {"date": date_b, "file": meta["epoch_B"]["file"],
                      "grid_file": "epoch_B_2025-12-17_aligned.fits",
                      "wavelength_um": meta["epoch_B"]["wavelength_um"]},
            "overlap_mask": "overlap_mask.fits",
            "difference": "difference_B_minus_A.fits",
            "time_baseline_days": gap,
            "pixel_scale_arcsec": scale,
        },
        "measured": {
            "fwhm_arcsec": {k: _r(v * scale, 2) for k, v in res["fwhm_px"].items()},
            "median_noise_mjy_sr": {k: _r(v, 5) for k, v in res["median_noise"].items()},
            "detections": res["detections"],
            "matched_in_both": res["matched"],
            "alignment_residual_shift_arcsec": [_r(v * scale, 3) for v in res["alignment"]["shift_px"]],
            "alignment_scatter_arcsec": _r(res["alignment"]["sigma_sys_px"] * scale, 3),
            "bright_stars_used_for_alignment": res["alignment"]["bright_stars_used"],
            "psf_matched_fwhm_arcsec": _r(res["matched_fwhm_px"] * scale, 2),
            "position_error_model": {
                "sigma_floor_arcsec": _r(res["position_scatter"]["sigma_sys_px"] * scale, 3),
                "k_arcsec": _r(res["position_scatter"]["k_px"] * scale, 3),
                "formula": "sigma^2 = floor^2 + k^2 (1/SNR_earlier^2 + 1/SNR_later^2), per axis",
            },
            "matched_beyond_stationary_tolerance": res["shift_tail"]["observed"],
            "gaussian_expectation_beyond_tolerance": _r(res["shift_tail"]["gaussian_expectation"], 3),
        },
        "thresholds": {
            "detection_snr": DETECTION_SNR,
            "forced_present_snr": FORCED_PRESENT_SNR,
            "match_radius_arcsec": _r(res["match_radius_px"] * scale, 2),
            "stationary_tolerance": f"{STATIONARY_NSIGMA:g} sigma of the combined alignment + centroid error "
                                    f"(at least {stationary_tol_min:.2f} arcsec for bright stars)",
            "edge_margin_arcsec": _r(EDGE_MARGIN_PX * scale, 1),
            "halo_radius_arcsec": _r(HALO_RADIUS_PX * scale, 1),
            "crowding_radius_arcsec": _r(CROWDING_RADIUS_FWHM * fwhm * scale, 1),
            "max_pair_separation_arcsec": _r(MAX_PAIR_SEPARATION_PX * scale, 0),
            "pair_brightness_ratio_max": PAIR_FLUX_RATIO_MAX,
            "difference_support_snr": DIFF_SUPPORT_SNR,
        },
        "rejected_by_reason": dict(sorted(res["rejected"].items(), key=lambda kv: -kv[1])),
        "rejection_reasons": VETO_TEXT,
        "flag_notes": d["flag_notes"],
        "counts": {"total": len(out), **counts},
        "candidates": out,
        "limitations": LIMITATIONS,
    }


LIMITATIONS = [
    "Two observations cannot establish a trajectory, an orbit or acceleration.",
    "A pairing of an earlier-only and a later-only source is a possibility, not a measured motion; "
    "other pairings may be equally possible.",
    "A source seen in only one observation may be variable, an artifact or noise rather than a mover.",
    "The two images are 0.0032 um apart in wavelength, so small brightness differences are expected.",
    "Every candidate needs follow-up observations before anything can be concluded.",
]


def _caveats(kind: str) -> list[str]:
    if kind == "possible_position_change":
        return ["Two positions only: the pairing is a possibility, not a measured track."]
    if kind == "shifted_match":
        return ["The shift is smaller than the image blur, so blends and pixel sampling can mimic it.",
                "A real shift this small in six months would need a nearby star with a very high proper "
                "motion; no Solar System object moves this slowly."]
    return ["Seen in one observation only: could be variability, an artifact or noise."]


def write_result(path: Path = RESULT_JSON) -> dict[str, Any]:
    result = run_real_pair()
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    r = write_result()
    print(json.dumps({k: r[k] for k in ("measured", "rejected_by_reason", "counts")}, indent=2))
    print(f"wrote {RESULT_JSON}")
