"""
Catalogue classification v3 for the validated three-epoch motion
candidates: epoch-propagated, uncertainty-aware cross-match.

Replaces the v2 decision logic (catalogue_crossmatch_v2.py), which
  - compared Gaia DR3 / SIMBAD positions as if static (no proper-motion
    propagation to the SPHEREx epochs),
  - used fixed 4"/8" radii with no positional uncertainties,
  - and set EVERY candidate to UNCERTAIN whenever SkyBoT/MPC were
    unreachable, even though Gaia placed a catalogued star on every
    detection.

Does NOT redo source detection, linking, or validation: it reads
validated_three_epoch_candidates.csv as-is, and reads (never writes) the
three original FITS files for epoch times and forced photometry.

Pipeline
  1. Epoch times from the FITS headers (MJD-OBS).
  2. Astrometric calibration: SPHEREx per-axis centroid error sigma_obs is
     fitted (Rayleigh + uniform-background mixture, by flux bin) from this
     project's own persistent A<->B sources (source_matches.csv) against
     Gaia DR3 propagated to each epoch. Same sample calibrates SPHEREx
     aperture flux vs Gaia G.
  3. Per candidate x epoch:
       Gaia DR3  -- every source within 60" propagated from J2016.0 to the
                    epoch with its own proper motion; per-source sigma_cat
                    from position + PM errors x dt (+ parallax). Match test
                    chi2 = sep^2 / (sigma_obs^2 + sigma_cat^2), 2 dof.
                    Local Gaia density -> chance-coincidence probability.
       SIMBAD    -- propagated from J2000 where PM is given.
       Small bodies -- JPL Small-Body Identification API (sb_ident; all
                    numbered/unnumbered asteroids + comets, MPC orbits) for
                    the full field at each epoch, refined with JPL Horizons
                    ephemerides from the SPHEREx spacecraft itself
                    (Horizons id -163182) at the exact epoch.
       Major planets + Pluto -- JPL Horizons.
       SkyBoT / MPC Checker -- connectivity recorded; NOT required, since
                    sb_ident performs the equivalent MPC-orbit search.
  4. Multi-epoch persistence: forced aperture photometry (same r=3 px
     aperture as the detection pipeline) at each epoch's candidate position
     in all three images. A static source detected at P_A should still be
     present at P_A in epochs C and B.
  5. Candidate status (see classify()).

UNMATCHED_AFTER_CHECKS never means "new planet", "Planet X", a discovery,
or a previously unknown object -- only that no catalogue association
survived these specific checks.

    python catalogue_crossmatch_v3.py            # uses cached queries
    python catalogue_crossmatch_v3.py --refresh  # re-query everything
"""

import json
import math
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from astropy.coordinates import SkyCoord
from astropy.io import fits
from astropy.stats import sigma_clipped_stats
from astropy.table import Table
from astropy.time import Time
from astropy.wcs import WCS
import astropy.units as u
from photutils.aperture import CircularAnnulus, CircularAperture, aperture_photometry

warnings.filterwarnings("ignore")

BASE = Path(__file__).resolve().parent
CACHE = BASE / "data" / "catalogue_v3"
CACHE.mkdir(parents=True, exist_ok=True)
REFRESH = "--refresh" in sys.argv

FILES = {
    "A": BASE / "level2_2025W19_2B_0166_3D3_spx_l2b-v20-2025-247.fits",
    "C": BASE / "level2_2025W22_1B_0226_1D3_spx_l2b-v20-2025-250.fits",
    "B": BASE / "level2_2025W24_1A_0099_1D3_spx_l2b-v20-2025-252.fits",
}
EPOCHS = ["A", "C", "B"]
VALIDATED_CSV = BASE / "validated_three_epoch_candidates.csv"
SOURCE_MATCHES_CSV = BASE / "source_matches.csv"
DETECTIONS_CSV = BASE / "three_epoch_detections.csv"
DETAIL_CSV = BASE / "catalogue_crossmatch_results.csv"
COMBINED_CSV = BASE / "validated_candidates_with_catalogue.csv"
SPHEREX_HORIZONS_ID = "-163182"

# --- decision constants (all explicit) -------------------------------------
GAIA_CONE_ARCSEC = 60.0        # for candidates AND local density
SIMBAD_CONE_ARCSEC = 15.0
CHI2_ACCEPT = 13.816           # chi2(2 dof) 99.9%: position consistent
PM_ALLOWANCE_MAS_YR = 20.0     # per axis, when Gaia has no PM (2-param solution)
P_CHANCE_SECURE = 0.05         # per-epoch chance-coincidence ceiling
JOINT_P_CHANCE_KNOWN = 1e-3    # all-epoch chance ceiling for KNOWN_OBJECT
JOINT_P_CHANCE_HIGH = 1e-5
MAG_OUTLIER_NSIGMA = 3.0       # SPHEREx flux vs Gaia G consistency
PERSIST_SNR = 3.0              # forced-photometry detection at another epoch
SSO_NEAR_DEG = 0.5             # sb_ident objects refined with Horizons
APERTURE_R = 3.0               # px, same as three_epoch_compare.py
MIN_GOOD_APERTURE_FRAC = 0.6   # forced photometry needs this many unflagged pixels
BAD_FLAG_BITS = (0, 1, 2, 4, 5, 6, 9, 10, 11, 15, 17, 19)
BAD_FLAG_MASK = sum(1 << b for b in BAD_FLAG_BITS)

GAIA_EPOCH_JYEAR = 2016.0
SIMBAD_EPOCH_JYEAR = 2000.0


def jyear(mjd: float) -> float:
    return 2000.0 + (mjd - 51544.5) / 365.25


def retry(fn, *args, tries=3, delay=3.0, **kw):
    last = None
    for i in range(tries):
        try:
            return fn(*args, **kw)
        except Exception as exc:  # noqa: BLE001
            last = exc
            if i < tries - 1:
                time.sleep(delay)
    raise last


def cached_table(name: str, fetch):
    path = CACHE / f"{name}.ecsv"
    if path.exists() and not REFRESH:
        return Table.read(path, format="ascii.ecsv")
    table = fetch()
    table.write(path, format="ascii.ecsv", overwrite=True)
    return table


def cached_json(name: str, fetch):
    path = CACHE / f"{name}.json"
    if path.exists() and not REFRESH:
        return json.loads(path.read_text(encoding="utf-8"))
    data = fetch()
    path.write_text(json.dumps(data), encoding="utf-8")
    return data


# ---------------------------------------------------------------------------
# Catalogue queries
# ---------------------------------------------------------------------------

GAIA_COLS = (
    "source_id, ra, dec, ra_error, dec_error, pmra, pmdec, pmra_error, "
    "pmdec_error, parallax, parallax_error, phot_g_mean_mag, "
    "astrometric_params_solved, ruwe"
)


