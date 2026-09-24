"""
Three-epoch (A -> C -> B) moving-source linker for the 31-day SPHEREx
D3 observations, with a stationary-source veto.

Detection: DAOStarFinder, 7 sigma, FWHM 2 px, r = 3 px aperture as in the
original pipeline, but with the sharpness/roundness limits relaxed and
SPHEREx-flagged bad pixels masked (see "second effect" below; with the
default limits only ~40% of injected point sources were detected per epoch).
Linking pairs an Epoch A source with an Epoch B source 5-120" away, predicts
the Epoch C position by linear interpolation in time, and requires a C
source there with consistent flux.

Root cause this version fixes: the original linker drew A, C and B sources
from the FULL source lists, including sources that are simply stationary
stars present in every epoch. With ~0.3 sources/arcmin^2 each A source has
~4 B sources within 120", i.e. ~5e4 A-B pairs; a random C source falls
inside a 4" gate ~0.4% of the time, so ~200 chance "tracks" joining three
unrelated stationary stars survived, and the flux filter trimmed them to
the 23 previous candidates. Nothing required a track's detections to be
ABSENT from the other epochs. A second effect made this worse: the SPHEREx
PSF (FWHM 5.2") is smaller than a 6.15" pixel, so a star's DAOStarFinder
sharpness depends on its sub-pixel phase, and the default sharpness cut
(<= 1.0) drops a given stationary star in some epochs but not others --
the star then looks "unmatched" there and is free to be mislinked.

Stationary-source veto (all tests in sky coordinates, never pixels):
  * Astrometric model, calibrated from this data: per-detection centroid
    error sigma_det(flux) fitted (Rayleigh + uniform mixture) to the
    separations of the same stationary sources between epochs; per epoch
    pair a registration offset (median dRA*, dDec, applied) and residual
    registration scatter sigma_reg (spread of offsets across a 4x4 grid of
    sky tiles). sigma_pair^2 = sigma_det1^2 + sigma_det2^2 + sigma_reg^2.
  * Counterpart test: a source in epoch X is STATIONARY if a source is
    detected at the same sky position in another epoch whose footprint
    covers it, with chi2 = sep^2 / sigma_pair^2 <= 11.83 (2 dof, 99.73%),
    and the local chance-coincidence probability (from the local source
    density = crowding) is <= P_CHANCE_MAX. Counterparts are searched in a
    deeper counterpart list (4 sigma, DAOStarFinder sharpness/roundness
    limits relaxed because they reject undersampled point sources by pixel
    phase, SPHEREx-flagged bad pixels masked so hot pixels / cosmic rays
    cannot act as counterparts). The 7-sigma linking detections use the
    same relaxed limits and mask.
    Because DAOStarFinder cannot separate peaks closer than ~25" (4 px), a
    faint persistent source next to a brighter star can be missing from
    another epoch's list; so a forced local-peak test is also applied at the
    same sky position in the other epochs: a local maximum >= 4 sigma whose
    3x3 centroid lies inside the same chi2 gate counts as the same source.
  * BLEND_FRAGMENT: not stationary, but either (i) a persistent source lies
    within one blend radius (PSF FWHM (+) 6.15" pixel = 8.1") at another
    epoch -- a counterpart displaced by blending beyond the astrometric
    gate -- or (ii) it is a feature in a bright star's PSF wing / halo in its
    own epoch: a saturated/nonlinear-flagged pixel within 3 px (18.5", the
    photometry aperture), or low contrast -- the median of the ring 2-3 px
    out is >= 25% of its own peak. SPHEREx's
    PSF (FWHM 0.85 px) puts ~no flux 2 px out, so a genuine point source
    stands far above that ring; a halo feature does not. (Saturated cores
    are flagged and masked, so the star itself is often not in the source
    list.)
  * Track vetoes (applied before a track is accepted):
      STATIONARY_SOURCE       >= 2 of the 3 detections are stationary, or
                              the A->B displacement is not significant
                              given the astrometric uncertainty.
      BLEND_MISLINK           exactly 1 stationary detection, or >= 2
                              detections that are stationary/blend
                              fragments: the apparent path is built from
                              detections around persistent sources.
      INCONSISTENT_TRAJECTORY the C detection misses the constant-velocity
                              prediction beyond its uncertainty plus a
                              3%-of-arc nonlinearity allowance.
    A genuine mover is only vetoed if one of its own detections coincides
    with a stationary source within ~2-4" (probability ~0.2% per detection
    at this density), so moving-source sensitivity is preserved; the old
    tracks that passed only the fixed 4" C gate are logged with reasons.

Outputs
  three_epoch_motion_candidates.csv  accepted tracks (same columns as
                                     before + uncertainty/veto diagnostics)
  rejected_three_epoch_tracks.csv    every track that passed the motion,
                                     flux and (old or new) C-position tests
                                     but was vetoed, with rejection_reason
  three_epoch_linking_calibration.json  the fitted astrometric model
"""

import json
import math
import os
from math import erf

