from astropy.io import fits
from astropy.wcs import WCS
from reproject import reproject_interp
from scipy import ndimage
import numpy as np
import csv
import os
import matplotlib.pyplot as plt
from matplotlib.patches import Circle

FILE_A = "level2_2025W19_2B_0166_3D3_spx_l2b-v20-2025-247.fits"
FILE_B = "level2_2025W24_1A_0099_1D3_spx_l2b-v20-2025-252.fits"
DIFF_FILE = "difference_A_minus_B.fits"
VAR_B_CACHE = "variance_B_aligned.fits"

THRESHOLD_SIGMA = 6.0
MIN_PIXELS = 2
MAX_PIXELS = 100
EDGE_MARGIN = 20
MAX_CANDIDATES = 100

print("1/5 Loading FITS data...")

with fits.open(FILE_A) as hdul:
    variance_a = hdul["VARIANCE"].data.astype(float)
    header_a = hdul["IMAGE"].header.copy()

with fits.open(FILE_B) as hdul:
    variance_b = hdul["VARIANCE"].data.astype(float)
    header_b = hdul["IMAGE"].header.copy()

wcs_a = WCS(header_a)
wcs_b = WCS(header_b)

print("2/5 Preparing aligned variance...")

if os.path.exists(VAR_B_CACHE):
    with fits.open(VAR_B_CACHE) as hdul:
        variance_b_aligned = hdul[0].data.astype(float)

    footprint = np.isfinite(variance_b_aligned).astype(float)
    print("Using cached aligned variance.")

else:
    variance_b_aligned, footprint = reproject_interp(
        (variance_b, wcs_b),
        wcs_a,
        shape_out=variance_a.shape
    )

    fits.writeto(
        VAR_B_CACHE,
        variance_b_aligned,
        header_a,
        overwrite=True
    )

    print("Aligned variance cached.")

with fits.open(DIFF_FILE) as hdul:
    difference = hdul[0].data.astype(float)

print("3/5 Calculating significance...")

variance_a[variance_a < 0] = np.nan
variance_b_aligned[variance_b_aligned < 0] = np.nan

noise = np.sqrt(variance_a + variance_b_aligned)

valid = (
    np.isfinite(difference)
    & np.isfinite(noise)
    & (noise > 0)
    & (footprint > 0)
)

significance = np.full(difference.shape, np.nan)
significance[valid] = difference[valid] / noise[valid]

fits.writeto(
    "change_significance.fits",
    significance,
    header_a,
    overwrite=True
)

print("4/5 Detecting candidates...")

detections = []

masks = [
    ("A_brighter", significance >= THRESHOLD_SIGMA),
    ("B_brighter", significance <= -THRESHOLD_SIGMA),
]

structure = np.ones((3, 3), dtype=int)

for change_type, mask in masks:

    labels, number = ndimage.label(mask, structure=structure)

    print(f"{change_type}: {number} raw regions")

    if number == 0:
        continue

    # Count component sizes efficiently
    counts = np.bincount(labels.ravel())

    valid_ids = np.where(
        (counts >= MIN_PIXELS)
        & (counts <= MAX_PIXELS)
    )[0]

    valid_ids = valid_ids[valid_ids != 0]

    objects = ndimage.find_objects(labels)

    for label_id in valid_ids:

        obj = objects[label_id - 1]

        if obj is None:
            continue

        y_slice, x_slice = obj

        # Edge filtering
        if (
            x_slice.start < EDGE_MARGIN
            or x_slice.stop >= difference.shape[1] - EDGE_MARGIN
            or y_slice.start < EDGE_MARGIN
            or y_slice.stop >= difference.shape[0] - EDGE_MARGIN
        ):
            continue

        local_labels = labels[obj]
        local_mask = local_labels == label_id

        yy_local, xx_local = np.where(local_mask)

        yy = yy_local + y_slice.start
        xx = xx_local + x_slice.start

        values = significance[yy, xx]

        if len(values) == 0:
            continue

        weights = np.abs(values)

        x_centroid = np.average(xx, weights=weights)
        y_centroid = np.average(yy, weights=weights)

        peak_index = np.argmax(weights)
        peak_snr = values[peak_index]

        ra, dec = wcs_a.pixel_to_world_values(
            x_centroid,
            y_centroid
        )

        detections.append({
            "type": change_type,
            "x": float(x_centroid),
            "y": float(y_centroid),
            "ra_deg": float(ra),
            "dec_deg": float(dec),
            "peak_snr": float(peak_snr),
            "abs_peak_snr": float(abs(peak_snr)),
            "pixels": int(len(xx)),
        })

detections.sort(
    key=lambda x: x["abs_peak_snr"],
    reverse=True
)

detections = detections[:MAX_CANDIDATES]

print("5/5 Saving results...")

with open(
    "change_candidates.csv",
    "w",
    newline="",
    encoding="utf-8"
) as csvfile:

    fieldnames = [
        "candidate_id",
        "type",
        "ra_deg",
        "dec_deg",
        "x",
        "y",
        "peak_snr",
        "pixels",
    ]

    writer = csv.DictWriter(
        csvfile,
        fieldnames=fieldnames
    )

    writer.writeheader()

    for i, candidate in enumerate(detections, start=1):

        writer.writerow({
            "candidate_id": f"CAND-{i:03d}",
            "type": candidate["type"],
            "ra_deg": candidate["ra_deg"],
            "dec_deg": candidate["dec_deg"],
            "x": candidate["x"],
            "y": candidate["y"],
            "peak_snr": candidate["peak_snr"],
            "pixels": candidate["pixels"],
        })

vmin, vmax = np.nanpercentile(
    difference[valid],
    [1, 99]
)

fig, ax = plt.subplots(figsize=(10, 10))

ax.imshow(
    difference,
    origin="lower",
    cmap="gray",
    vmin=vmin,
    vmax=vmax
)

for i, candidate in enumerate(detections[:50], start=1):

    circle = Circle(
        (candidate["x"], candidate["y"]),
        radius=15,
        fill=False
    )

    ax.add_patch(circle)

    ax.text(
        candidate["x"] + 16,
        candidate["y"] + 16,
        str(i),
        fontsize=7
    )

ax.set_title("SPHEREx Significant Change Candidates")
ax.set_xlabel("X pixel")
ax.set_ylabel("Y pixel")

plt.tight_layout()
plt.savefig("change_candidates.png", dpi=180)
plt.show()

print()
print("DONE")
print("Total candidates:", len(detections))
print("Created:")
print(" change_significance.fits")
print(" change_candidates.csv")
print(" change_candidates.png")

print()
print("Top candidates:")

for i, c in enumerate(detections[:10], start=1):
    print(
        f"{i:02d} | {c['type']} | "
        f"RA={c['ra_deg']:.6f} | "
        f"Dec={c['dec_deg']:.6f} | "
        f"SNR={c['peak_snr']:.2f}"
    )