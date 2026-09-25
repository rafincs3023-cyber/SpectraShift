from astropy.io import fits
from astropy.wcs import WCS
from astropy.stats import sigma_clipped_stats
from astropy.coordinates import SkyCoord
import astropy.units as u

from photutils.detection import DAOStarFinder
from photutils.aperture import CircularAperture, aperture_photometry

import numpy as np
import csv


FILE_A = "level2_2025W19_2B_0166_3D3_spx_l2b-v20-2025-247.fits"
FILE_B = "level2_2025W24_1A_0099_1D3_spx_l2b-v20-2025-252.fits"

DETECTION_SIGMA = 5.0
FWHM = 2.0
APERTURE_RADIUS = 3.0
MATCH_RADIUS_ARCSEC = 10.0


def detect_sources(filename, label):

    print(f"\nDetecting sources in {label}...")

    with fits.open(filename) as hdul:
        image = hdul["IMAGE"].data.astype(float)
        header = hdul["IMAGE"].header.copy()

    wcs = WCS(header)

    finite = np.isfinite(image)

    mean, median, std = sigma_clipped_stats(
        image[finite],
        sigma=3.0
    )

    clean_image = image.copy()
    clean_image[~finite] = median

    background_subtracted = clean_image - median

    finder = DAOStarFinder(
        fwhm=FWHM,
        threshold=DETECTION_SIGMA * std
    )

    sources = finder(background_subtracted)

    if sources is None:
        print("No sources detected.")
        return [], wcs

    positions = np.transpose(
        (
            sources["xcentroid"],
            sources["ycentroid"]
        )
    )

    apertures = CircularAperture(
        positions,
        r=APERTURE_RADIUS
    )

    photometry = aperture_photometry(
        background_subtracted,
        apertures
    )

    result = []

    for i in range(len(sources)):

        x = float(sources["xcentroid"][i])
        y = float(sources["ycentroid"][i])

        ra, dec = wcs.pixel_to_world_values(x, y)

        flux = float(
            photometry["aperture_sum"][i]
        )

        result.append({
            "id": i + 1,
            "x": x,
            "y": y,
            "ra": float(ra),
            "dec": float(dec),
            "flux": flux
        })

    print(f"{label}: {len(result)} sources detected")

    return result, wcs


print("1/4 Detecting Observation A")

sources_a, wcs_a = detect_sources(
    FILE_A,
    "Observation A"
)

print("\n2/4 Detecting Observation B")

sources_b, wcs_b = detect_sources(
    FILE_B,
    "Observation B"
)


print("\n3/4 Matching sources...")


coords_a = SkyCoord(
    ra=[s["ra"] for s in sources_a] * u.deg,
    dec=[s["dec"] for s in sources_a] * u.deg
)

coords_b = SkyCoord(
    ra=[s["ra"] for s in sources_b] * u.deg,
    dec=[s["dec"] for s in sources_b] * u.deg
)


idx, separation, _ = coords_a.match_to_catalog_sky(
    coords_b
)


matched = []
matched_b_ids = set()
unmatched_a = []


for i, sep in enumerate(separation):

    source_a = sources_a[i]

    if sep.arcsec <= MATCH_RADIUS_ARCSEC:

        source_b = sources_b[idx[i]]

        matched_b_ids.add(idx[i])

        flux_a = source_a["flux"]
        flux_b = source_b["flux"]

        if flux_a != 0:
            brightness_change = (
                (flux_b - flux_a) / abs(flux_a)
            ) * 100
        else:
            brightness_change = np.nan

        matched.append({
            "source_a": source_a["id"],
            "source_b": source_b["id"],

            "ra_a": source_a["ra"],
            "dec_a": source_a["dec"],

            "ra_b": source_b["ra"],
            "dec_b": source_b["dec"],

            "separation_arcsec": sep.arcsec,

            "flux_a": flux_a,
            "flux_b": flux_b,

            "brightness_change_percent":
                brightness_change
        })

    else:
        unmatched_a.append(source_a)


unmatched_b = []

for i, source_b in enumerate(sources_b):

    if i not in matched_b_ids:
        unmatched_b.append(source_b)


print("\n4/4 Saving results...")


with open(
    "source_matches.csv",
    "w",
    newline="",
    encoding="utf-8"
) as f:

    fieldnames = [
        "source_a",
        "source_b",
        "ra_a",
        "dec_a",
        "ra_b",
        "dec_b",
        "separation_arcsec",
        "flux_a",
        "flux_b",
        "brightness_change_percent"
    ]

    writer = csv.DictWriter(
        f,
        fieldnames=fieldnames
    )

    writer.writeheader()
    writer.writerows(matched)


def save_unmatched(filename, sources):

    with open(
        filename,
        "w",
        newline="",
        encoding="utf-8"
    ) as f:

        fieldnames = [
            "id",
            "ra",
            "dec",
            "x",
            "y",
            "flux"
        ]

        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames
        )

        writer.writeheader()
        writer.writerows(sources)


save_unmatched(
    "unmatched_A.csv",
    unmatched_a
)

save_unmatched(
    "unmatched_B.csv",
    unmatched_b
)


print("\nDONE")
print("-------------------------")

print(
    "Observation A sources:",
    len(sources_a)
)

print(
    "Observation B sources:",
    len(sources_b)
)

print(
    "Matched sources:",
    len(matched)
)

print(
    "Unmatched A:",
    len(unmatched_a)
)

print(
    "Unmatched B:",
    len(unmatched_b)
)

print("\nCreated:")
print(" source_matches.csv")
print(" unmatched_A.csv")
print(" unmatched_B.csv")