from astropy.io import fits
from astropy.wcs import WCS
from astropy.stats import sigma_clipped_stats
from astropy.coordinates import SkyCoord
import astropy.units as u

from photutils.detection import DAOStarFinder
from photutils.aperture import CircularAperture, aperture_photometry

import numpy as np
import pandas as pd


FILE_A = "level2_2025W19_2B_0166_3D3_spx_l2b-v20-2025-247.fits"
FILE_C = "level2_2025W22_1B_0226_1D3_spx_l2b-v20-2025-250.fits"
FILE_B = "level2_2025W24_1A_0099_1D3_spx_l2b-v20-2025-252.fits"

DETECTION_SIGMA = 7.0
COUNTERPART_SIGMA = 4.0      # deeper list, only used to find stationary counterparts
FWHM = 2.0
APERTURE_RADIUS = 3.0

MIN_TOTAL_MOTION = 5.0       # arcsec
MAX_TOTAL_MOTION = 120.0     # arcsec
OLD_C_POSITION_TOLERANCE = 4.0   # arcsec, the original fixed gate (kept only for the rejection log)

MIN_FLUX_RATIO = 0.4
MAX_FLUX_RATIO = 2.5

CHI2_GATE = 11.829           # chi2, 2 dof, 99.73% (3-sigma equivalent)
NONLINEAR_FRACTION = 0.03    # allowed deviation from linear motion at C, fraction of the A-B arc
P_CHANCE_MAX = 0.05          # a counterpart this likely to be a chance neighbour is not trusted
DENSITY_RADIUS_ARCSEC = 120.0
PIXEL_SCALE_ARCSEC = 6.15
REG_TILES = 4
SHAPE_LIMITS = dict(sharplo=0.0, sharphi=3.0, roundlo=-2.0, roundhi=2.0)
FORCED_PEAK_SNR = 4.0        # forced local-peak presence test at a known position
HALO_RADIUS_PX = 3.0         # = APERTURE_RADIUS: a bright neighbour's wing inside the aperture
SATURATION_BITS = (1, 15)    # MP_OVERFLOW, MP_NONLINEAR: bright-star cores
HALO_CONTRAST = 0.25         # ring (2-3 px) median / own peak at or above this -> halo feature
DETECTIONS_CSV_NAME = "three_epoch_detections.csv"
N_RANDOM_PROBES = 20000      # random sky positions used to measure the false-veto rate
BAD_FLAG_BITS = (0, 1, 2, 4, 5, 6, 9, 10, 11, 15, 17, 19)  # MP_* pixel-quality bits (FLAGS header)
BAD_FLAG_MASK = sum(1 << bit for bit in BAD_FLAG_BITS)

# Injection-recovery testing (test_linker_injection.py): synthetic movers are
# added to in-memory copies of the images only, and every output gets a
# prefix so the real pipeline outputs are never overwritten.
INJECT_JSON = os.environ.get("SPHEREX_INJECT_JSON")
OUTPUT_PREFIX = os.environ.get("SPHEREX_OUTPUT_PREFIX", "")
INJECTED = json.load(open(INJECT_JSON, encoding="utf-8")) if INJECT_JSON else None

CANDIDATES_CSV = OUTPUT_PREFIX + "three_epoch_motion_candidates.csv"
CALIBRATION_JSON = OUTPUT_PREFIX + "three_epoch_linking_calibration.json"
REJECTED_CSV = OUTPUT_PREFIX + "rejected_three_epoch_tracks.csv"
DETECTIONS_CSV = OUTPUT_PREFIX + "three_epoch_detections.csv"
EPOCHS = ["A", "C", "B"]


def inject_point_sources(image, wcs_e, sources, header):
    """Add pixel-integrated Gaussian point sources (FWHM = header PSF_FWHM)
    whose total flux equals `flux` in the image's own units x pixels, i.e.
    comparable to the r = 3 px aperture sums used everywhere here."""
    sig_px = float(header.get("PSF_FWHM", 5.2)) / PIXEL_SCALE_ARCSEC / 2.3548
    for src in sources:
        x0, y0 = (float(v) for v in wcs_e.world_to_pixel_values(src["ra"], src["dec"]))
        xi, yi = int(round(x0)), int(round(y0))
        for yy in range(yi - 3, yi + 4):
            for xx in range(xi - 3, xi + 4):
                if 0 <= yy < image.shape[0] and 0 <= xx < image.shape[1] and np.isfinite(image[yy, xx]):
                    fx = 0.5 * (erf((xx + 0.5 - x0) / (sig_px * 2 ** 0.5)) - erf((xx - 0.5 - x0) / (sig_px * 2 ** 0.5)))
                    fy = 0.5 * (erf((yy + 0.5 - y0) / (sig_px * 2 ** 0.5)) - erf((yy - 0.5 - y0) / (sig_px * 2 ** 0.5)))
                    image[yy, xx] += src["flux"] * fx * fy


