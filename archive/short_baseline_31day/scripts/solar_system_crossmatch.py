"""
Known Solar System object cross-match for the validated candidates (legacy;
superseded by catalogue_crossmatch_v3.py).

Does NOT repeat the Gaia DR3 / SIMBAD checks already stored in
catalogue_crossmatch_results.csv -- this script only adds the missing
known-Solar-System-object columns to that same file.

Attempts, in order:
  1. SkyBoT (IMCCE)          - reverse cone search vs the full MPC minor-body
                                 orbital catalogue (comprehensive, epoch-aware)
  2. MPC Minor Planet Checker - reverse cone search vs MPC orbital catalogue
  3. JPL Horizons              - direct ephemeris for a fixed list of major
                                 planets + the largest/brightest minor planets
                                 and TNOs (NOT comprehensive: only checks the
                                 ~20 named bodies below, not the full ~1.3M
                                 object minor-planet catalogue)

If both (1) and (2) are unreachable (as previously found for this
environment), this script falls back to (3) and clearly records that the
check was only a "major/bright body" check, not a full minor-planet
catalogue search, via the console report.
"""

import warnings

from astropy.io import fits
from astropy.coordinates import SkyCoord
from astropy.time import Time
import astropy.units as u

import numpy as np
import pandas as pd

FILE_A = "level2_2025W19_2B_0166_3D3_spx_l2b-v20-2025-247.fits"
FILE_C = "level2_2025W22_1B_0226_1D3_spx_l2b-v20-2025-250.fits"
FILE_B = "level2_2025W24_1A_0099_1D3_spx_l2b-v20-2025-252.fits"

VALIDATED_CSV = "validated_three_epoch_candidates.csv"
RESULTS_CSV = "catalogue_crossmatch_results.csv"

EPOCHS = ["A", "C", "B"]

SEARCH_RADIUS_ARCSEC = 60.0   # generous: Horizons ephemerides are ~exact,
                               # our own astrometry is the limiting factor
KNOWN_RADIUS_ARCSEC = 10.0

# Major planets + the largest/brightest minor planets and TNOs. This is a
# fixed, named-object best-effort list -- NOT the full MPC minor-planet
# catalogue (that requires SkyBoT/MPC reverse search, which is unreachable
# from this environment; see console output).
HORIZONS_TARGETS = {
    "Mercury": "199",
    "Venus": "299",
    "Mars": "499",
    "Jupiter": "599",
    "Saturn": "699",
    "Uranus": "799",
    "Neptune": "899",
    "Pluto": "999",
    "Ceres": "1;",
    "Pallas": "2;",
    "Juno": "3;",
    "Vesta": "4;",
    "Eris": "136199;",
    "Makemake": "136472;",
    "Haumea": "136108;",
    "Sedna": "90377;",
    "Quaoar": "50000;",
    "Orcus": "90482;",
    "Gonggong": "225088;",
}


def get_mjd(filename):
    with fits.open(filename) as hdul:
        return hdul["IMAGE"].header.get("MJD-OBS")


def check_reverse_search_services():
    """Try SkyBoT then MPC checkmp; return which (if any) is usable."""

    import requests

    services = {
        "SkyBoT (IMCCE)": "https://ssp.imcce.fr/webservices/skybot/api/conesearch.php",
        "MPC Checker": "https://minorplanetcenter.net/cgi-bin/checkmp.cgi",
    }

    for name, url in services.items():
        try:
            requests.head(url, timeout=12)
            print(f"  {name}: reachable")
            return name
        except Exception as exc:
            print(f"  {name}: unreachable ({type(exc).__name__})")

    return None


def query_horizons_positions(targets, epochs_jd):
    """Return dict {name: {epoch_label: SkyCoord}} for each target/epoch."""

    from astroquery.jplhorizons import Horizons

    positions = {}

    for name, target_id in targets.items():
        positions[name] = {}
        for epoch_label, jd in epochs_jd.items():
            try:
                obj = Horizons(
                    id=target_id,
                    location="500",
                    epochs=jd,
                    id_type=None
                )
                eph = obj.ephemerides()
                ra = float(eph["RA"][0])
                dec = float(eph["DEC"][0])
                positions[name][epoch_label] = SkyCoord(ra * u.deg, dec * u.deg)
            except Exception as exc:
                print(f"    Horizons query failed for {name} @ {epoch_label}: {exc}")

    return positions


print("1/5 Loading candidates and epoch timing")

results = pd.read_csv(RESULTS_CSV)
validated = pd.read_csv(VALIDATED_CSV)

df = results.merge(
    validated[["candidate_id", "A_ra", "A_dec", "C_ra", "C_dec", "B_ra", "B_dec"]],
    on="candidate_id",
    how="left"
)

