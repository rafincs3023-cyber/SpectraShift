import pandas as pd
import numpy as np

from astropy.coordinates import SkyCoord
import astropy.units as u
from astropy.io import fits


FILE_A = "level2_2025W19_2B_0166_3D3_spx_l2b-v20-2025-247.fits"
FILE_B = "level2_2025W24_1A_0099_1D3_spx_l2b-v20-2025-252.fits"

UNMATCHED_A = "unmatched_A.csv"
UNMATCHED_B = "unmatched_B.csv"

MIN_MOTION_ARCSEC = 10
MAX_MOTION_ARCSEC = 120
MIN_FLUX_RATIO = 0.5
MAX_FLUX_RATIO = 2.0


print("1/4 Loading source lists...")

a = pd.read_csv(UNMATCHED_A)
b = pd.read_csv(UNMATCHED_B)

# Remove invalid detections
a = a[
    np.isfinite(a["ra"])
    & np.isfinite(a["dec"])
    & np.isfinite(a["flux"])
    & (a["flux"] > 0)
].reset_index(drop=True)

b = b[
    np.isfinite(b["ra"])
    & np.isfinite(b["dec"])
    & np.isfinite(b["flux"])
    & (b["flux"] > 0)
].reset_index(drop=True)


print("Valid unmatched A:", len(a))
print("Valid unmatched B:", len(b))


print("\n2/4 Reading observation time...")

with fits.open(FILE_A) as hdul:
    mjd_a = hdul["IMAGE"].header.get("MJD-OBS")

with fits.open(FILE_B) as hdul:
    mjd_b = hdul["IMAGE"].header.get("MJD-OBS")

time_gap_days = abs(mjd_b - mjd_a)

print("Time gap:", round(time_gap_days, 3), "days")


print("\n3/4 Searching for motion pairs...")

coords_a = SkyCoord(
    ra=a["ra"].values * u.deg,
    dec=a["dec"].values * u.deg
)

coords_b = SkyCoord(
    ra=b["ra"].values * u.deg,
    dec=b["dec"].values * u.deg
)

# A -> nearest B
idx_ab, sep_ab, _ = coords_a.match_to_catalog_sky(coords_b)

# B -> nearest A
idx_ba, sep_ba, _ = coords_b.match_to_catalog_sky(coords_a)

candidates = []

for i in range(len(a)):

    j = idx_ab[i]

    # Must be mutual nearest neighbour
    if idx_ba[j] != i:
        continue

    separation = sep_ab[i].arcsec

    if separation < MIN_MOTION_ARCSEC:
        continue

    if separation > MAX_MOTION_ARCSEC:
        continue

    flux_a = a.iloc[i]["flux"]
    flux_b = b.iloc[j]["flux"]

    flux_ratio = flux_b / flux_a

    if not (
        MIN_FLUX_RATIO
        <= flux_ratio
        <= MAX_FLUX_RATIO
    ):
        continue

    motion_per_day = (
        separation / time_gap_days
    )

    candidates.append({
        "ra_epoch_A": a.iloc[i]["ra"],
        "dec_epoch_A": a.iloc[i]["dec"],

        "ra_epoch_B": b.iloc[j]["ra"],
        "dec_epoch_B": b.iloc[j]["dec"],

        "separation_arcsec": separation,
        "motion_arcsec_per_day": motion_per_day,

        "flux_A": flux_a,
        "flux_B": flux_b,
        "flux_ratio_B_over_A": flux_ratio,

        "source_A_id": a.iloc[i]["id"],
        "source_B_id": b.iloc[j]["id"]
    })


result = pd.DataFrame(candidates)

if len(result) > 0:

    # Larger displacement first
    result = result.sort_values(
        "separation_arcsec",
        ascending=False
    )

    result.insert(
        0,
        "candidate_id",
        [
            f"MOTION-{i:03d}"
            for i in range(
                1,
                len(result) + 1
            )
        ]
    )

    result.to_csv(
        "motion_candidates.csv",
        index=False
    )


print("\n4/4 Finished.")

print("\n==============================")
print("PRELIMINARY MOTION RESULTS")
print("==============================")

print(
    "Motion candidates:",
    len(result)
)

if len(result) > 0:

    print("\nTop 10:\n")

    print(
        result[
            [
                "candidate_id",
                "separation_arcsec",
                "motion_arcsec_per_day",
                "flux_ratio_B_over_A"
            ]
        ].head(10).to_string(index=False)
    )

    print(
        "\nCreated: motion_candidates.csv"
    )

else:
    print(
        "No candidates passed current filters."
    )