def detect_sources(filename, name, sigma=DETECTION_SIGMA):
    """DAOStarFinder with shape limits relaxed for SPHEREx's undersampled PSF
    (default sharphi=1.0 rejects ~half of real point sources depending on
    sub-pixel phase) and SPHEREx-flagged bad pixels masked, so hot pixels,
    cosmic rays and other flagged artifacts cannot become detections."""

    print(f"Detecting {name} ({sigma:g} sigma)...")

    with fits.open(filename) as hdul:

        image = hdul["IMAGE"].data.astype(float)
        header = hdul["IMAGE"].header.copy()

        mjd = header.get("MJD-OBS")

        if INJECTED is not None:
            inject_point_sources(image, WCS(header), INJECTED[name.split()[1]], header)

        flags = hdul["FLAGS"].data.astype(np.int64)
        image[(flags & BAD_FLAG_MASK) != 0] = np.nan

    wcs = WCS(header)

    good = np.isfinite(image)

    mean, median, std = sigma_clipped_stats(
        image[good],
        sigma=3.0
    )

    clean = image.copy()
    clean[~good] = median

    data = clean - median

    finder = DAOStarFinder(
        fwhm=FWHM,
        threshold=sigma * std,
        **SHAPE_LIMITS
    )

    sources = finder(data)

    if sources is None:
        return pd.DataFrame(), mjd

    positions = np.transpose([
        sources["x_centroid"],
        sources["y_centroid"]
    ])

    apertures = CircularAperture(
        positions,
        r=APERTURE_RADIUS
    )

    phot = aperture_photometry(
        data,
        apertures
    )

    rows = []

    for i in range(len(sources)):

        x = float(sources["x_centroid"][i])
        y = float(sources["y_centroid"][i])

        ra, dec = wcs.pixel_to_world_values(
            x,
            y
        )

        flux = float(
            phot["aperture_sum"][i]
        )

        if not np.isfinite(flux) or flux <= 0:
            continue

        rows.append({
            "id": i + 1,
            "ra": float(ra),
            "dec": float(dec),
            "x": x,
            "y": y,
            "flux": flux
        })

    result = pd.DataFrame(rows)

    print(
        name,
        "sources:",
        len(result)
    )

    return result, mjd


def coords(df):
    return SkyCoord(df["ra"].values * u.deg, df["dec"].values * u.deg)


def offsets_arcsec(ra1, dec1, ra2, dec2):
    """(dRA*, dDec) in arcsec from position 1 to position 2 (small angles)."""
    dra = (np.asarray(ra2) - np.asarray(ra1)) * np.cos(np.radians(np.asarray(dec1))) * 3600.0
    ddec = (np.asarray(dec2) - np.asarray(dec1)) * 3600.0
    return dra, ddec


print("1/7 Detecting sources")

files = {"A": FILE_A, "C": FILE_C, "B": FILE_B}
det, deep, mjd, wcs, footprint, pixels, background = {}, {}, {}, {}, {}, {}, {}
raw_pixels, saturated = {}, {}
for e in EPOCHS:
    det[e], mjd[e] = detect_sources(files[e], f"Epoch {e}")
    deep[e], _ = detect_sources(files[e], f"Epoch {e} counterpart list", sigma=COUNTERPART_SIGMA)
    with fits.open(files[e]) as hdul:
        wcs[e] = WCS(hdul["IMAGE"].header)
        footprint[e] = np.isfinite(hdul["IMAGE"].data)
        psf_fwhm = float(hdul["IMAGE"].header.get("PSF_FWHM", 5.2))
        pix = hdul["IMAGE"].data.astype(float)
        flag_bits = hdul["FLAGS"].data.astype(np.int64)
        if INJECTED is not None:
            inject_point_sources(pix, wcs[e], INJECTED[e], hdul["IMAGE"].header)
        raw_pixels[e] = pix.copy()
        saturated[e] = (flag_bits & sum(1 << bit for bit in SATURATION_BITS)) != 0
        pix[(flag_bits & BAD_FLAG_MASK) != 0] = np.nan
        _, bkg_med, bkg_std = sigma_clipped_stats(pix[np.isfinite(pix)], sigma=3.0)
        pixels[e], background[e] = pix, (float(bkg_med), float(bkg_std))

A, C, B = det["A"], det["C"], det["B"]
mjd_a, mjd_c, mjd_b = mjd["A"], mjd["C"], mjd["B"]


def covers(epoch, ra, dec, margin_px=2):
    """True where the sky position falls on valid pixels of this epoch."""
    x, y = wcs[epoch].world_to_pixel_values(np.atleast_1d(ra), np.atleast_1d(dec))
    xi, yi = np.round(x).astype(int), np.round(y).astype(int)
    h, w = footprint[epoch].shape
    inside = (xi >= margin_px) & (yi >= margin_px) & (xi < w - margin_px) & (yi < h - margin_px)
    ok = np.zeros(len(xi), dtype=bool)
    ok[inside] = footprint[epoch][yi[inside], xi[inside]]
    return ok


print("\n2/7 Observation timing")

dt_ab = mjd_b - mjd_a
dt_ac = mjd_c - mjd_a

fraction = dt_ac / dt_ab