def gaia_cone(ra: float, dec: float, radius_arcsec: float) -> Table:
    from astroquery.gaia import Gaia

    Gaia.ROW_LIMIT = -1
    adql = (
        f"SELECT {GAIA_COLS} FROM gaiadr3.gaia_source WHERE 1=CONTAINS("
        f"POINT('ICRS', ra, dec), CIRCLE('ICRS', {ra}, {dec}, {radius_arcsec / 3600.0}))"
    )
    table = retry(lambda: Gaia.launch_job(adql).get_results())
    return Table(table, masked=True)


def simbad_cone(ra: float, dec: float, radius_arcsec: float) -> Table:
    from astroquery.simbad import Simbad

    s = Simbad()
    s.add_votable_fields("otype", "pmra", "pmdec", "coo_err_maj")
    t = retry(s.query_region, SkyCoord(ra * u.deg, dec * u.deg), radius=radius_arcsec * u.arcsec)
    if t is None or len(t) == 0:
        return Table(names=["main_id", "ra", "dec", "otype", "pmra", "pmdec", "coo_err_maj"],
                     dtype=[str, float, float, str, float, float, float])
    keep = [c for c in ["main_id", "ra", "dec", "otype", "pmra", "pmdec", "coo_err_maj"] if c in t.colnames]
    return Table(t[keep], masked=True)


def val(row, col, default=np.nan):
    try:
        v = row[col]
    except (KeyError, IndexError):
        return default
    if np.ma.is_masked(v):
        return default
    try:
        f = float(v)
    except (TypeError, ValueError):
        return default
    return default if not math.isfinite(f) else f


def propagate_gaia(table: Table, t_jyear: float) -> pd.DataFrame:
    """Gaia DR3 sources -> positions at t_jyear with per-source 1-sigma
    per-axis positional uncertainty (arcsec)."""
    dt = t_jyear - GAIA_EPOCH_JYEAR
    rows = []
    for r in table:
        ra, dec = val(r, "ra"), val(r, "dec")
        pmra, pmdec = val(r, "pmra"), val(r, "pmdec")
        has_pm = math.isfinite(pmra) and math.isfinite(pmdec)
        pos_err = math.sqrt((val(r, "ra_error", 1.0) ** 2 + val(r, "dec_error", 1.0) ** 2) / 2)
        if has_pm:
            pm_err = math.sqrt((val(r, "pmra_error", 1.0) ** 2 + val(r, "pmdec_error", 1.0) ** 2) / 2)
            ra_t = ra + (pmra * dt / 3.6e6) / math.cos(math.radians(dec))
            dec_t = dec + pmdec * dt / 3.6e6
        else:
            pm_err = PM_ALLOWANCE_MAS_YR
            ra_t, dec_t = ra, dec
        plx = max(val(r, "parallax", 0.0), 0.0)
        sigma_cat_mas = math.sqrt(pos_err ** 2 + (pm_err * dt) ** 2 + (plx / 2) ** 2)
        rows.append({
            "source_id": int(r["source_id"]),
            "ra_ref": ra, "dec_ref": dec,
            "ra": ra_t, "dec": dec_t,
            "pmra": pmra if has_pm else np.nan,
            "pmdec": pmdec if has_pm else np.nan,
            "has_pm": has_pm,
            "sigma_cat": sigma_cat_mas / 1000.0,
            "gmag": val(r, "phot_g_mean_mag"),
            "ruwe": val(r, "ruwe"),
        })
    return pd.DataFrame(rows)


def sep_arcsec(ra1, dec1, ra2, dec2):
    c1 = SkyCoord(np.atleast_1d(ra1) * u.deg, np.atleast_1d(dec1) * u.deg)
    c2 = SkyCoord(np.atleast_1d(ra2) * u.deg, np.atleast_1d(dec2) * u.deg)
    return c1.separation(c2).arcsec


def position_angle_deg(ra1, dec1, ra2, dec2) -> float:
    c1 = SkyCoord(ra1 * u.deg, dec1 * u.deg)
    c2 = SkyCoord(ra2 * u.deg, dec2 * u.deg)
    return float(c1.position_angle(c2).deg) % 360.0


# ---------------------------------------------------------------------------
# 1. Inputs
# ---------------------------------------------------------------------------

print("1/7 Inputs")
cands = pd.read_csv(VALIDATED_CSV)
headers = {e: fits.getheader(p, "IMAGE") for e, p in FILES.items()}
mjd = {e: float(h["MJD-OBS"]) for e, h in headers.items()}
tyear = {e: jyear(m) for e, m in mjd.items()}
jd = {e: Time(m, format="mjd", scale="utc").jd for e, m in mjd.items()}
print("  candidates:", len(cands), " epochs (MJD):", mjd)

images, wcss = {}, {}
for e, p in FILES.items():
    with fits.open(p) as hdul:
        img = hdul["IMAGE"].data.astype(float)
        # pixel-quality bits from the FLAGS header (MP_*): transient, overflow,
        # SUR error, phantom, reference, non-functional, missing data, hot,
        # cold, nonlinear, persistence, outlier -> treated as invalid
        flags = hdul["FLAGS"].data.astype(np.int64)
        img[(flags & BAD_FLAG_MASK) != 0] = np.nan
        images[e] = img
        wcss[e] = WCS(hdul["IMAGE"].header)

services = {}  # name -> {"ok": bool, "error": str|None, "required": bool}


# ---------------------------------------------------------------------------
# 2. Astrometric + photometric calibration against Gaia
# ---------------------------------------------------------------------------

print("2/7 Calibration of SPHEREx astrometric error and flux-vs-G")
# calibration sample: sources the linker classified as STATIONARY (present at
# the same position in other epochs), from three_epoch_detections.csv;
# falls back to the older A<->B source_matches.csv if that file is absent
if DETECTIONS_CSV.exists():
    _d = pd.read_csv(DETECTIONS_CSV)
    cal_sources = _d[_d["stationary"] & (_d["flux"] > 0)][["epoch", "ra", "dec", "flux"]]
else:
    _m = pd.read_csv(SOURCE_MATCHES_CSV)
    _m = _m[(_m["flux_a"] > 0) & (_m["flux_b"] > 0)]
    cal_sources = pd.concat([
        pd.DataFrame({"epoch": "A", "ra": _m["ra_a"], "dec": _m["dec_a"], "flux": _m["flux_a"]}),
        pd.DataFrame({"epoch": "B", "ra": _m["ra_b"], "dec": _m["dec_b"], "flux": _m["flux_b"]}),
    ])
cal_centres = [tuple(float(v) for v in wcss["A"].pixel_to_world_values(x, y))
               for x in (500, 1020, 1540) for y in (700, 1340)]
