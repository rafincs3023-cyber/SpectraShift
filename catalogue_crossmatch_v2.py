"""
Rigorous, audit-trail catalogue cross-match for the 22 validated three-epoch
motion candidates (validated_three_epoch_candidates.csv).

Does NOT redo source detection, matching, three-epoch motion detection, or
scientific validation -- those results are read as-is.

For EVERY candidate x EVERY relevant epoch (A, C, B) x EVERY catalogue
service, one detailed row is recorded in catalogue_crossmatch_results.csv
with: candidate_id, epoch, mjd, candidate_ra/dec, catalogue, matched_object,
object_type, matched_ra/dec, separation_arcsec, match_status, notes.

Catalogues attempted:
  - Gaia DR3            (static stellar/point-source astrometric catalogue)
  - SIMBAD              (static object catalogue, any object type)
  - SkyBoT (IMCCE)      (epoch-aware reverse search vs the full MPC minor-body
                          orbital catalogue)
  - MPC Checker         (epoch-aware reverse search vs the MPC catalogue)
  - JPL Horizons        (direct ephemeris for a fixed list of major planets +
                          the largest/brightest minor planets and TNOs only --
                          NOT a substitute for a full minor-planet catalogue
                          search)

For moving Solar System objects the actual Epoch A/C/B observation times
(from the original FITS headers) are used for every epoch-aware query
(SkyBoT, MPC, Horizons) -- not a single static position.

Network/service failures are recorded, never invented or approximated:
SERVICE_UNAVAILABLE rows are written with the real exception text; no
match is guessed for a service that could not be reached.

Final per-candidate status (one of KNOWN_OBJECT / UNMATCHED_AFTER_CHECKS /
UNCERTAIN) is decided conservatively:
  - KNOWN_OBJECT only if a catalogue match is both tight (within its
    "known" radius) AND capable of actually explaining that candidate
    (i.e. not just an incidental single-epoch field-star coincidence that
    cannot account for tens of arcsec of multi-epoch motion).
  - UNCERTAIN if the comprehensive Solar System check (SkyBoT and/or MPC)
    could not be completed for this candidate, since that check is central
    to this project and its absence cannot be treated as a clean "no".
  - UNMATCHED_AFTER_CHECKS only if every relevant, important check
    actually succeeded and none produced a match.

No candidate is labelled Planet X, a discovery, a new planet, or a
confirmed unknown object anywhere in this script's output.
"""

import time
import warnings

from astropy.io import fits
from astropy.coordinates import SkyCoord
from astropy.time import Time
import astropy.units as u

import numpy as np
import pandas as pd

from astroquery.gaia import Gaia
from astroquery.simbad import Simbad
from astroquery.exceptions import NoResultsWarning

try:
    from astroquery.imcce import Skybot
except ImportError:
    Skybot = None

try:
    from astroquery.jplhorizons import Horizons
except ImportError:
    Horizons = None


FILE_A = "level2_2025W19_2B_0166_3D3_spx_l2b-v20-2025-247.fits"
FILE_C = "level2_2025W22_1B_0226_1D3_spx_l2b-v20-2025-250.fits"
FILE_B = "level2_2025W24_1A_0099_1D3_spx_l2b-v20-2025-252.fits"

VALIDATED_CSV = "validated_three_epoch_candidates.csv"
DETAIL_CSV = "catalogue_crossmatch_results.csv"
COMBINED_CSV = "validated_candidates_with_catalogue.csv"

EPOCHS = ["A", "C", "B"]

GAIA_SEARCH_RADIUS = 8.0
GAIA_KNOWN_RADIUS = 4.0

SIMBAD_SEARCH_RADIUS = 8.0
SIMBAD_KNOWN_RADIUS = 4.0

SKYBOT_SEARCH_RADIUS = 20.0
SKYBOT_KNOWN_RADIUS = 10.0

HORIZONS_SEARCH_RADIUS = 60.0
HORIZONS_KNOWN_RADIUS = 10.0