print("A MJD:", mjd_a)
print("C MJD:", mjd_c)
print("B MJD:", mjd_b)

print(
    "C position fraction:",
    round(fraction, 4)
)


print("\n3/7 Calibrating the astrometric model from stationary sources")

# registration: median offset per epoch pair (applied) and its spread over
# a 4x4 grid of sky tiles (residual registration uncertainty)
registration = {}
pair_seps = []
for e1, e2 in (("A", "C"), ("A", "B"), ("C", "B")):
    c1, c2 = coords(det[e1]), coords(det[e2])
    idx, d2d, _ = c1.match_to_catalog_sky(c2)
    close = d2d.arcsec < 3.0
    dra, ddec = offsets_arcsec(det[e1]["ra"].values[close], det[e1]["dec"].values[close],
                               det[e2]["ra"].values[idx[close]], det[e2]["dec"].values[idx[close]])
    off = (float(np.median(dra)), float(np.median(ddec)))
    ra_c, dec_c = det[e1]["ra"].values[close], det[e1]["dec"].values[close]
    tx = np.clip(((ra_c - ra_c.min()) / (np.ptp(ra_c) + 1e-9) * REG_TILES).astype(int), 0, REG_TILES - 1)
    ty = np.clip(((dec_c - dec_c.min()) / (np.ptp(dec_c) + 1e-9) * REG_TILES).astype(int), 0, REG_TILES - 1)
    tile_meds = []
    for i in range(REG_TILES):
        for j in range(REG_TILES):
            m = (tx == i) & (ty == j)
            if m.sum() >= 20:
                tile_meds.append((np.median(dra[m]) - off[0], np.median(ddec[m]) - off[1]))
    tile_meds = np.array(tile_meds)
    sigma_reg = float(np.sqrt(np.mean(tile_meds ** 2))) if len(tile_meds) else 0.0
    registration[(e1, e2)] = {"offset_ra": off[0], "offset_dec": off[1], "sigma_reg": sigma_reg,
                              "n_matched": int(close.sum()), "n_tiles": int(len(tile_meds))}
    registration[(e2, e1)] = {"offset_ra": -off[0], "offset_dec": -off[1], "sigma_reg": sigma_reg,
                              "n_matched": int(close.sum()), "n_tiles": int(len(tile_meds))}
    # registration-corrected separations for the centroid-error fit
    rdra, rddec = offsets_arcsec(det[e1]["ra"].values, det[e1]["dec"].values,
                                 det[e2]["ra"].values[idx], det[e2]["dec"].values[idx])
    r_corr = np.hypot(rdra - off[0], rddec - off[1])
    f1 = det[e1]["flux"].values
    f2 = det[e2]["flux"].values[idx]
    pair_seps.append(pd.DataFrame({"r": r_corr, "flux": np.sqrt(f1 * f2)}))
    print(f"  {e1}-{e2}: offset dRA* {off[0]:+.3f}\" dDec {off[1]:+.3f}\", "
          f"sigma_reg {sigma_reg:.3f}\" ({close.sum()} matched stationary sources)")
pair_seps = pd.concat(pair_seps)


def fit_sigma_pair(r, rmax=6.0):
    """MLE of Rayleigh(sigma) + uniform-in-area background within rmax."""
    r = r[r < rmax]
    best = (-np.inf, 1.0)
    for s in np.linspace(0.1, 3.0, 291):
        ray = (r / s ** 2) * np.exp(-r ** 2 / (2 * s ** 2))
        bkg = 2 * r / rmax ** 2
        for f in np.linspace(0.3, 1.0, 36):
            ll = np.sum(np.log(f * ray + (1 - f) * bkg + 1e-300))
            if ll > best[0]:
                best = (ll, s)
    return best[1]


FLUX_BINS = [0.0, 2.0, 4.0, 8.0, 20.0, 80.0, np.inf]
sigma_table = []
for lo, hi in zip(FLUX_BINS[:-1], FLUX_BINS[1:]):
    sub = pair_seps[(pair_seps["flux"] >= lo) & (pair_seps["flux"] < hi)]
    mean_reg2 = np.mean([v["sigma_reg"] ** 2 for v in registration.values()])
    s_pair = fit_sigma_pair(sub["r"].values)
    # sigma_pair^2 = 2 sigma_det^2 + sigma_reg^2
    s_det = math.sqrt(max(s_pair ** 2 - mean_reg2, 0.01) / 2.0)
    sigma_table.append({"flux_lo": lo, "flux_hi": hi, "n": int((sub["r"] < 6).sum()),
                        "sigma_pair": s_pair, "sigma_det": s_det})
    print(f"  flux {lo:>5g}-{hi:<5g}: sigma_det {s_det:.3f}\" (n={int((sub['r'] < 6).sum())})")


def sigma_det(flux):
    flux = np.atleast_1d(flux)
    out = np.empty(len(flux))
    for k, f in enumerate(flux):
        for row in sigma_table:
            if row["flux_lo"] <= f < row["flux_hi"]:
                out[k] = row["sigma_det"]
                break
    return out