cal_rows = []
try:
    for i, (ra0, dec0) in enumerate(cal_centres):
        g = cached_table(f"gaia_cal_{ra0:.4f}_{dec0:.4f}", lambda: gaia_cone(ra0, dec0, 360.0))
        near = cal_sources[sep_arcsec(cal_sources["ra"].values, cal_sources["dec"].values, ra0, dec0) < 330.0]
        for e_label, inside in near.groupby("epoch"):
            gp = propagate_gaia(g, tyear[e_label])
            gc = SkyCoord(gp["ra"].values * u.deg, gp["dec"].values * u.deg)
            sc = SkyCoord(inside["ra"].values * u.deg, inside["dec"].values * u.deg)
            idx, d2d, _ = sc.match_to_catalog_sky(gc)
            for k in range(len(inside)):
                cal_rows.append({
                    "epoch": e_label, "flux": float(inside["flux"].iloc[k]),
                    "r": float(d2d[k].arcsec), "gmag": float(gp["gmag"].iloc[idx[k]]),
                })
    services["Gaia DR3"] = {"ok": True, "error": None, "required": True}
except Exception as exc:  # noqa: BLE001
    services["Gaia DR3"] = {"ok": False, "error": f"{type(exc).__name__}: {exc}", "required": True}
cal = pd.DataFrame(cal_rows).drop_duplicates()


def fit_sigma(r: np.ndarray, rmax: float = 6.0) -> tuple[float, float]:
    """MLE of Rayleigh(sigma) + uniform-in-area background within rmax."""
    r = r[r < rmax]
    best = (-np.inf, 1.0, 1.0)
    for s in np.linspace(0.1, 3.0, 291):
        ray = (r / s ** 2) * np.exp(-r ** 2 / (2 * s ** 2))
        bkg = 2 * r / rmax ** 2
        for f in np.linspace(0.5, 1.0, 51):
            ll = np.sum(np.log(f * ray + (1 - f) * bkg + 1e-300))
            if ll > best[0]:
                best = (ll, s, f)
    return best[1], best[2]


FLUX_BINS = [(0.0, 3.0), (3.0, 6.0), (6.0, 15.0), (15.0, np.inf)]
sigma_by_bin = []
for lo, hi in FLUX_BINS:
    sub = cal[(cal["flux"] >= lo) & (cal["flux"] < hi)]
    s, f = fit_sigma(sub["r"].values) if len(sub) > 30 else (np.nan, np.nan)
    sigma_by_bin.append({"flux_lo": lo, "flux_hi": hi, "n": int(len(sub)), "sigma_obs": s, "true_frac": f})
sigma_tab = pd.DataFrame(sigma_by_bin)
fallback_sigma = float(np.nanmax(sigma_tab["sigma_obs"]))
print(sigma_tab.to_string(index=False))


def sigma_obs_for(flux: float) -> float:
    for row in sigma_by_bin:
        if row["flux_lo"] <= flux < row["flux_hi"] and math.isfinite(row["sigma_obs"]):
            return float(row["sigma_obs"])
    return fallback_sigma


# flux vs G: m_sx = -2.5 log10(flux) ~ a*G + b, fitted on clean matches
good = cal[(cal["r"] < 1.5) & np.isfinite(cal["gmag"]) & (cal["flux"] > 0)].copy()
good["m_sx"] = -2.5 * np.log10(good["flux"])
a_fit, b_fit = np.polyfit(good["gmag"], good["m_sx"], 1)
for _ in range(3):  # iterative 3-sigma clipping
    resid = good["m_sx"] - (a_fit * good["gmag"] + b_fit)
    mad = 1.4826 * np.median(np.abs(resid - np.median(resid)))
    good = good[np.abs(resid) < 3 * mad]
    a_fit, b_fit = np.polyfit(good["gmag"], good["m_sx"], 1)
resid = good["m_sx"] - (a_fit * good["gmag"] + b_fit)
mag_scatter = float(1.4826 * np.median(np.abs(resid - np.median(resid))))
print(f"  flux-vs-G: m_sx = {a_fit:.3f} G + {b_fit:.3f}, robust scatter {mag_scatter:.3f} mag (n={len(good)})")


def mag_residual(flux: float, gmag: float) -> float:
    if not (flux > 0 and math.isfinite(gmag)):
        return np.nan
    return float(-2.5 * math.log10(flux) - (a_fit * gmag + b_fit))


# ---------------------------------------------------------------------------
# 3. Small bodies (JPL sb_ident full field + Horizons from SPHEREx) & planets
# ---------------------------------------------------------------------------

print("3/7 Solar System bodies")
fields = json.loads((CACHE / "sbident_fields.json").read_text(encoding="utf-8"))
SBIDENT_URL = "https://ssd-api.jpl.nasa.gov/sb_ident.api"
SBIDENT_HW = {"ra": 2.3, "dec": 2.0}   # deg; covers all candidate positions + NEO parallax margin
sso_by_epoch: dict[str, list[dict]] = {}
sb_ok = True
sb_errors = []
for e in EPOCHS:
    try:
        def fetch_sb(e=e):
            params = {
                "mpc-code": "500", "obs-time": fields[e]["time"],
                "fov-ra-center": fields[e]["ra"], "fov-dec-center": fields[e]["dec"],
                "fov-ra-hwidth": SBIDENT_HW["ra"], "fov-dec-hwidth": SBIDENT_HW["dec"],
                "two-pass": "true", "suppress-first-pass": "true",
            }
            resp = requests.get(SBIDENT_URL, params=params, timeout=1500)
            resp.raise_for_status()
            return resp.json()
        data = cached_json(f"sbident_{e}", fetch_sb)
        if data.get("summary", {}).get("fov-ra-hwidth") not in (str(SBIDENT_HW["ra"]), SBIDENT_HW["ra"]):
            raise RuntimeError("cached sb_ident field does not match configured field; run --refresh")
        objs = []
        for rec in data.get("data_second_pass", []):
            c = SkyCoord(rec[1], rec[2].replace("'", " ").replace('"', ""), unit=(u.hourangle, u.deg))
            objs.append({"name": rec[0], "ra": c.ra.deg, "dec": c.dec.deg, "vmag": rec[6]})
        sso_by_epoch[e] = objs
    except Exception as exc:  # noqa: BLE001
        sb_ok = False
        sb_errors.append(f"epoch {e}: {type(exc).__name__}: {exc}")
services["JPL Small-Body Identification (sb_ident)"] = {
    "ok": sb_ok, "error": "; ".join(sb_errors) or None, "required": True}
print("  sb_ident objects per epoch:", {e: len(v) for e, v in sso_by_epoch.items()})