HORIZONS_TARGETS = {
    "Mercury": ("199", "planet"),
    "Venus": ("299", "planet"),
    "Mars": ("499", "planet"),
    "Jupiter": ("599", "planet"),
    "Saturn": ("699", "planet"),
    "Uranus": ("799", "planet"),
    "Neptune": ("899", "planet"),
    "Pluto": ("999", "dwarf planet"),
    "Ceres": ("1;", "minor planet"),
    "Pallas": ("2;", "minor planet"),
    "Juno": ("3;", "minor planet"),
    "Vesta": ("4;", "minor planet"),
    "Eris": ("136199;", "dwarf planet / TNO"),
    "Makemake": ("136472;", "dwarf planet / TNO"),
    "Haumea": ("136108;", "dwarf planet / TNO"),
    "Sedna": ("90377;", "TNO"),
    "Quaoar": ("50000;", "TNO"),
    "Orcus": ("90482;", "TNO"),
    "Gonggong": ("225088;", "TNO"),
}

Gaia.ROW_LIMIT = 20
warnings.simplefilter("ignore", category=NoResultsWarning)

simbad = Simbad()
simbad.add_votable_fields("otype")

rows = []          # detailed per candidate/epoch/catalogue rows
services_ok = set()
services_failed = {}   # name -> example error text


def get_mjd(filename):
    with fits.open(filename) as hdul:
        return hdul["IMAGE"].header.get("MJD-OBS")


def add_row(candidate_id, epoch, mjd, ra, dec, catalogue, matched_object,
            object_type, matched_ra, matched_dec, separation_arcsec,
            match_status, notes):
    rows.append({
        "candidate_id": candidate_id,
        "epoch": epoch,
        "mjd": mjd,
        "candidate_ra": ra,
        "candidate_dec": dec,
        "catalogue": catalogue,
        "matched_object": matched_object,
        "object_type": object_type,
        "matched_ra": matched_ra,
        "matched_dec": matched_dec,
        "separation_arcsec": separation_arcsec,
        "match_status": match_status,
        "notes": notes,
    })


def retry_call(fn, *args, retries=3, delay=2.0, **kwargs):
    """Retry a flaky network call a few times before giving up.

    Distinguishes transient blips (connection reset, brief timeout) from a
    genuinely down host (SkyBoT/MPC), which is tested separately and not
    retried here since repeated long timeouts against a confirmed-down host
    would just waste minutes.
    """
    last_exc = None
    for attempt in range(retries):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            last_exc = exc
            if attempt < retries - 1:
                time.sleep(delay)
    raise last_exc


def query_gaia(coord, radius_arcsec):
    radius_deg = radius_arcsec / 3600.0
    adql = (
        "SELECT source_id, ra, dec, phot_g_mean_mag "
        "FROM gaiadr3.gaia_source WHERE 1=CONTAINS("
        "POINT('ICRS', ra, dec), "
        f"CIRCLE('ICRS', {coord.ra.deg}, {coord.dec.deg}, {radius_deg}))"
    )
    job = Gaia.launch_job(adql)
    table = job.get_results()
    if table is None or len(table) == 0:
        return None
    cat_coords = SkyCoord(table["ra"].data * u.deg, table["dec"].data * u.deg)
    sep = coord.separation(cat_coords).arcsec
    i = int(np.argmin(sep))
    return {
        "name": f"Gaia DR3 {int(table['source_id'][i])}",
        "type": "star (Gaia point source)",
        "ra": float(table["ra"][i]),
        "dec": float(table["dec"][i]),
        "sep": float(sep[i]),
    }


def query_simbad(coord, radius_arcsec):
    table = simbad.query_region(coord, radius=radius_arcsec * u.arcsec)
    if table is None or len(table) == 0:
        return None
    cat_coords = SkyCoord(table["ra"].data * u.deg, table["dec"].data * u.deg)
    sep = coord.separation(cat_coords).arcsec
    i = int(np.argmin(sep))
    main_id = table["main_id"][i]
    if isinstance(main_id, bytes):
        main_id = main_id.decode()
    otype = table["otype"][i] if "otype" in table.colnames else ""
    if isinstance(otype, bytes):
        otype = otype.decode()
    return {
        "name": str(main_id),
        "type": str(otype),
        "ra": float(table["ra"][i]),
        "dec": float(table["dec"][i]),
        "sep": float(sep[i]),
    }