BLEND_RADIUS = math.hypot(psf_fwhm, PIXEL_SCALE_ARCSEC)
print(f"  blend radius (PSF FWHM {psf_fwhm:.2f}\" (+) pixel {PIXEL_SCALE_ARCSEC}\"): {BLEND_RADIUS:.2f}\"")

deep_coord = {e: coords(deep[e]) for e in EPOCHS}
det_coord = {e: coords(det[e]) for e in EPOCHS}


print("\n4/7 Classifying every source as stationary / blend fragment / free")


def classify_positions(e, ra, dec, flux):
    """For sky positions observed in epoch e, test for the same source at the
    same position (STATIONARY) or a displaced persistent source within the
    blend radius (BLEND_FRAGMENT) in every other epoch that covers them."""
    ra, dec, flux = np.atleast_1d(ra), np.atleast_1d(dec), np.atleast_1d(flux)
    n = len(ra)
    pos = SkyCoord(ra * u.deg, dec * u.deg)
    s_self = sigma_det(flux)
    stationary = np.zeros(n, dtype=bool)
    blend = np.zeros(n, dtype=bool)
    best_chi2 = np.full(n, np.inf)
    counterpart_epochs = [""] * n
    for o in EPOCHS:
        if o == e:
            continue
        reg = registration[(e, o)]
        on_o = covers(o, ra, dec)
        idx, _, _ = pos.match_to_catalog_sky(deep_coord[o])
        dra, ddec = offsets_arcsec(ra, dec, deep[o]["ra"].values[idx], deep[o]["dec"].values[idx])
        r = np.hypot(dra - reg["offset_ra"], ddec - reg["offset_dec"])
        chi2 = r ** 2 / (s_self ** 2 + sigma_det(deep[o]["flux"].values[idx]) ** 2 + reg["sigma_reg"] ** 2)
        # crowding: chance of an unrelated counterpart-list source this close,
        # from the local density of that list around this position
        rho = local_density(o, pos)
        p_chance = 1 - np.exp(-math.pi * rho * r ** 2)
        hit = on_o & (chi2 <= CHI2_GATE) & (p_chance <= P_CHANCE_MAX)
        near = on_o & (r <= BLEND_RADIUS) & (p_chance <= P_CHANCE_MAX)
        # forced local-peak test at the same (registration-corrected) position
        forced_r = forced_peak_offset(o, ra, dec, reg)
        forced_chi2 = forced_r ** 2 / (s_self ** 2 + sigma_det(np.zeros(n)) ** 2 + reg["sigma_reg"] ** 2)
        forced_p = 1 - np.exp(-math.pi * rho * forced_r ** 2)
        hit |= on_o & (forced_chi2 <= CHI2_GATE) & (forced_p <= P_CHANCE_MAX)
        stationary |= hit
        blend |= near
        for k in np.where(hit)[0]:
            counterpart_epochs[k] += o
        better = on_o & (chi2 < best_chi2)
        best_chi2[better] = chi2[better]
    blend &= ~stationary
    return pd.DataFrame({"stationary": stationary, "blend_fragment": blend,
                         "best_chi2": best_chi2, "counterpart_epochs": counterpart_epochs})


def forced_peak_offset(o, ra, dec, reg):
    """Distance (arcsec) from each expected position in epoch o to the nearest
    local maximum >= FORCED_PEAK_SNR sigma within 1 px, using its 3x3
    background-subtracted centroid; inf where there is none."""
    img = pixels[o]
    med, std = background[o]
    h, w = img.shape
    # expected position in epoch o = position + registration offset
    ra_o = ra + reg["offset_ra"] / 3600.0 / np.cos(np.radians(dec))
    dec_o = dec + reg["offset_dec"] / 3600.0
    x, y = wcs[o].world_to_pixel_values(ra_o, dec_o)
    out = np.full(len(ra), np.inf)
    for k in range(len(ra)):
        xi, yi = int(round(float(x[k]))), int(round(float(y[k])))
        if not (3 <= xi < w - 3 and 3 <= yi < h - 3):
            continue
        best = np.inf
        for py in range(yi - 1, yi + 2):
            for px in range(xi - 1, xi + 2):
                v = img[py, px]
                if not np.isfinite(v) or (v - med) / std < FORCED_PEAK_SNR:
                    continue
                nb = img[py - 1:py + 2, px - 1:px + 2]
                if np.nanmax(nb) > v:
                    continue  # not a local maximum (e.g. a brighter neighbour's wing)
                wgt = np.clip(np.nan_to_num(nb - med), 0, None)
                if wgt.sum() <= 0:
                    continue
                cx = px + float((wgt.sum(axis=0) * np.arange(-1, 2)).sum() / wgt.sum())
                cy = py + float((wgt.sum(axis=1) * np.arange(-1, 2)).sum() / wgt.sum())
                best = min(best, math.hypot(cx - float(x[k]), cy - float(y[k])) * PIXEL_SCALE_ARCSEC)
        out[k] = best
    return out