def horizons_from_spherex(target: str) -> dict:
    """Ephemeris of one body seen FROM the SPHEREx spacecraft at the three
    exact epochs (RA/Dec, 3-sigma errors, rates)."""
    from astroquery.jplhorizons import Horizons

    obj = Horizons(id=target, id_type="smallbody", location=f"500@{SPHEREX_HORIZONS_ID}",
                   epochs=[jd[e] for e in EPOCHS])
    eph = retry(obj.ephemerides, quantities="1,3,36")
    out = {}
    for i, e in enumerate(EPOCHS):
        out[e] = {
            "ra": float(eph["RA"][i]), "dec": float(eph["DEC"][i]),
            "ra_3sigma": val(eph[i], "RA_3sigma", np.nan),
            "dec_3sigma": val(eph[i], "DEC_3sigma", np.nan),
            "ra_rate": val(eph[i], "RA_rate"), "dec_rate": val(eph[i], "DEC_rate"),  # "/h
        }
    return out


def sso_designation(name: str) -> str:
    # "313052 (2000 RL52)" -> "313052"; "(2010 HK)" -> "2010 HK"
    name = name.strip()
    if name.startswith("("):
        return name.strip("()")
    return name.split()[0]


sso_ephem: dict[str, dict] = {}
near_names = set()
for e, objs in (sso_by_epoch.items() if len(cands) else []):
    for o in objs:
        d = sep_arcsec(cands[f"{e}_ra"].values, cands[f"{e}_dec"].values, o["ra"], o["dec"]).min() / 3600
        if d < SSO_NEAR_DEG:
            near_names.add(o["name"])
for name in sorted(near_names):
    try:
        sso_ephem[name] = cached_json(f"horizons_sso_{sso_designation(name).replace(' ', '_')}",
                                      lambda n=name: horizons_from_spherex(sso_designation(n)))
    except Exception as exc:  # noqa: BLE001
        services["JPL Small-Body Identification (sb_ident)"]["ok"] = False
        services["JPL Small-Body Identification (sb_ident)"]["error"] = (
            f"Horizons refinement failed for {name}: {type(exc).__name__}: {exc}")
PLANETS = {"Mercury": "199", "Venus": "299", "Mars": "499", "Jupiter": "599", "Saturn": "699",
           "Uranus": "799", "Neptune": "899", "Pluto": "999"}


def fetch_planets():
    from astroquery.jplhorizons import Horizons

    out = {}
    for name, pid in PLANETS.items():
        eph = retry(Horizons(id=pid, id_type="majorbody", location=f"500@{SPHEREX_HORIZONS_ID}",
                             epochs=[jd[e] for e in EPOCHS]).ephemerides, quantities="1")
        out[name] = {e: [float(eph["RA"][i]), float(eph["DEC"][i])] for i, e in enumerate(EPOCHS)}
    return out


try:
    planets = cached_json("horizons_planets", fetch_planets)
    services["JPL Horizons (planets)"] = {"ok": True, "error": None, "required": True}
except Exception as exc:  # noqa: BLE001
    planets = {}
    services["JPL Horizons (planets)"] = {"ok": False, "error": f"{type(exc).__name__}: {exc}", "required": True}


def probe(url: str) -> str | None:
    try:
        requests.head(url, timeout=15)
        return None
    except Exception as exc:  # noqa: BLE001
        return f"{type(exc).__name__}"


for name, url in (("SkyBoT (IMCCE)", "https://ssp.imcce.fr/webservices/skybot/"),
                  ("MPC Checker", "https://minorplanetcenter.net/cgi-bin/checkmp.cgi")):
    err = probe(url)
    services[name] = {"ok": err is None, "error": err, "required": False}


# ---------------------------------------------------------------------------
# 4. Per candidate x epoch catalogue association
# ---------------------------------------------------------------------------

print("4/7 Per-epoch association (Gaia DR3 propagated, SIMBAD, small bodies, planets)")
detail_rows = []
epoch_assoc: dict[tuple[str, str], dict] = {}
simbad_ok = True
simbad_err = None