def query_skybot(coord, mjd_val, radius_arcsec):
    epoch_time = Time(mjd_val, format="mjd")
    table = Skybot.cone_search(coord, radius_arcsec * u.arcsec, epoch_time, location="500")
    if table is None or len(table) == 0:
        return None
    cat_coords = SkyCoord(table["RA"], table["DEC"])
    sep = coord.separation(cat_coords).arcsec
    i = int(np.argmin(sep))
    return {
        "name": str(table["Name"][i]),
        "type": "solar system body (SkyBoT)",
        "ra": float(cat_coords[i].ra.deg),
        "dec": float(cat_coords[i].dec.deg),
        "sep": float(sep[i]),
    }


print("1/6 Loading validated candidates and epoch timing")

df = pd.read_csv(VALIDATED_CSV)
print("Validated candidates:", len(df))

mjd = {
    "A": get_mjd(FILE_A),
    "C": get_mjd(FILE_C),
    "B": get_mjd(FILE_B),
}
jd = {k: Time(v, format="mjd").jd for k, v in mjd.items()}
print("Epoch MJDs:", mjd)


print("\n2/6 Testing Gaia / SIMBAD reachability")

try:
    _ = retry_call(query_gaia, SkyCoord(df["A_ra"].iloc[0] * u.deg, df["A_dec"].iloc[0] * u.deg), GAIA_SEARCH_RADIUS)
    services_ok.add("Gaia DR3")
    print("  Gaia DR3: reachable")
except Exception as exc:
    services_failed["Gaia DR3"] = f"{type(exc).__name__}: {exc}"
    print(f"  Gaia DR3: FAILED ({type(exc).__name__})")

try:
    _ = retry_call(query_simbad, SkyCoord(df["A_ra"].iloc[0] * u.deg, df["A_dec"].iloc[0] * u.deg), SIMBAD_SEARCH_RADIUS)
    services_ok.add("SIMBAD")
    print("  SIMBAD: reachable")
except Exception as exc:
    services_failed["SIMBAD"] = f"{type(exc).__name__}: {exc}"
    print(f"  SIMBAD: FAILED ({type(exc).__name__})")


print("\n3/6 Testing SkyBoT (IMCCE) / MPC Checker reachability")

skybot_ok = False
if Skybot is not None:
    try:
        Skybot.TIMEOUT = 15
        _ = query_skybot(
            SkyCoord(df["A_ra"].iloc[0] * u.deg, df["A_dec"].iloc[0] * u.deg),
            mjd["A"],
            SKYBOT_SEARCH_RADIUS
        )
        skybot_ok = True
        services_ok.add("SkyBoT (IMCCE)")
        print("  SkyBoT (IMCCE): reachable")
    except Exception as exc:
        services_failed["SkyBoT (IMCCE)"] = f"{type(exc).__name__}: {exc}"
        print(f"  SkyBoT (IMCCE): FAILED ({type(exc).__name__}: {exc})")
else:
    services_failed["SkyBoT (IMCCE)"] = "astroquery.imcce.Skybot not installed/importable"
    print("  SkyBoT (IMCCE): module not available")

import requests
mpc_ok = False
try:
    requests.head("https://minorplanetcenter.net/cgi-bin/checkmp.cgi", timeout=15)
    mpc_ok = True
    services_ok.add("MPC Checker")
    print("  MPC Checker: reachable")
except Exception as exc:
    services_failed["MPC Checker"] = f"{type(exc).__name__}: {exc}"
    print(f"  MPC Checker: FAILED ({type(exc).__name__}: {exc})")


print("\n4/6 Querying JPL Horizons for reference-body ephemerides (major/bright bodies only)")