def halo_flags(e, ra, dec, model_detection=False):
    """Positions in epoch e that sit in a bright star's PSF wing / halo.

    model_detection=False: the position is a real detection; its own peak is
    the 3x3 maximum there. model_detection=True (random probes): model a
    faint point source added at the position, peak = local ring level +
    DETECTION_SIGMA sigma, so the false-veto rate reflects a real mover."""
    img, sat = raw_pixels[e], saturated[e]
    med, std = background[e]
    h, w = img.shape
    rad = int(math.ceil(HALO_RADIUS_PX))
    yy, xx = np.mgrid[-rad:rad + 1, -rad:rad + 1]
    rr = np.hypot(xx, yy)
    within = rr <= HALO_RADIUS_PX
    ring = (rr >= 2.0) & within
    x, y = wcs[e].world_to_pixel_values(np.atleast_1d(ra), np.atleast_1d(dec))
    flag = np.zeros(len(np.atleast_1d(ra)), dtype=bool)
    for k in range(len(flag)):
        xi, yi = int(round(float(x[k]))), int(round(float(y[k])))
        if not (rad <= xi < w - rad and rad <= yi < h - rad):
            continue
        if sat[yi - rad:yi + rad + 1, xi - rad:xi + rad + 1][within].any():
            flag[k] = True
            continue
        win = img[yi - rad:yi + rad + 1, xi - rad:xi + rad + 1] - med
        ring_level = float(np.nanmedian(win[ring]))
        if model_detection:
            own = max(ring_level, 0.0) + DETECTION_SIGMA * std
        else:
            own = float(np.nanmax(win[rad - 1:rad + 2, rad - 1:rad + 2]))
        if not (np.isfinite(own) and own > 0):
            continue
        flag[k] = bool(ring_level >= HALO_CONTRAST * own)
    return flag


def local_density(o, pos):
    """Counterpart-list sources per arcsec^2 within DENSITY_RADIUS of each position."""
    idx_pos, _, _, _ = deep_coord[o].search_around_sky(pos, DENSITY_RADIUS_ARCSEC * u.arcsec)
    counts = np.bincount(idx_pos, minlength=len(pos))
    return np.maximum(counts, 1) / (math.pi * DENSITY_RADIUS_ARCSEC ** 2)


status = {}
for e in EPOCHS:
    status[e] = classify_positions(e, det[e]["ra"].values, det[e]["dec"].values, det[e]["flux"].values)
for e in EPOCHS:
    st = status[e]
    halo = halo_flags(e, det[e]["ra"].values, det[e]["dec"].values)
    st["halo"] = halo & ~st["stationary"].values
    st["blend_fragment"] = (st["blend_fragment"].values | halo) & ~st["stationary"].values
    print(f"  Epoch {e}: {int(st['stationary'].sum())} stationary, {int(st['blend_fragment'].sum())} "
          f"blend fragments, {int((~st['stationary'] & ~st['blend_fragment']).sum())} free (of {len(st)})")

# False-veto rate for genuine movers: a mover's detection sits at an
# essentially random sky position, so classify random positions inside the
# region all three epochs cover, with a typical faint-candidate flux.
rng = np.random.default_rng(42)
ra_lo, ra_hi = np.percentile(det["A"]["ra"], [1, 99])
dec_lo, dec_hi = np.percentile(det["A"]["dec"], [1, 99])
probe_ra = rng.uniform(ra_lo, ra_hi, N_RANDOM_PROBES * 3)
probe_dec = np.degrees(np.arcsin(rng.uniform(np.sin(np.radians(dec_lo)), np.sin(np.radians(dec_hi)),
                                             N_RANDOM_PROBES * 3)))
in_all = covers("A", probe_ra, probe_dec) & covers("C", probe_ra, probe_dec) & covers("B", probe_ra, probe_dec)
probe_ra, probe_dec = probe_ra[in_all][:N_RANDOM_PROBES], probe_dec[in_all][:N_RANDOM_PROBES]
probe_flux = np.full(len(probe_ra), float(np.median(det["A"]["flux"])))
probe_rates = {}
for e in EPOCHS:
    pc = classify_positions(e, probe_ra, probe_dec, probe_flux)
    probe_halo = halo_flags(e, probe_ra, probe_dec, model_detection=True)
    pc["blend_fragment"] = (pc["blend_fragment"].values | probe_halo) & ~pc["stationary"].values
    probe_rates[e] = {"stationary": float(pc["stationary"].mean()), "blend": float(pc["blend_fragment"].mean())}
p_s = float(np.mean([v["stationary"] for v in probe_rates.values()]))
p_b = float(np.mean([v["blend"] for v in probe_rates.values()]))
# track veto for a mover whose 3 detections are independent random positions:
# vetoed if >= 1 stationary, or >= 2 of (stationary or blend)
p_free = 1 - p_s - p_b
p_mover_vetoed = 1 - (p_free ** 3 + 3 * p_b * p_free ** 2)
print(f"  random-position rates: stationary {p_s:.4f}, blend {p_b:.4f} per detection "
      f"-> a genuine mover is vetoed with probability {p_mover_vetoed:.3f} ({len(probe_ra)} probes)")