for _, cand in cands.iterrows():
    cid = cand["candidate_id"]
    for e in EPOCHS:
        ra, dec = float(cand[f"{e}_ra"]), float(cand[f"{e}_dec"])
        flux = float(cand[f"flux_{e}"])
        s_obs = sigma_obs_for(flux)
        base = {"candidate_id": cid, "epoch": e, "mjd": mjd[e], "candidate_ra": ra, "candidate_dec": dec,
                "sigma_obs_arcsec": s_obs}

        # --- Gaia DR3 ---
        assoc = {"status": "NO_DATA", "n_consistent": 0}
        try:
            g = cached_table(f"gaia_{ra:.5f}_{dec:.5f}", lambda: gaia_cone(ra, dec, GAIA_CONE_ARCSEC))
            gp = propagate_gaia(g, tyear[e])
            density = len(gp) / (math.pi * GAIA_CONE_ARCSEC ** 2)  # per arcsec^2
            if len(gp):
                gp["sep"] = sep_arcsec(gp["ra"].values, gp["dec"].values, ra, dec)
                gp["sigma_tot"] = np.sqrt(s_obs ** 2 + gp["sigma_cat"] ** 2)
                gp["chi2"] = (gp["sep"] / gp["sigma_tot"]) ** 2
                gp = gp.sort_values("chi2")
                consistent = gp[gp["chi2"] <= CHI2_ACCEPT]
            else:
                consistent = gp
            best = gp.iloc[0] if len(gp) else None
            p_chance = (1 - math.exp(-math.pi * density * float(best["sep"]) ** 2)) if best is not None else np.nan
            mres = mag_residual(flux, float(best["gmag"])) if best is not None else np.nan
            mag_ok = (not math.isfinite(mres)) or abs(mres) <= MAG_OUTLIER_NSIGMA * mag_scatter
            assoc = {
                "status": "OK",
                "n_consistent": int(len(consistent)),
                "density_per_arcmin2": density * 3600,
                "best": None if best is None else {
                    "name": f"Gaia DR3 {int(best['source_id'])}",
                    "source_id": int(best["source_id"]),
                    "sep": float(best["sep"]), "chi2": float(best["chi2"]),
                    "sigma_tot": float(best["sigma_tot"]), "sigma_cat": float(best["sigma_cat"]),
                    "ra_exp": float(best["ra"]), "dec_exp": float(best["dec"]),
                    "pmra": float(best["pmra"]), "pmdec": float(best["pmdec"]),
                    "has_pm": bool(best["has_pm"]), "gmag": float(best["gmag"]),
                    "consistent": bool(best["chi2"] <= CHI2_ACCEPT),
                    "p_chance": p_chance, "mag_resid": mres, "mag_ok": bool(mag_ok),
                },
            }
            b = assoc["best"]
            if b is None:
                detail_rows.append({**base, "catalogue": "Gaia DR3", "matched_object": "", "object_type": "",
                                    "matched_ra": np.nan, "matched_dec": np.nan, "separation_arcsec": np.nan,
                                    "match_status": "NO_MATCH",
                                    "notes": f"No Gaia DR3 source within {GAIA_CONE_ARCSEC:.0f}\""})
            else:
                detail_rows.append({
                    **base, "catalogue": "Gaia DR3", "matched_object": b["name"],
                    "object_type": "star (Gaia DR3 point source)",
                    "matched_ra": b["ra_exp"], "matched_dec": b["dec_exp"], "separation_arcsec": b["sep"],
                    "match_status": "MATCH" if b["consistent"] else "NO_MATCH",
                    "expected_ra_at_epoch": b["ra_exp"], "expected_dec_at_epoch": b["dec_exp"],
                    "sigma_cat_arcsec": b["sigma_cat"], "sigma_total_arcsec": b["sigma_tot"],
                    "chi2": b["chi2"], "n_consistent_sources": assoc["n_consistent"],
                    "p_chance": b["p_chance"], "pmra_mas_yr": b["pmra"], "pmdec_mas_yr": b["pmdec"],
                    "gaia_g_mag": b["gmag"], "mag_residual": b["mag_resid"],
                    "notes": (
                        f"Propagated J2016.0 -> J{tyear[e]:.3f} "
                        f"({'catalogue PM' if b['has_pm'] else f'no PM; +/-{PM_ALLOWANCE_MAS_YR:.0f} mas/yr allowance'}); "
                        f"chi2={b['chi2']:.2f} (accept <= {CHI2_ACCEPT}); "
                        f"{assoc['n_consistent']} consistent source(s); "
                        f"local density {assoc['density_per_arcmin2']:.1f}/arcmin^2; "
                        f"P_chance={b['p_chance']:.4f}; "
                        f"flux-vs-G residual {b['mag_resid']:+.2f} mag (scatter {mag_scatter:.2f})"
                    ),
                })
        except Exception as exc:  # noqa: BLE001
            services["Gaia DR3"] = {"ok": False, "error": f"{type(exc).__name__}: {exc}", "required": True}
            detail_rows.append({**base, "catalogue": "Gaia DR3", "matched_object": "", "object_type": "",
                                "matched_ra": np.nan, "matched_dec": np.nan, "separation_arcsec": np.nan,
                                "match_status": "SERVICE_UNAVAILABLE", "notes": f"{type(exc).__name__}: {exc}"})
        epoch_assoc[(cid, e)] = {"gaia": assoc, "flux": flux, "sigma_obs": s_obs}

        # --- SIMBAD (supporting) ---
        try:
            st = cached_table(f"simbad_{ra:.5f}_{dec:.5f}", lambda: simbad_cone(ra, dec, SIMBAD_CONE_ARCSEC))
            best_s = None
            for r in st:
                sra, sdec = val(r, "ra"), val(r, "dec")
                pmra, pmdec = val(r, "pmra", 0.0), val(r, "pmdec", 0.0)
                dt = tyear[e] - SIMBAD_EPOCH_JYEAR
                sra += pmra * dt / 3.6e6 / math.cos(math.radians(sdec))
                sdec += pmdec * dt / 3.6e6
                err = val(r, "coo_err_maj", 100.0) / 1000.0
                sep = float(sep_arcsec(sra, sdec, ra, dec)[0])
                chi2 = sep ** 2 / (s_obs ** 2 + err ** 2)
                if best_s is None or chi2 < best_s["chi2"]:
                    best_s = {"name": str(r["main_id"]), "type": str(r["otype"]) if "otype" in st.colnames else "",
                              "ra": sra, "dec": sdec, "sep": sep, "chi2": chi2}
            epoch_assoc[(cid, e)]["simbad"] = best_s
            detail_rows.append({
                **base, "catalogue": "SIMBAD",
                "matched_object": best_s["name"] if best_s else "", "object_type": best_s["type"] if best_s else "",
                "matched_ra": best_s["ra"] if best_s else np.nan, "matched_dec": best_s["dec"] if best_s else np.nan,
                "separation_arcsec": best_s["sep"] if best_s else np.nan,
                "match_status": "MATCH" if best_s and best_s["chi2"] <= CHI2_ACCEPT else "NO_MATCH",
                "expected_ra_at_epoch": best_s["ra"] if best_s else np.nan,
                "expected_dec_at_epoch": best_s["dec"] if best_s else np.nan,
                "chi2": best_s["chi2"] if best_s else np.nan,
                "notes": ("PM-propagated from J2000 where SIMBAD gives PM; " if best_s else "")
                         + f"cone {SIMBAD_CONE_ARCSEC:.0f}\"",
            })
        except Exception as exc:  # noqa: BLE001
            simbad_ok, simbad_err = False, f"{type(exc).__name__}: {exc}"
            epoch_assoc[(cid, e)]["simbad"] = None
            detail_rows.append({**base, "catalogue": "SIMBAD", "matched_object": "", "object_type": "",
                                "matched_ra": np.nan, "matched_dec": np.nan, "separation_arcsec": np.nan,
                                "match_status": "SERVICE_UNAVAILABLE", "notes": simbad_err})

        # --- small bodies ---
        best_sso = None
        if e in sso_by_epoch:
            for o in sso_by_epoch[e]:
                eph = sso_ephem.get(o["name"], {}).get(e)
                ora, odec = (eph["ra"], eph["dec"]) if eph else (o["ra"], o["dec"])
                sep = float(sep_arcsec(ora, odec, ra, dec)[0])
                if best_sso is None or sep < best_sso["sep"]:
                    s_eph = (max(val(eph, "ra_3sigma", 0.0), val(eph, "dec_3sigma", 0.0)) / 3.0) if eph else 0.0
                    chi2 = sep ** 2 / (s_obs ** 2 + s_eph ** 2)
                    best_sso = {"name": o["name"], "ra": ora, "dec": odec, "sep": sep, "chi2": chi2,
                                "from_spherex": bool(eph)}
        epoch_assoc[(cid, e)]["sso"] = best_sso
        detail_rows.append({
            **base, "catalogue": "JPL Small-Body Identification (sb_ident)",
            "matched_object": best_sso["name"] if best_sso and best_sso["chi2"] <= CHI2_ACCEPT else "",
            "object_type": "Solar System small body" if best_sso and best_sso["chi2"] <= CHI2_ACCEPT else "",
            "matched_ra": best_sso["ra"] if best_sso else np.nan,
            "matched_dec": best_sso["dec"] if best_sso else np.nan,
            "separation_arcsec": best_sso["sep"] if best_sso else np.nan,
            "match_status": ("SERVICE_UNAVAILABLE" if e not in sso_by_epoch else
                             "MATCH" if best_sso and best_sso["chi2"] <= CHI2_ACCEPT else "NO_MATCH"),
            "expected_ra_at_epoch": best_sso["ra"] if best_sso else np.nan,
            "expected_dec_at_epoch": best_sso["dec"] if best_sso else np.nan,
            "chi2": best_sso["chi2"] if best_sso else np.nan,
            "notes": (
                f"Full-field epoch-aware search of all known asteroids/comets at {fields[e]['time']} UTC; "
                f"{len(sso_by_epoch.get(e, []))} object(s) in field; "
                + (f"nearest {best_sso['name']} at {best_sso['sep'] / 60:.1f}' "
                   f"({'Horizons from SPHEREx' if best_sso['from_spherex'] else 'geocentric'})"
                   if best_sso else "none in field")
            ) if e in sso_by_epoch else "sb_ident unavailable for this epoch",
        })

        # --- planets ---
        if planets:
            pname, psep = min(((n, float(sep_arcsec(p[e][0], p[e][1], ra, dec)[0])) for n, p in planets.items()),
                              key=lambda x: x[1])
            detail_rows.append({**base, "catalogue": "JPL Horizons (planets)", "matched_object": "",
                                "object_type": "", "matched_ra": planets[pname][e][0],
                                "matched_dec": planets[pname][e][1], "separation_arcsec": psep,
                                "match_status": "NO_MATCH" if psep > 600 else "MATCH",
                                "notes": f"8 planets + Pluto from SPHEREx; nearest {pname} at {psep / 3600:.1f} deg"})

        # --- optional services (connectivity only) ---
        for name in ("SkyBoT (IMCCE)", "MPC Checker"):
            detail_rows.append({**base, "catalogue": name, "matched_object": "", "object_type": "",
                                "matched_ra": np.nan, "matched_dec": np.nan, "separation_arcsec": np.nan,
                                "match_status": "SERVICE_UNAVAILABLE" if not services[name]["ok"] else "NO_MATCH",
                                "notes": ("Not required: the equivalent MPC-orbit small-body search was "
                                          "performed with JPL sb_ident. " +
                                          (f"Unreachable this run ({services[name]['error']})."
                                           if not services[name]["ok"] else "Reachable; not queried."))})