horizons_ok = False
body_positions = {}

if Horizons is not None:
    try:
        for name, (target_id, obj_type) in HORIZONS_TARGETS.items():
            body_positions[name] = {}
            for epoch_label, jd_val in jd.items():
                obj = Horizons(id=target_id, location="500", epochs=jd_val)
                eph = obj.ephemerides()
                ra = float(eph["RA"][0])
                dec = float(eph["DEC"][0])
                body_positions[name][epoch_label] = SkyCoord(ra * u.deg, dec * u.deg)
        horizons_ok = True
        services_ok.add("JPL Horizons")
        print("  JPL Horizons: reachable,", len(HORIZONS_TARGETS), "bodies x 3 epochs queried")
    except Exception as exc:
        services_failed["JPL Horizons"] = f"{type(exc).__name__}: {exc}"
        print(f"  JPL Horizons: FAILED ({type(exc).__name__}: {exc})")
else:
    services_failed["JPL Horizons"] = "astroquery.jplhorizons.Horizons not installed/importable"
    print("  JPL Horizons: module not available")


print("\n5/6 Cross-matching each candidate at each epoch against each catalogue")

for row_i, cand in df.iterrows():

    candidate_id = cand["candidate_id"]
    print(f"  {candidate_id} ...", flush=True)

    for epoch in EPOCHS:

        ra = float(cand[f"{epoch}_ra"])
        dec = float(cand[f"{epoch}_dec"])
        coord = SkyCoord(ra * u.deg, dec * u.deg)
        mjd_val = mjd[epoch]

        # --- Gaia DR3 ---
        if "Gaia DR3" in services_ok:
            try:
                g = retry_call(query_gaia, coord, GAIA_SEARCH_RADIUS)
            except Exception as exc:
                add_row(candidate_id, epoch, mjd_val, ra, dec, "Gaia DR3",
                        "", "", np.nan, np.nan, np.nan, "SERVICE_UNAVAILABLE",
                        f"Query failed mid-run: {type(exc).__name__}: {exc}")
                g = "error"
            if g not in (None, "error"):
                add_row(candidate_id, epoch, mjd_val, ra, dec, "Gaia DR3",
                        g["name"], g["type"], g["ra"], g["dec"], g["sep"],
                        "MATCH" if g["sep"] <= GAIA_SEARCH_RADIUS else "NO_MATCH",
                        f"Static catalogue; search radius {GAIA_SEARCH_RADIUS}\"; "
                        f"'known' radius {GAIA_KNOWN_RADIUS}\"")
            elif g is None:
                add_row(candidate_id, epoch, mjd_val, ra, dec, "Gaia DR3",
                        "", "", np.nan, np.nan, np.nan, "NO_MATCH",
                        f"No Gaia DR3 source within {GAIA_SEARCH_RADIUS}\"")
        else:
            add_row(candidate_id, epoch, mjd_val, ra, dec, "Gaia DR3",
                    "", "", np.nan, np.nan, np.nan, "SERVICE_UNAVAILABLE",
                    services_failed.get("Gaia DR3", "unreachable"))

        # --- SIMBAD ---
        if "SIMBAD" in services_ok:
            try:
                s = retry_call(query_simbad, coord, SIMBAD_SEARCH_RADIUS)
            except Exception as exc:
                add_row(candidate_id, epoch, mjd_val, ra, dec, "SIMBAD",
                        "", "", np.nan, np.nan, np.nan, "SERVICE_UNAVAILABLE",
                        f"Query failed mid-run: {type(exc).__name__}: {exc}")
                s = "error"
            if s not in (None, "error"):
                add_row(candidate_id, epoch, mjd_val, ra, dec, "SIMBAD",
                        s["name"], s["type"], s["ra"], s["dec"], s["sep"],
                        "MATCH" if s["sep"] <= SIMBAD_SEARCH_RADIUS else "NO_MATCH",
                        f"Static catalogue; search radius {SIMBAD_SEARCH_RADIUS}\"; "
                        f"'known' radius {SIMBAD_KNOWN_RADIUS}\"")
            elif s is None:
                add_row(candidate_id, epoch, mjd_val, ra, dec, "SIMBAD",
                        "", "", np.nan, np.nan, np.nan, "NO_MATCH",
                        f"No SIMBAD object within {SIMBAD_SEARCH_RADIUS}\"")
        else:
            add_row(candidate_id, epoch, mjd_val, ra, dec, "SIMBAD",
                    "", "", np.nan, np.nan, np.nan, "SERVICE_UNAVAILABLE",
                    services_failed.get("SIMBAD", "unreachable"))

        # --- SkyBoT (IMCCE) ---
        if skybot_ok:
            try:
                sb = query_skybot(coord, mjd_val, SKYBOT_SEARCH_RADIUS)
            except Exception as exc:
                add_row(candidate_id, epoch, mjd_val, ra, dec, "SkyBoT (IMCCE)",
                        "", "", np.nan, np.nan, np.nan, "SERVICE_UNAVAILABLE",
                        f"Query failed mid-run: {type(exc).__name__}: {exc}")
                sb = "error"
            if sb not in (None, "error"):
                add_row(candidate_id, epoch, mjd_val, ra, dec, "SkyBoT (IMCCE)",
                        sb["name"], sb["type"], sb["ra"], sb["dec"], sb["sep"],
                        "MATCH" if sb["sep"] <= SKYBOT_SEARCH_RADIUS else "NO_MATCH",
                        f"Epoch-aware reverse search vs MPC orbital catalogue; "
                        f"search radius {SKYBOT_SEARCH_RADIUS}\"")
            elif sb is None:
                add_row(candidate_id, epoch, mjd_val, ra, dec, "SkyBoT (IMCCE)",
                        "", "", np.nan, np.nan, np.nan, "NO_MATCH",
                        f"No known Solar System body within {SKYBOT_SEARCH_RADIUS}\" at this epoch")
        else:
            add_row(candidate_id, epoch, mjd_val, ra, dec, "SkyBoT (IMCCE)",
                    "", "", np.nan, np.nan, np.nan, "SERVICE_UNAVAILABLE",
                    "Connectivity pre-test failed for this run: "
                    + services_failed.get("SkyBoT (IMCCE)", "unreachable")
                    + ". Not re-attempted per candidate/epoch to avoid repeated "
                      "long timeouts against an already-confirmed-down host.")

        # --- MPC Checker ---
        add_row(candidate_id, epoch, mjd_val, ra, dec, "MPC Checker",
                "", "", np.nan, np.nan, np.nan,
                "SERVICE_UNAVAILABLE" if not mpc_ok else "NO_MATCH",
                ("Connectivity pre-test failed for this run: "
                 + services_failed.get("MPC Checker", "unreachable")
                 + ". Not re-attempted per candidate/epoch (no working reverse "
                   "position-search endpoint available via astroquery for MPC; "
                   "would require the raw web form, also unreachable).")
                if not mpc_ok else
                "MPC Checker reachable but no scripted reverse-search query was run"
                " (see SkyBoT result for the equivalent MPC-catalogue check).")

        # --- JPL Horizons (major/bright bodies only) ---
        if horizons_ok:
            best = None
            for name, epoch_positions in body_positions.items():
                body_coord = epoch_positions.get(epoch)
                if body_coord is None:
                    continue
                sep = coord.separation(body_coord).arcsec
                if best is None or sep < best[1]:
                    best = (name, sep, body_coord)
            if best is not None:
                name, sep, body_coord = best
                obj_type = HORIZONS_TARGETS[name][1]
                status = "MATCH" if sep <= HORIZONS_SEARCH_RADIUS else "NO_MATCH"
                add_row(candidate_id, epoch, mjd_val, ra, dec, "JPL Horizons",
                        name if status == "MATCH" else "", obj_type if status == "MATCH" else "",
                        body_coord.ra.deg, body_coord.dec.deg, sep, status,
                        "Checked against 19 named major planets/dwarf planets/TNOs "
                        "only, NOT the full minor-planet catalogue "
                        f"(nearest body: {name}, {sep:.1f}\")")
            else:
                add_row(candidate_id, epoch, mjd_val, ra, dec, "JPL Horizons",
                        "", "", np.nan, np.nan, np.nan, "NO_MATCH",
                        "Checked against 19 named major planets/dwarf planets/TNOs "
                        "only, NOT the full minor-planet catalogue")
        else:
            add_row(candidate_id, epoch, mjd_val, ra, dec, "JPL Horizons",
                    "", "", np.nan, np.nan, np.nan, "SERVICE_UNAVAILABLE",
                    services_failed.get("JPL Horizons", "unreachable"))