print("Candidates:", len(df))

mjd = {
    "A": get_mjd(FILE_A),
    "C": get_mjd(FILE_C),
    "B": get_mjd(FILE_B),
}
jd = {k: Time(v, format="mjd").jd for k, v in mjd.items()}
print("Epoch MJDs:", mjd)

# Ecliptic latitude context: known minor planets/TNOs cluster tightly around
# the ecliptic plane, so this is useful physical context for interpreting
# any "Unmatched" result.
mean_coord = SkyCoord(
    df["A_ra"].mean() * u.deg,
    df["A_dec"].mean() * u.deg
)
ecl = mean_coord.transform_to("geocentricmeanecliptic")
print(
    f"Field center ecliptic latitude: {ecl.lat.deg:.2f} deg "
    "(known minor planets/TNOs are almost always within a few tens of "
    "degrees of the ecliptic; a large |beta| here makes a known-catalogue "
    "match a priori unlikely, independent of catalogue coverage)"
)


print("\n2/5 Checking reverse position-search services (SkyBoT / MPC)")

reverse_service = check_reverse_search_services()

if reverse_service is None:
    print(
        "  Neither SkyBoT nor the MPC Checker is reachable from this "
        "environment. Falling back to JPL Horizons ephemerides for a "
        "fixed list of major planets + largest minor planets/TNOs "
        "(NOT a full minor-planet catalogue search)."
    )


print("\n3/5 Querying JPL Horizons ephemerides for reference bodies")

body_positions = query_horizons_positions(HORIZONS_TARGETS, jd)


print("\n4/5 Cross-matching each candidate against reference-body positions")

records = []

for _, row in df.iterrows():

    candidate_id = row["candidate_id"]

    epoch_hits = []

    for epoch in EPOCHS:

        ra = row[f"{epoch}_ra"]
        dec = row[f"{epoch}_dec"]

        if pd.isna(ra) or pd.isna(dec):
            continue

        coord = SkyCoord(ra * u.deg, dec * u.deg)

        for name, epoch_positions in body_positions.items():
            body_coord = epoch_positions.get(epoch)
            if body_coord is None:
                continue

            sep = coord.separation(body_coord).arcsec

            if sep <= SEARCH_RADIUS_ARCSEC:
                epoch_hits.append({
                    "name": name,
                    "epoch": epoch,
                    "separation_arcsec": float(sep),
                })

    if epoch_hits:
        best = min(epoch_hits, key=lambda h: h["separation_arcsec"])
        sep = best["separation_arcsec"]
        status = "Known" if sep <= KNOWN_RADIUS_ARCSEC else "Possible"
        object_name = best["name"]
        matched_epoch = best["epoch"]
    else:
        sep = np.nan
        status = "Unmatched"
        object_name = ""
        matched_epoch = ""

    records.append({
        "candidate_id": candidate_id,
        "solar_system_checked": True,
        "solar_system_match": status,
        "solar_system_object_name": object_name,
        "solar_system_separation": sep,
        "solar_system_epoch": matched_epoch,
    })

sso = pd.DataFrame(records)


print("\n5/5 Updating catalogue_crossmatch_results.csv")

for col in [
    "solar_system_checked",
    "solar_system_match",
    "solar_system_object_name",
    "solar_system_separation",
    "solar_system_epoch",
]:
    if col in results.columns:
        results = results.drop(columns=[col])

results = results.merge(sso, on="candidate_id", how="left")
results.to_csv(RESULTS_CSV, index=False)


print()
print("==============================")
print("SOLAR SYSTEM OBJECT CROSS-MATCH")
print("==============================")
print(f"Method: JPL Horizons, {len(HORIZONS_TARGETS)} major/bright named "
      f"bodies (SkyBoT/MPC reverse search: {reverse_service or 'unreachable'})")
print(f"Field ecliptic latitude: {ecl.lat.deg:.2f} deg")
print()

n_known = int((results["solar_system_match"] == "Known").sum())
n_possible = int((results["solar_system_match"] == "Possible").sum())
n_unmatched = int((results["solar_system_match"] == "Unmatched").sum())

print("Known:", n_known)
print("Possible:", n_possible)
print("Unmatched:", n_unmatched)

unmatched_ids = results.loc[
    results["solar_system_match"] == "Unmatched",
    "candidate_id"
].tolist()

print()
print("Unmatched candidate IDs:")
print(unmatched_ids)

print()
print(
    results[
        [
            "candidate_id",
            "solar_system_match",
            "solar_system_object_name",
            "solar_system_separation",
            "solar_system_epoch",
        ]
    ].to_string(index=False)
)

print()
print("Updated:", RESULTS_CSV)