services["SIMBAD"] = {"ok": simbad_ok, "error": simbad_err, "required": True}


# ---------------------------------------------------------------------------
# 5. Multi-epoch persistence (forced photometry)
# ---------------------------------------------------------------------------

print("5/7 Forced photometry for multi-epoch persistence")
bkg_std = {}
for e, img in images.items():
    finite = np.isfinite(img)
    _, med, std = sigma_clipped_stats(img[finite], sigma=3.0)
    bkg_std[e] = (med, std)


def forced_snr(image_epoch: str, ra: float, dec: float) -> float:
    img = images[image_epoch]
    x, y = wcss[image_epoch].world_to_pixel_values(ra, dec)
    if not (5 <= x < img.shape[1] - 5 and 5 <= y < img.shape[0] - 5):
        return np.nan
    ap = CircularAperture([(x, y)], r=APERTURE_R)
    ann = CircularAnnulus([(x, y)], r_in=6.0, r_out=10.0)
    ann_vals = ann.to_mask(method="center")[0].get_values(img)
    ann_vals = ann_vals[np.isfinite(ann_vals)]
    ap_vals = ap.to_mask(method="center")[0].get_values(img)
    if len(ann_vals) < 20 or np.isfinite(ap_vals).mean() < MIN_GOOD_APERTURE_FRAC:
        return np.nan  # too many flagged pixels to measure
    _, local_med, local_std = sigma_clipped_stats(ann_vals, sigma=3.0)
    # flagged aperture pixels contribute the local background (zero net flux)
    clean = np.where(np.isfinite(img), img, local_med)
    flux = float(aperture_photometry(clean - local_med, ap)["aperture_sum"][0])
    return flux / (local_std * math.sqrt(ap.area))


persistence = {}
for _, cand in cands.iterrows():
    cid = cand["candidate_id"]
    for e in EPOCHS:
        ra, dec = float(cand[f"{e}_ra"]), float(cand[f"{e}_dec"])
        persistence[(cid, e)] = {img_e: forced_snr(img_e, ra, dec) for img_e in EPOCHS}


# ---------------------------------------------------------------------------
# 6. Candidate classification
# ---------------------------------------------------------------------------

print("6/7 Classification")
required = [n for n, s in services.items() if s["required"]]
required_ok = all(services[n]["ok"] for n in required)