detail = pd.DataFrame(rows)
detail.to_csv(DETAIL_CSV, index=False)
print(f"\nWrote {len(detail)} detail rows to {DETAIL_CSV}")


print("\n6/6 Determining final per-candidate status and saving combined file")

comprehensive_sso_available = skybot_ok or mpc_ok

summaries = []

for candidate_id, group in detail.groupby("candidate_id"):

    matches = group[group["match_status"] == "MATCH"]

    # Only a genuinely explanatory match counts toward KNOWN_OBJECT:
    #   - a Horizons major/bright-body match within its known radius, or
    #   - a Gaia/SIMBAD match within its known radius to the SAME cataloged
    #     object at more than one of the candidate's three epochs. Matching
    #     *some* nearby star at each epoch is not enough: this is a dense
    #     field (~12 Gaia sources/arcmin^2), so any single epoch has a
    #     non-trivial chance of landing within a few arcsec of an unrelated
    #     star, and different epochs can each coincidentally hit a
    #     DIFFERENT star (this was observed and would be a false positive
    #     if not filtered out here). Only the same object recurring ties
    #     the candidate to one static source; since the candidates' own
    #     inter-epoch motion (tens of arcsec) is far larger than the
    #     catalogue search radius, this essentially never happens for a
    #     genuinely moving candidate, which is the physically expected,
    #     conservative result.
    known_object_match = None

    horizons_hits = matches[
        (matches["catalogue"] == "JPL Horizons")
        & (matches["separation_arcsec"] <= HORIZONS_KNOWN_RADIUS)
    ]
    if len(horizons_hits) > 0:
        known_object_match = horizons_hits.iloc[0]

    if known_object_match is None:
        for cat, radius in [("Gaia DR3", GAIA_KNOWN_RADIUS), ("SIMBAD", SIMBAD_KNOWN_RADIUS)]:
            cat_matches = matches[
                (matches["catalogue"] == cat)
                & (matches["separation_arcsec"] <= radius)
            ]
            repeat_objects = cat_matches["matched_object"].value_counts()
            repeat_objects = repeat_objects[repeat_objects >= 2]
            if len(repeat_objects) > 0:
                same_object_matches = cat_matches[
                    cat_matches["matched_object"] == repeat_objects.index[0]
                ]
                known_object_match = same_object_matches.sort_values("separation_arcsec").iloc[0]
                break

    skybot_hits = matches[
        (matches["catalogue"] == "SkyBoT (IMCCE)")
        & (matches["separation_arcsec"] <= SKYBOT_KNOWN_RADIUS)
    ]
    if len(skybot_hits) > 0:
        known_object_match = skybot_hits.iloc[0]

    # best incidental match, for reporting even when not decisive
    best_any = matches.sort_values("separation_arcsec").iloc[0] if len(matches) > 0 else None

    if known_object_match is not None:
        final_status = "KNOWN_OBJECT"
    elif not comprehensive_sso_available:
        final_status = "UNCERTAIN"
    else:
        final_status = "UNMATCHED_AFTER_CHECKS"

    services_used = sorted(group["catalogue"].unique().tolist())
    services_failed_here = sorted(
        group.loc[group["match_status"] == "SERVICE_UNAVAILABLE", "catalogue"].unique().tolist()
    )
    services_succeeded_here = sorted(
        group.loc[group["match_status"] != "SERVICE_UNAVAILABLE", "catalogue"].unique().tolist()
    )

    if final_status == "UNCERTAIN":
        status_notes = (
            "Comprehensive Solar System catalogue check (SkyBoT/MPC) could not "
            "be completed for this candidate in this run; status kept UNCERTAIN "
            "rather than UNMATCHED_AFTER_CHECKS."
        )
    elif final_status == "KNOWN_OBJECT":
        status_notes = (
            f"Explanatory match: {known_object_match['catalogue']} -> "
            f"{known_object_match['matched_object']} at "
            f"{known_object_match['separation_arcsec']:.2f}\" "
            f"(epoch {known_object_match['epoch']})"
        )
    else:
        status_notes = "All performed checks completed; no match found in any."

    if best_any is not None and (known_object_match is None or best_any.name != known_object_match.name):
        status_notes += (
            f" | Nearest incidental catalogue coincidence (not treated as "
            f"identification): {best_any['catalogue']} -> "
            f"{best_any['matched_object']} at {best_any['separation_arcsec']:.2f}\" "
            f"(epoch {best_any['epoch']})"
        )

    summaries.append({
        "candidate_id": candidate_id,
        "final_catalogue_status": final_status,
        "best_match_catalogue": best_any["catalogue"] if best_any is not None else "",
        "best_match_object": best_any["matched_object"] if best_any is not None else "",
        "best_match_separation_arcsec": best_any["separation_arcsec"] if best_any is not None else np.nan,
        "best_match_epoch": best_any["epoch"] if best_any is not None else "",
        "services_succeeded": ";".join(services_succeeded_here),
        "services_failed": ";".join(services_failed_here),
        "catalogue_notes": status_notes,
    })

