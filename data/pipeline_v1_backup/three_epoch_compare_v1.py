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
FWHM = 2.0
APERTURE_RADIUS = 3.0

MIN_TOTAL_MOTION = 5.0       # arcsec
MAX_TOTAL_MOTION = 120.0     # arcsec
C_POSITION_TOLERANCE = 4.0   # arcsec

MIN_FLUX_RATIO = 0.4
MAX_FLUX_RATIO = 2.5


def detect_sources(filename, name):

    print(f"Detecting {name}...")

    with fits.open(filename) as hdul:

        image = hdul["IMAGE"].data.astype(float)
        header = hdul["IMAGE"].header.copy()

        mjd = header.get("MJD-OBS")

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
        threshold=DETECTION_SIGMA * std
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


print("1/5 Detecting sources")

A, mjd_a = detect_sources(
    FILE_A,
    "Epoch A"
)

C, mjd_c = detect_sources(
    FILE_C,
    "Epoch C"
)

B, mjd_b = detect_sources(
    FILE_B,
    "Epoch B"
)


print("\n2/5 Observation timing")

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


print("\n3/5 Building sky coordinates")

coord_a = SkyCoord(
    A["ra"].values * u.deg,
    A["dec"].values * u.deg
)

coord_b = SkyCoord(
    B["ra"].values * u.deg,
    B["dec"].values * u.deg
)

coord_c = SkyCoord(
    C["ra"].values * u.deg,
    C["dec"].values * u.deg
)


# Find nearby A-B combinations
idx_a, idx_b, sep_ab, _ = coord_b.search_around_sky(
    coord_a,
    MAX_TOTAL_MOTION * u.arcsec
)


print(
    "Possible A-B pairs:",
    len(idx_a)
)


print("\n4/5 Testing three-epoch motion")

candidates = []

for ia, ib, sep in zip(
    idx_a,
    idx_b,
    sep_ab
):

    total_motion = sep.arcsec

    if total_motion < MIN_TOTAL_MOTION:
        continue

    a = A.iloc[ia]
    b = B.iloc[ib]

    # Flux similarity A vs B
    ratio_ab = b["flux"] / a["flux"]

    if not (
        MIN_FLUX_RATIO
        <= ratio_ab
        <= MAX_FLUX_RATIO
    ):
        continue

    # Predict where object should be at Epoch C
    ra_pred = (
        a["ra"]
        + fraction
        * (b["ra"] - a["ra"])
    )

    dec_pred = (
        a["dec"]
        + fraction
        * (b["dec"] - a["dec"])
    )

    predicted = SkyCoord(
        ra_pred * u.deg,
        dec_pred * u.deg
    )

    idx_c, sep_c, _ = predicted.match_to_catalog_sky(
        coord_c
    )

    # predicted is a scalar SkyCoord, so astropy returns 0-d/
    # single-element ndarrays here instead of plain scalars;
    # unwrap to Python scalars so they stay hashable/sortable
    # downstream (.item() handles both 0-d and shape-(1,) arrays).
    idx_c = int(np.asarray(idx_c).item())
    prediction_error = float(np.asarray(sep_c.arcsec).item())

    if prediction_error > C_POSITION_TOLERANCE:
        continue

    c = C.iloc[idx_c]

    ratio_ac = c["flux"] / a["flux"]
    ratio_cb = b["flux"] / c["flux"]

    if not (
        MIN_FLUX_RATIO
        <= ratio_ac
        <= MAX_FLUX_RATIO
    ):
        continue

    if not (
        MIN_FLUX_RATIO
        <= ratio_cb
        <= MAX_FLUX_RATIO
    ):
        continue

    motion_per_day = (
        total_motion / dt_ab
    )

    candidates.append({

        "A_source": int(a["id"]),
        "C_source": int(c["id"]),
        "B_source": int(b["id"]),

        "A_ra": float(a["ra"]),
        "A_dec": float(a["dec"]),

        "C_ra": float(c["ra"]),
        "C_dec": float(c["dec"]),

        "B_ra": float(b["ra"]),
        "B_dec": float(b["dec"]),

        "total_motion_arcsec":
            float(total_motion),

        "motion_arcsec_per_day":
            float(motion_per_day),

        "C_prediction_error_arcsec":
            float(prediction_error),

        "flux_A": float(a["flux"]),
        "flux_C": float(c["flux"]),
        "flux_B": float(b["flux"])
    })


result = pd.DataFrame(candidates)


print("\n5/5 Saving results")

if len(result) > 0:

    result = result.sort_values(
        [
            "C_prediction_error_arcsec",
            "total_motion_arcsec"
        ],
        ascending=[
            True,
            False
        ]
    )

    result.insert(
        0,
        "candidate_id",
        [
            f"3EPOCH-{i:03d}"
            for i in range(
                1,
                len(result) + 1
            )
        ]
    )

    result.to_csv(
        "three_epoch_motion_candidates.csv",
        index=False
    )


print()
print("==============================")
print("THREE-EPOCH MOTION RESULTS")
print("==============================")

print(
    "Candidates:",
    len(result)
)

if len(result) > 0:

    print()
    print(
        result[
            [
                "candidate_id",
                "total_motion_arcsec",
                "motion_arcsec_per_day",
                "C_prediction_error_arcsec"
            ]
        ].head(20).to_string(
            index=False
        )
    )

    print()
    print(
        "Created: three_epoch_motion_candidates.csv"
    )

else:

    print(
        "No three-epoch motion candidate "
        "passed the current filters."
    )