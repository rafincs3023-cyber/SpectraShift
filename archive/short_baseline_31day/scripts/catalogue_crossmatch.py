"""
Cross-match the 22 validated three-epoch motion candidates against:
  1. Gaia DR3          (static astrometric catalogue -> flags stars/blends)
  2. SIMBAD            (static object catalogue -> flags known stars/galaxies/etc.)
  3. SkyBoT / IMCCE     (known Solar System objects, epoch-aware reverse cone search;
                         SkyBoT is the standard reverse-search front end for the
                         MPC/JPL minor-body orbital catalogue)

Each candidate is checked at ALL THREE of its detected sky positions (Epoch A,
C, B), because a real moving object should show no static-catalogue counterpart
at any epoch, whereas a spurious/blended pair could coincide with a real Gaia/
SIMBAD source at one or more epochs. The single best (closest, most confident)
match across all catalogues/epochs is reported as the candidate's primary
match; full per-epoch detail is kept in extra columns for transparency.

This script does NOT rerun the three-epoch validation and does NOT claim any
unmatched candidate is a new/real object (including "Planet X").
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


FILE_A = "level2_2025W19_2B_0166_3D3_spx_l2b-v20-2025-247.fits"
FILE_C = "level2_2025W22_1B_0226_1D3_spx_l2b-v20-2025-250.fits"
FILE_B = "level2_2025W24_1A_0099_1D3_spx_l2b-v20-2025-252.fits"

INPUT_CSV = "validated_three_epoch_candidates.csv"
OUTPUT_CSV = "catalogue_crossmatch_results.csv"

EPOCHS = ["A", "C", "B"]

# Search / confidence radii (arcsec). SPHEREx pixel scale is ~6.15"/pixel, and
# the three-epoch pipeline used a 4" astrometric tolerance, so these are set
# a bit looser than that to absorb centroiding + WCS uncertainty while still
# being a tight, meaningful association.
GAIA_SEARCH_RADIUS = 8.0
GAIA_KNOWN_RADIUS = 4.0

SIMBAD_SEARCH_RADIUS = 8.0
SIMBAD_KNOWN_RADIUS = 4.0

# Looser radius for known moving objects: SkyBoT ephemeris + our own
# astrometric uncertainty both contribute.
SKYBOT_SEARCH_RADIUS = 20.0
SKYBOT_KNOWN_RADIUS = 10.0

Gaia.ROW_LIMIT = 20

warnings.simplefilter("ignore", category=NoResultsWarning)


def get_mjd(filename):
    with fits.open(filename) as hdul:
        return hdul["IMAGE"].header.get("MJD-OBS")


def query_gaia(coord, radius_arcsec):
    radius_deg = radius_arcsec / 3600.0
    adql = (
        "SELECT source_id, ra, dec, phot_g_mean_mag "
        "FROM gaiadr3.gaia_source WHERE 1=CONTAINS("
        f"POINT('ICRS', ra, dec), "
        f"CIRCLE('ICRS', {coord.ra.deg}, {coord.dec.deg}, {radius_deg}))"
    )

    job = Gaia.launch_job(adql)
    table = job.get_results()

    if table is None or len(table) == 0:
        return None

    cat_coords = SkyCoord(
        table["ra"].data * u.deg,
        table["dec"].data * u.deg
    )
    sep = coord.separation(cat_coords).arcsec

    i = int(np.argmin(sep))

    return {
        "name": f"Gaia DR3 {int(table['source_id'][i])}",
        "separation_arcsec": float(sep[i]),
    }


def query_simbad(coord, radius_arcsec):
    table = Simbad.query_region(coord, radius=radius_arcsec * u.arcsec)

    if table is None or len(table) == 0:
        return None

    cat_coords = SkyCoord(
        table["ra"].data * u.deg,
        table["dec"].data * u.deg
    )
    sep = coord.separation(cat_coords).arcsec

    i = int(np.argmin(sep))
    main_id = table["main_id"][i]
    if isinstance(main_id, bytes):
        main_id = main_id.decode()

    return {
        "name": str(main_id),
        "separation_arcsec": float(sep[i]),
    }


def query_skybot(coord, mjd, radius_arcsec):
    epoch = Time(mjd, format="mjd")

    table = Skybot.cone_search(
        coord,
        radius_arcsec * u.arcsec,
        epoch,
        location="500"
    )

    if table is None or len(table) == 0:
        return None

    cat_coords = SkyCoord(table["RA"], table["DEC"])
    sep = coord.separation(cat_coords).arcsec

    i = int(np.argmin(sep))
    name = table["Name"][i]

    return {
        "name": str(name),
        "separation_arcsec": float(sep[i]),
    }


print("1/4 Loading validated candidates and epoch timing")

df = pd.read_csv(INPUT_CSV)
print("Candidates to cross-match:", len(df))

mjd = {
    "A": get_mjd(FILE_A),
    "C": get_mjd(FILE_C),
    "B": get_mjd(FILE_B),
}
print("Epoch MJDs:", mjd)


print("\n2/4 Checking SkyBoT (IMCCE/MPC known-object service) availability")

skybot_available = False

if Skybot is not None:
    try:
        Skybot.TIMEOUT = 15
        test_coord = SkyCoord(df["A_ra"].iloc[0] * u.deg, df["A_dec"].iloc[0] * u.deg)
        query_skybot(test_coord, mjd["A"], SKYBOT_SEARCH_RADIUS)
        skybot_available = True
        print("SkyBoT reachable - known Solar System object search enabled.")
    except Exception as exc:
        print(
            "SkyBoT/IMCCE service unreachable from this environment "
            f"({type(exc).__name__}). Skipping known-SSO (JPL/MPC) "
            "cross-match; all candidates will be marked "
            "'not checked' for that catalogue."
        )
else:
    print("astroquery.imcce.Skybot not available in this install.")


print("\n3/4 Cross-matching Gaia DR3 / SIMBAD / SkyBoT for each candidate x epoch")

records = []

for row_i, row in df.iterrows():

    candidate_id = row["candidate_id"]
    print(f"  {candidate_id} ...", flush=True)

    epoch_matches = {"gaia": [], "simbad": [], "skybot": []}

    for epoch in EPOCHS:

        ra = row[f"{epoch}_ra"]
        dec = row[f"{epoch}_dec"]
        coord = SkyCoord(ra * u.deg, dec * u.deg)

        try:
            g = query_gaia(coord, GAIA_SEARCH_RADIUS)
        except Exception as exc:
            g = None
            print(f"    Gaia query failed at epoch {epoch}: {exc}")
        if g is not None:
            g["epoch"] = epoch
            epoch_matches["gaia"].append(g)

        try:
            s = query_simbad(coord, SIMBAD_SEARCH_RADIUS)
        except Exception as exc:
            s = None
            print(f"    SIMBAD query failed at epoch {epoch}: {exc}")
        if s is not None:
            s["epoch"] = epoch
            epoch_matches["simbad"].append(s)

        if skybot_available:
            try:
                sb = query_skybot(coord, mjd[epoch], SKYBOT_SEARCH_RADIUS)
            except Exception as exc:
                sb = None
                print(f"    SkyBoT query failed at epoch {epoch}: {exc}")
            if sb is not None:
                sb["epoch"] = epoch
                epoch_matches["skybot"].append(sb)

    def best_of(matches):
        if not matches:
            return None
        return min(matches, key=lambda m: m["separation_arcsec"])

    best_gaia = best_of(epoch_matches["gaia"])
    best_simbad = best_of(epoch_matches["simbad"])
    best_skybot = best_of(epoch_matches["skybot"])

    # normalize each catalogue's best separation by its own "known" radius
    # so the three catalogues can be compared on equal footing
    candidates_for_best = []
    if best_gaia is not None:
        candidates_for_best.append(
            ("Gaia DR3", best_gaia, GAIA_KNOWN_RADIUS, GAIA_SEARCH_RADIUS)
        )
    if best_simbad is not None:
        candidates_for_best.append(
            ("SIMBAD", best_simbad, SIMBAD_KNOWN_RADIUS, SIMBAD_SEARCH_RADIUS)
        )
    if best_skybot is not None:
        candidates_for_best.append(
            ("SkyBoT (MPC/JPL bodies)", best_skybot, SKYBOT_KNOWN_RADIUS, SKYBOT_SEARCH_RADIUS)
        )

    if candidates_for_best:
        catalogue, match, known_r, search_r = min(
            candidates_for_best,
            key=lambda c: c[1]["separation_arcsec"] / c[2]
        )
        sep = match["separation_arcsec"]
        status = "Known" if sep <= known_r else "Possible"
        matched_object = match["name"]
        matched_epoch = match["epoch"]
    else:
        catalogue = "None"
        matched_object = ""
        sep = np.nan
        status = "Unmatched"
        matched_epoch = ""

    records.append({
        "candidate_id": candidate_id,
        "matched_catalogue": catalogue,
        "matched_object": matched_object,
        "angular_separation_arcsec": sep,
        "match_status": status,
        "matched_epoch": matched_epoch,
        "gaia_best_match": best_gaia["name"] if best_gaia else "",
        "gaia_separation_arcsec": best_gaia["separation_arcsec"] if best_gaia else np.nan,
        "simbad_best_match": best_simbad["name"] if best_simbad else "",
        "simbad_separation_arcsec": best_simbad["separation_arcsec"] if best_simbad else np.nan,
        "skybot_best_match": best_skybot["name"] if best_skybot else "",
        "skybot_separation_arcsec": best_skybot["separation_arcsec"] if best_skybot else np.nan,
        "skybot_checked": skybot_available,
    })


print("\n4/4 Saving results")

result = pd.DataFrame(records)
result.to_csv(OUTPUT_CSV, index=False)

print()
print("==============================")
print("CATALOGUE CROSS-MATCH RESULTS")
print("==============================")
print("Total candidates:", len(result))

for status in ["Known", "Possible", "Unmatched"]:
    n = int((result["match_status"] == status).sum())
    print(f"{status}: {n}")

print()
print(
    result[
        [
            "candidate_id",
            "matched_catalogue",
            "matched_object",
            "angular_separation_arcsec",
            "match_status"
        ]
    ].to_string(index=False)
)

print()
print("Created:", OUTPUT_CSV)

if not skybot_available:
    print()
    print(
        "NOTE: The SkyBoT/IMCCE known Solar System object service "
        "(the standard reverse cone-search front end for the MPC/JPL "
        "minor-body catalogue) was unreachable from this environment, "
        "so the JPL/MPC known-object check could not be completed. "
        "No candidate has been checked against known asteroids/comets/"
        "planets; this is reflected in 'skybot_checked' = False for "
        "every row, and no match was fabricated."
    )