CLASS_NAMES = np.array(["FREE", "BLEND_FRAGMENT", "STATIONARY"])


def class_codes(e):
    st = status[e]
    return np.where(st["stationary"], 2, np.where(st["blend_fragment"], 1, 0))


print("\n5/7 Linking A -> C -> B and applying the veto")

coord_a, coord_c, coord_b = det_coord["A"], det_coord["C"], det_coord["B"]
idx_a, idx_b, sep_ab, _ = coord_b.search_around_sky(coord_a, MAX_TOTAL_MOTION * u.arcsec)
print("Possible A-B pairs:", len(idx_a))

# motion window + A/B flux consistency (vectorised)
total = sep_ab.arcsec
fa, fb = A["flux"].values[idx_a], B["flux"].values[idx_b]
keep = (total >= MIN_TOTAL_MOTION) & (fb / fa >= MIN_FLUX_RATIO) & (fb / fa <= MAX_FLUX_RATIO)
idx_a, idx_b, total, fa, fb = idx_a[keep], idx_b[keep], total[keep], fa[keep], fb[keep]

# constant-velocity C prediction and nearest C source
ra_pred = A["ra"].values[idx_a] + fraction * (B["ra"].values[idx_b] - A["ra"].values[idx_a])
dec_pred = A["dec"].values[idx_a] + fraction * (B["dec"].values[idx_b] - A["dec"].values[idx_a])
idx_c, sep_c, _ = SkyCoord(ra_pred * u.deg, dec_pred * u.deg).match_to_catalog_sky(coord_c)
err_c = sep_c.arcsec
fc = C["flux"].values[idx_c]

# uncertainty-aware C gate: 3-sigma astrometry (+) nonlinearity allowance
s_a, s_b, s_c = sigma_det(fa), sigma_det(fb), sigma_det(fc)
s_reg_c = max(registration[("A", "C")]["sigma_reg"], registration[("C", "B")]["sigma_reg"])
s_c_total2 = ((1 - fraction) * s_a) ** 2 + (fraction * s_b) ** 2 + s_c ** 2 + s_reg_c ** 2
c_gate = np.sqrt(CHI2_GATE * s_c_total2 + (NONLINEAR_FRACTION * total) ** 2)
passes_new_c = err_c <= c_gate
passes_fixed_c = err_c <= OLD_C_POSITION_TOLERANCE
keep = (passes_new_c | passes_fixed_c) \
    & (fc / fa >= MIN_FLUX_RATIO) & (fc / fa <= MAX_FLUX_RATIO) \
    & (fb / fc >= MIN_FLUX_RATIO) & (fb / fc <= MAX_FLUX_RATIO)
print("Tracks passing motion, flux and C-position tests:", int(keep.sum()))

reg_ab = registration[("A", "B")]
code = {"A": class_codes("A"), "C": class_codes("C"), "B": class_codes("B")}
candidates = []
rejected = []
reason_counts = {"STATIONARY_SOURCE": 0, "BLEND_MISLINK": 0, "INCONSISTENT_TRAJECTORY": 0}

for k in np.where(keep)[0]:
    ia, ib, ic = int(idx_a[k]), int(idx_b[k]), int(idx_c[k])
    classes = {"A": CLASS_NAMES[code["A"][ia]], "C": CLASS_NAMES[code["C"][ic]], "B": CLASS_NAMES[code["B"][ib]]}
    n_stat = sum(v == "STATIONARY" for v in classes.values())
    n_blend = sum(v == "BLEND_FRAGMENT" for v in classes.values())
    motion_chi2 = total[k] ** 2 / (s_a[k] ** 2 + s_b[k] ** 2 + reg_ab["sigma_reg"] ** 2)

    reason, detail = None, ""
    if motion_chi2 <= CHI2_GATE:
        reason = "STATIONARY_SOURCE"
        detail = (f"A->B displacement {total[k]:.2f}\" is not significant "
                  f"(chi2 {motion_chi2:.1f} <= {CHI2_GATE})")
    elif n_stat >= 2:
        reason = "STATIONARY_SOURCE"
        detail = (f"{n_stat} of 3 detections are stationary sources present at the same sky "
                  f"position in other epochs")
    elif n_stat == 1 or n_stat + n_blend >= 2:
        reason = "BLEND_MISLINK"
        detail = (f"{n_stat} stationary + {n_blend} blend-fragment detection(s): the path is built "
                  f"from detections around persistent sources")
    elif not passes_new_c[k]:
        reason = "INCONSISTENT_TRAJECTORY"
        detail = (f"C detection {err_c[k]:.2f}\" from the constant-velocity prediction; "
                  f"allowed {c_gate[k]:.2f}\" (3-sigma astrometry + {NONLINEAR_FRACTION:.0%} of arc)")

    row = {
        "A_source": int(A["id"].values[ia]),
        "C_source": int(C["id"].values[ic]),
        "B_source": int(B["id"].values[ib]),
        "A_ra": float(A["ra"].values[ia]), "A_dec": float(A["dec"].values[ia]),
        "C_ra": float(C["ra"].values[ic]), "C_dec": float(C["dec"].values[ic]),
        "B_ra": float(B["ra"].values[ib]), "B_dec": float(B["dec"].values[ib]),
        "total_motion_arcsec": float(total[k]),
        "motion_arcsec_per_day": float(total[k] / dt_ab),
        "C_prediction_error_arcsec": float(err_c[k]),
        "C_gate_arcsec": float(c_gate[k]),
        "motion_significance_chi2": float(motion_chi2),
        "flux_A": float(fa[k]), "flux_C": float(fc[k]), "flux_B": float(fb[k]),
        "A_class": classes["A"], "C_class": classes["C"], "B_class": classes["B"],
        "A_counterpart_epochs": status["A"]["counterpart_epochs"].iloc[ia],
        "C_counterpart_epochs": status["C"]["counterpart_epochs"].iloc[ic],
        "B_counterpart_epochs": status["B"]["counterpart_epochs"].iloc[ib],
        "passes_fixed_4arcsec_C_gate": bool(passes_fixed_c[k]),
    }

    if reason is None:
        candidates.append(row)
    else:
        reason_counts[reason] += 1
        rejected.append({**row, "rejection_reason": reason, "rejection_detail": detail})