def classify(cand) -> dict:
    cid = cand["candidate_id"]
    reasons = []
    ga = {e: epoch_assoc[(cid, e)]["gaia"] for e in EPOCHS}
    best = {e: ga[e].get("best") for e in EPOCHS}

    # observed motion (A -> B)
    obs_rate = float(cand["motion_arcsec_per_day"])
    obs_pa = position_angle_deg(cand["A_ra"], cand["A_dec"], cand["B_ra"], cand["B_dec"])
    dt_days = mjd["B"] - mjd["A"]

    # --- (a) known small body consistent at >= 2 epochs, with consistent motion
    sso_hits = {e: epoch_assoc[(cid, e)]["sso"] for e in EPOCHS
                if epoch_assoc[(cid, e)]["sso"] and epoch_assoc[(cid, e)]["sso"]["chi2"] <= CHI2_ACCEPT}
    expected_motion = None
    if sso_hits:
        name = next(iter(sso_hits.values()))["name"]
        eph = sso_ephem.get(name)
        if eph:
            exp_rate = float(sep_arcsec(eph["A"]["ra"], eph["A"]["dec"], eph["B"]["ra"], eph["B"]["dec"])[0]) / dt_days
            exp_pa = position_angle_deg(eph["A"]["ra"], eph["A"]["dec"], eph["B"]["ra"], eph["B"]["dec"])
            expected_motion = {"rate": exp_rate, "pa": exp_pa, "source": f"{name} (Horizons from SPHEREx)"}
        same = len({h["name"] for h in sso_hits.values()}) == 1
        sig_rate = math.sqrt(2) * max(epoch_assoc[(cid, e)]["sigma_obs"] for e in EPOCHS) / dt_days
        motion_ok = expected_motion is not None and abs(exp_rate - obs_rate) <= 3 * sig_rate + 0.05 * exp_rate \
            and abs((exp_pa - obs_pa + 180) % 360 - 180) <= 10
        if same and len(sso_hits) >= 2 and motion_ok:
            return dict(status="KNOWN_OBJECT", explanation="KNOWN_SOLAR_SYSTEM_OBJECT", confidence="HIGH",
                        object=name, catalogue="JPL sb_ident + Horizons", expected_motion=expected_motion,
                        obs_rate=obs_rate, obs_pa=obs_pa,
                        reason=f"{name} matches the candidate at epochs {', '.join(sso_hits)} (from the "
                               f"SPHEREx spacecraft position) with consistent rate and direction.")
        reasons.append(f"Possible small-body association ({name}) at {len(sso_hits)} epoch(s) but not "
                       f"consistent in position and motion across epochs.")

    # --- per-epoch Gaia verdicts
    secure = {}
    for e in EPOCHS:
        b = best[e]
        if ga[e]["status"] != "OK" or b is None:
            secure[e] = False
            continue
        secure[e] = (b["consistent"] and ga[e]["n_consistent"] == 1 and b["p_chance"] <= P_CHANCE_SECURE
                     and b["mag_ok"])
    consistent_ids = {e: best[e]["source_id"] for e in EPOCHS if best[e] and best[e]["consistent"]}

    # --- (b) the same Gaia star at >= 2 epochs: the source is not moving
    ids = list(consistent_ids.values())
    repeated = [s for s in set(ids) if ids.count(s) >= 2]
    if repeated:
        sid = repeated[0]
        return dict(status="KNOWN_OBJECT", explanation="STATIC_KNOWN_STAR", confidence="HIGH",
                    object=f"Gaia DR3 {sid}", catalogue="Gaia DR3",
                    expected_motion={"rate": 0.0, "pa": np.nan, "source": "Gaia DR3 proper motion"},
                    obs_rate=obs_rate, obs_pa=obs_pa,
                    reason=f"The same Gaia DR3 star {sid} is consistent with the candidate at "
                           f"{ids.count(sid)} epochs, so the apparent motion is not a real displacement.")

    # --- (c) a high-proper-motion star whose PM reproduces the observed motion
    for e in EPOCHS:
        b = best[e]
        if b and b["consistent"] and b["has_pm"]:
            pm_rate = math.hypot(b["pmra"], b["pmdec"]) / 1000.0 / 365.25  # "/day
            if pm_rate > 0.5 * obs_rate:
                return dict(status="UNCERTAIN", explanation="HIGH_PM_STAR_CANDIDATE", confidence="MEDIUM",
                            object=b["name"], catalogue="Gaia DR3",
                            expected_motion={"rate": pm_rate, "pa": math.degrees(math.atan2(b["pmra"], b["pmdec"])) % 360,
                                             "source": "Gaia DR3 proper motion"},
                            obs_rate=obs_rate, obs_pa=obs_pa,
                            reason="A catalogued high-proper-motion star lies on the track; needs manual review.")

    # expected motion of the catalogued stars themselves (to contrast with observed)
    pm_rates = [math.hypot(best[e]["pmra"], best[e]["pmdec"]) / 1000.0 / 365.25
                for e in EPOCHS if best[e] and best[e]["has_pm"]]
    star_motion = {"rate": max(pm_rates) if pm_rates else np.nan, "pa": np.nan,
                   "source": "largest Gaia DR3 proper motion among the matched stars"}

    # --- persistence: does each epoch's source stay put in the other images?
    persist = {}
    for e in EPOCHS:
        others = [persistence[(cid, e)][o] for o in EPOCHS if o != e]
        persist[e] = any(math.isfinite(s) and s >= PERSIST_SNR for s in others)

    # --- (d) every epoch is a distinct, securely associated catalogued star
    distinct = len(set(consistent_ids.values())) == len(consistent_ids)
    joint_p = float(np.prod([best[e]["p_chance"] for e in EPOCHS if best[e]])) if all(best.values()) else np.nan
    if all(secure.values()) and distinct and joint_p <= JOINT_P_CHANCE_KNOWN:
        n_persist = sum(persist.values())
        if n_persist >= 2:
            conf = "HIGH" if (joint_p <= JOINT_P_CHANCE_HIGH and n_persist == 3) else "MEDIUM"
            names = ", ".join(f"{e}: {best[e]['name']}" for e in EPOCHS)
            return dict(status="KNOWN_OBJECT", explanation="LINKED_KNOWN_STARS", confidence=conf,
                        object=names, catalogue="Gaia DR3", expected_motion=star_motion,
                        obs_rate=obs_rate, obs_pa=obs_pa, joint_p=joint_p,
                        reason=(f"Each epoch's detection coincides with a different Gaia DR3 star at its "
                                f"proper-motion-propagated position (all chi2 <= {CHI2_ACCEPT}, unique, "
                                f"brightness consistent; joint chance probability {joint_p:.1e}). The stars' "
                                f"catalogued motions ({star_motion['rate']:.1e}\"/day) cannot produce the "
                                f"observed {obs_rate:.2f}\"/day, and {n_persist}/3 of these sources are still "
                                f"present at the same position in the other epochs. The apparent motion is "
                                f"explained by linking three unrelated known stars, not by a moving object."))
        reasons.append(f"All epochs match distinct Gaia stars, but only {n_persist}/3 sources persist "
                       f"at their position in the other epochs.")

    # --- anything left is either unmatched or uncertain
    any_assoc = any(best[e] and best[e]["consistent"] for e in EPOCHS) or any(
        epoch_assoc[(cid, e)].get("simbad") and epoch_assoc[(cid, e)]["simbad"]["chi2"] <= CHI2_ACCEPT
        for e in EPOCHS) or bool(sso_hits)
    if not any_assoc and required_ok:
        return dict(status="UNMATCHED_AFTER_CHECKS", explanation="NO_ASSOCIATION", confidence="NONE",
                    object="", catalogue="", expected_motion=None, obs_rate=obs_rate, obs_pa=obs_pa,
                    reason="All required catalogue checks completed at every epoch and none produced a "
                           "positionally consistent association. This is NOT evidence of a new or "
                           "unknown object.")
    if not required_ok:
        failed = [n for n in required if not services[n]["ok"]]
        reasons.append("Required check(s) incomplete: " + ", ".join(failed) + ".")
    for e in EPOCHS:
        b = best[e]
        if not b:
            reasons.append(f"{e}: no Gaia source within {GAIA_CONE_ARCSEC:.0f}\".")
        elif not b["consistent"]:
            reasons.append(f"{e}: nearest Gaia star {b['sep']:.2f}\" away (chi2 {b['chi2']:.1f}) - not consistent.")
        elif ga[e]["n_consistent"] > 1:
            reasons.append(f"{e}: {ga[e]['n_consistent']} Gaia stars are positionally consistent (ambiguous).")
        elif b["p_chance"] > P_CHANCE_SECURE:
            reasons.append(f"{e}: chance-coincidence probability {b['p_chance']:.3f} too high.")
        elif not b["mag_ok"]:
            reasons.append(f"{e}: brightness inconsistent with {b['name']} "
                           f"({b['mag_resid']:+.2f} mag vs {mag_scatter:.2f} scatter).")
    if math.isfinite(joint_p) and joint_p > JOINT_P_CHANCE_KNOWN and all(secure.values()):
        reasons.append(f"Joint chance probability {joint_p:.1e} above {JOINT_P_CHANCE_KNOWN:.0e}.")
    n_persist = sum(persist.values())
    if n_persist == 3:
        reasons.append("Supporting evidence: the source at each epoch's position is still present at "
                       "that same position in the other two epochs (forced photometry), as expected for "
                       "static sources, but the catalogue identification is not secure enough for "
                       "KNOWN_OBJECT.")
    elif n_persist < 3:
        reasons.append(f"Only {n_persist}/3 epoch positions show a persistent source in the other epochs.")
    top = min((best[e] for e in EPOCHS if best[e]), key=lambda b: b["chi2"], default=None)
    return dict(status="UNCERTAIN", explanation="INSUFFICIENT_OR_AMBIGUOUS", confidence="LOW",
                object=top["name"] if top else "", catalogue="Gaia DR3" if top else "",
                expected_motion=star_motion, obs_rate=obs_rate, obs_pa=obs_pa, joint_p=joint_p,
                reason=" ".join(reasons) or "Evidence insufficient for a confident classification.")


