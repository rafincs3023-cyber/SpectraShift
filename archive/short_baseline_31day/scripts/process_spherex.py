from astropy.io import fits
from astropy.wcs import WCS
from reproject import reproject_interp
import numpy as np
import matplotlib.pyplot as plt

file_a = "level2_2025W19_2B_0166_3D3_spx_l2b-v20-2025-247.fits"
file_b = "level2_2025W24_1A_0099_1D3_spx_l2b-v20-2025-252.fits"

# Load Observation A
with fits.open(file_a) as hdul:
    image_a = hdul["IMAGE"].data.astype(float)
    header_a = hdul["IMAGE"].header.copy()

# Load Observation B
with fits.open(file_b) as hdul:
    image_b = hdul["IMAGE"].data.astype(float)
    header_b = hdul["IMAGE"].header.copy()

# Align B onto A using sky coordinates
aligned_b, footprint = reproject_interp(
    (image_b, WCS(header_b)),
    WCS(header_a),
    shape_out=image_a.shape
)

# Only compare pixels present in both observations
valid = (
    np.isfinite(image_a)
    & np.isfinite(aligned_b)
    & (footprint > 0)
)

difference = np.full(image_a.shape, np.nan)
difference[valid] = image_a[valid] - aligned_b[valid]

# Save scientific results
fits.writeto(
    "observation_B_aligned.fits",
    aligned_b,
    header_a,
    overwrite=True
)

fits.writeto(
    "difference_A_minus_B.fits",
    difference,
    header_a,
    overwrite=True
)

# Display limits
a_min, a_max = np.nanpercentile(image_a[valid], [1, 99])
b_min, b_max = np.nanpercentile(aligned_b[valid], [1, 99])
d_min, d_max = np.nanpercentile(difference[valid], [1, 99])

fig, ax = plt.subplots(1, 3, figsize=(15, 5))

ax[0].imshow(image_a, origin="lower", cmap="gray", vmin=a_min, vmax=a_max)
ax[0].set_title("Observation A")

ax[1].imshow(aligned_b, origin="lower", cmap="gray", vmin=b_min, vmax=b_max)
ax[1].set_title("Observation B (Aligned)")

ax[2].imshow(difference, origin="lower", cmap="gray", vmin=d_min, vmax=d_max)
ax[2].set_title("A - B Difference")

plt.tight_layout()
plt.savefig("spherex_comparison.png", dpi=150)
plt.show()

print("Alignment completed.")
print("Valid overlapping pixels:", np.sum(valid))
print("Created:")
print("  observation_B_aligned.fits")
print("  difference_A_minus_B.fits")
print("  spherex_comparison.png")