result = pd.DataFrame(candidates)
rejected_df = pd.DataFrame(rejected)


print("\n6/7 Saving results")

candidate_cols = [
    "candidate_id", "A_source", "C_source", "B_source", "A_ra", "A_dec", "C_ra", "C_dec",
    "B_ra", "B_dec", "total_motion_arcsec", "motion_arcsec_per_day", "C_prediction_error_arcsec",
    "flux_A", "flux_C", "flux_B", "C_gate_arcsec", "motion_significance_chi2",
    "A_class", "C_class", "B_class",
]

if len(result) > 0:
    result = result.sort_values(["C_prediction_error_arcsec", "total_motion_arcsec"],
                                ascending=[True, False])
    result.insert(0, "candidate_id", [f"3EPOCH-{i:03d}" for i in range(1, len(result) + 1)])
    result = result[candidate_cols]
else:
    result = pd.DataFrame(columns=candidate_cols)

# written even when empty, so no stale candidate list is left behind
result.to_csv(CANDIDATES_CSV, index=False)

pd.concat([
    det[e].assign(epoch=e, stationary=status[e]["stationary"].values,
                  blend_fragment=status[e]["blend_fragment"].values)
    [["epoch", "id", "ra", "dec", "x", "y", "flux", "stationary", "blend_fragment"]]
    for e in EPOCHS
]).to_csv(DETECTIONS_CSV, index=False)

if len(rejected_df) > 0:
    rejected_df = rejected_df.sort_values(["rejection_reason", "C_prediction_error_arcsec"])
    rejected_df.insert(0, "track_id", [f"REJ-{i:04d}" for i in range(1, len(rejected_df) + 1)])
rejected_df.to_csv(REJECTED_CSV, index=False)

calibration = {
    "detection_sigma": DETECTION_SIGMA,
    "counterpart_sigma": COUNTERPART_SIGMA,
    "chi2_gate": CHI2_GATE,
    "nonlinear_fraction": NONLINEAR_FRACTION,
    "p_chance_max": P_CHANCE_MAX,
    "psf_fwhm_arcsec": psf_fwhm,
    "blend_radius_arcsec": BLEND_RADIUS,
    "false_veto_rate": {"per_epoch_random_positions": probe_rates,
                        "genuine_mover_track_vetoed_probability": p_mover_vetoed,
                        "n_probes": int(len(probe_ra))},
    "registration": {f"{k[0]}-{k[1]}": v for k, v in registration.items() if EPOCHS.index(k[0]) < EPOCHS.index(k[1])},
    "sigma_det_by_flux": sigma_table,
    "source_counts": {e: {"detected": len(det[e]), "counterpart_list": len(deep[e]),
                          "stationary": int(status[e]["stationary"].sum()),
                          "blend_fragment": int(status[e]["blend_fragment"].sum())} for e in EPOCHS},
    "tracks": {
        "accepted": int(len(result)),
        "rejected": reason_counts,
    },
    "mjd": mjd,
}
with open(CALIBRATION_JSON, "w", encoding="utf-8") as f:
    json.dump(calibration, f, indent=2, default=float)


print("\n7/7 Summary")
print()
print("==============================")
print("THREE-EPOCH MOTION RESULTS")
print("==============================")
print("Candidates:", len(result))
print("Rejected tracks:", len(rejected_df), reason_counts)

if len(result) > 0:
    print()
    print(result[["candidate_id", "total_motion_arcsec", "motion_arcsec_per_day",
                  "C_prediction_error_arcsec", "A_class", "C_class", "B_class"]].head(20).to_string(index=False))
    print()
    print("Created:", CANDIDATES_CSV)
else:
    print("No three-epoch motion candidate passed the linker and the stationary-source veto.")

print("Created:", REJECTED_CSV, "and", CALIBRATION_JSON)