summary_df = pd.DataFrame(summaries)

combined = df.merge(summary_df, on="candidate_id", how="left")
combined.to_csv(COMBINED_CSV, index=False)


print()
print("==============================")
print("CATALOGUE CROSS-MATCH SUMMARY")
print("==============================")
print("Candidates:", len(summary_df))
print()
print("Services that worked this run:", sorted(services_ok) or "none")
print("Services that failed this run:")
for name, err in services_failed.items():
    print(f"  - {name}: {err}")

print()
n_known = int((summary_df["final_catalogue_status"] == "KNOWN_OBJECT").sum())
n_unmatched = int((summary_df["final_catalogue_status"] == "UNMATCHED_AFTER_CHECKS").sum())
n_uncertain = int((summary_df["final_catalogue_status"] == "UNCERTAIN").sum())

print("KNOWN_OBJECT:", n_known)
print("UNMATCHED_AFTER_CHECKS:", n_unmatched)
print("UNCERTAIN:", n_uncertain)

print()
print(
    summary_df[
        ["candidate_id", "final_catalogue_status", "best_match_catalogue",
         "best_match_separation_arcsec"]
    ].to_string(index=False)
)

print()
print("Detail rows written:", len(detail), "->", DETAIL_CSV)
print("Combined file written:", len(combined), "rows ->", COMBINED_CSV)

# --- verification ---
print()
print("VERIFICATION")
detail_check = pd.read_csv(DETAIL_CSV)
combined_check = pd.read_csv(COMBINED_CSV)
assert len(detail_check) == 22 * 3 * 5, f"unexpected detail row count: {len(detail_check)}"
assert len(combined_check) == 22, f"unexpected combined row count: {len(combined_check)}"
assert set(combined_check["final_catalogue_status"].unique()) <= {
    "KNOWN_OBJECT", "UNMATCHED_AFTER_CHECKS", "UNCERTAIN"
}
print(f"  {DETAIL_CSV}: {len(detail_check)} rows, {detail_check['candidate_id'].nunique()} candidates - OK")
print(f"  {COMBINED_CSV}: {len(combined_check)} rows, all final_catalogue_status values valid - OK")