summaries = []
for _, cand in cands.iterrows():
    cid = cand["candidate_id"]
    res = classify(cand)
    best = {e: epoch_assoc[(cid, e)]["gaia"].get("best") for e in EPOCHS}
    top_e = min((e for e in EPOCHS if best[e]), key=lambda e: best[e]["chi2"], default=None)
    row = {
        "candidate_id": cid,
        "final_catalogue_status": res["status"],
        "catalogue_explanation": res["explanation"],
        "match_confidence": res["confidence"],
        "best_match_catalogue": res["catalogue"],
        "best_match_object": res["object"],
        "best_match_separation_arcsec": best[top_e]["sep"] if top_e else np.nan,
        "best_match_epoch": top_e or "",
        "observed_rate_arcsec_per_day": res["obs_rate"],
        "observed_pa_deg": res["obs_pa"],
        "expected_rate_arcsec_per_day": (res["expected_motion"] or {}).get("rate", np.nan),
        "expected_pa_deg": (res["expected_motion"] or {}).get("pa", np.nan),
        "expected_motion_source": (res["expected_motion"] or {}).get("source", ""),
        "joint_p_chance": res.get("joint_p", np.nan),
        "catalogues_checked": ";".join(n for n, s in services.items() if s["ok"]),
        "services_succeeded": ";".join(n for n, s in services.items() if s["ok"]),
        "services_failed": ";".join(n for n, s in services.items() if s["required"] and not s["ok"]),
        "optional_services_unavailable": ";".join(n for n, s in services.items()
                                                  if not s["required"] and not s["ok"]),
        "status_reason": res["reason"],
        "catalogue_notes": res["reason"],
    }
    for e in EPOCHS:
        b = best[e]
        row.update({
            f"{e}_match_object": b["name"] if b else "",
            f"{e}_separation_arcsec": b["sep"] if b else np.nan,
            f"{e}_chi2": b["chi2"] if b else np.nan,
            f"{e}_sigma_total_arcsec": b["sigma_tot"] if b else np.nan,
            f"{e}_expected_ra": b["ra_exp"] if b else np.nan,
            f"{e}_expected_dec": b["dec_exp"] if b else np.nan,
            f"{e}_p_chance": b["p_chance"] if b else np.nan,
            f"{e}_n_consistent": epoch_assoc[(cid, e)]["gaia"].get("n_consistent", 0),
            f"{e}_mag_residual": b["mag_resid"] if b else np.nan,
            f"{e}_persist_snr_other_epochs": ";".join(
                f"{o}:{persistence[(cid, e)][o]:.1f}" for o in EPOCHS if o != e),
        })
    summaries.append(row)


# ---------------------------------------------------------------------------
# 7. Write outputs
# ---------------------------------------------------------------------------

print("7/7 Writing outputs")
SUMMARY_COLUMNS = [
    "candidate_id", "final_catalogue_status", "catalogue_explanation", "match_confidence",
    "best_match_catalogue", "best_match_object", "best_match_separation_arcsec", "best_match_epoch",
    "observed_rate_arcsec_per_day", "observed_pa_deg", "expected_rate_arcsec_per_day", "expected_pa_deg",
    "expected_motion_source", "joint_p_chance", "catalogues_checked", "services_succeeded",
    "services_failed", "optional_services_unavailable", "status_reason", "catalogue_notes",
] + [f"{e}_{k}" for e in EPOCHS for k in (
    "match_object", "separation_arcsec", "chi2", "sigma_total_arcsec", "expected_ra", "expected_dec",
    "p_chance", "n_consistent", "mag_residual", "persist_snr_other_epochs")]
DETAIL_COLUMNS = [
    "candidate_id", "epoch", "mjd", "candidate_ra", "candidate_dec", "sigma_obs_arcsec", "catalogue",
    "matched_object", "object_type", "matched_ra", "matched_dec", "separation_arcsec", "match_status",
    "expected_ra_at_epoch", "expected_dec_at_epoch", "sigma_cat_arcsec", "sigma_total_arcsec", "chi2",
    "n_consistent_sources", "p_chance", "pmra_mas_yr", "pmdec_mas_yr", "gaia_g_mag", "mag_residual", "notes",
]
# explicit schema so an empty run still writes complete headers
summary = pd.DataFrame(summaries).reindex(columns=SUMMARY_COLUMNS)
cands["candidate_id"] = cands["candidate_id"].astype(str)
summary["candidate_id"] = summary["candidate_id"].astype(str)
combined = cands.merge(summary, on="candidate_id", how="left")
combined.to_csv(COMBINED_CSV, index=False)
pd.DataFrame(detail_rows).reindex(columns=DETAIL_COLUMNS).to_csv(DETAIL_CSV, index=False)

run_meta = {
    "epochs_mjd": mjd,
    "sigma_obs_by_flux_bin": sigma_by_bin,
    "flux_vs_g": {"a": a_fit, "b": b_fit, "scatter_mag": mag_scatter, "n": int(len(good))},
    "constants": {
        "chi2_accept": CHI2_ACCEPT, "p_chance_secure": P_CHANCE_SECURE,
        "joint_p_chance_known": JOINT_P_CHANCE_KNOWN, "joint_p_chance_high": JOINT_P_CHANCE_HIGH,
        "mag_outlier_nsigma": MAG_OUTLIER_NSIGMA, "persist_snr": PERSIST_SNR,
        "pm_allowance_mas_yr": PM_ALLOWANCE_MAS_YR,
    },
    "services": services,
    "sso_in_field": {e: [o["name"] for o in v] for e, v in sso_by_epoch.items()},
}
(CACHE / "run_metadata.json").write_text(json.dumps(run_meta, indent=2, default=float), encoding="utf-8")

print()
print("Services:", json.dumps(services, indent=1))
print(summary["final_catalogue_status"].value_counts().to_string())
print(summary[["candidate_id", "final_catalogue_status", "catalogue_explanation", "match_confidence",
               "joint_p_chance"]].to_string(index=False))

assert len(combined) == len(cands)
assert set(summary["final_catalogue_status"]) <= {"KNOWN_OBJECT", "UNMATCHED_AFTER_CHECKS", "UNCERTAIN"}
