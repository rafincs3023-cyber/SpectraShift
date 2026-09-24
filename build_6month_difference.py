from pathlib import Path
import json
import numpy as np

from astropy.io import fits
from astropy.wcs import WCS
from astropy.coordinates import SkyCoord
import astropy.units as u
from reproject import reproject_interp

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(r"C:\SPHEREx_Data_Processing")

A_FILE = ROOT / "level2_2025W25_1B_0652_1D3_spx_l2b-v20-2025-253.fits"
B_FILE = ROOT / "level2_2025W51_1A_0594_2D3_spx_l2b-v21-2025-354.fits"

OUT = ROOT / "data" / "time_compare_6month"
OUT.mkdir(parents=True, exist_ok=True)

RA, DEC = 155.352, -42.700
TARGET = SkyCoord(RA*u.deg, DEC*u.deg, frame="icrs")


def load(path):
    h = fits.open(path)

    ih = h["IMAGE"].header
    data = np.asarray(h["IMAGE"].data, dtype=np.float32)

    w = WCS(ih).celestial

    x, y = w.world_to_pixel(TARGET)
    back = w.pixel_to_world(x, y)
    roundtrip = TARGET.separation(back).arcsec

    sw = WCS(ih, fobj=h, key="W")
    sw.sip = None
    wl, bw = sw.pixel_to_world(x, y)

    return {
        "hdul": h,
        "header": ih,
        "data": data,
        "wcs": w,
        "x": float(x),
        "y": float(y),
        "roundtrip": float(roundtrip),
        "wave": float(wl.to_value(u.um)),
        "bw": float(bw.to_value(u.um)),
        "mjd": float(ih["MJD-OBS"]),
        "date": ih["DATE-OBS"],
        "bunit": str(ih.get("BUNIT", "")),
        "psf": float(ih.get("PSF_FWHM", np.nan))
    }


A = load(A_FILE)
B = load(B_FILE)

gap = B["mjd"] - A["mjd"]
wave_delta = abs(B["wave"] - A["wave"])
mean_bw = (A["bw"] + B["bw"]) / 2
ratio = wave_delta / mean_bw

print("\n===== FINAL PRE-CHECK =====")
print("A:", A["date"])
print("B:", B["date"])
print("TIME GAP:", f"{gap:.6f} days")
print("A wavelength:", f'{A["wave"]:.6f} um')
print("B wavelength:", f'{B["wave"]:.6f} um')
print("DELTA/BW:", f"{ratio:.4f}")
print("A roundtrip:", f'{A["roundtrip"]:.8f} arcsec')
print("B roundtrip:", f'{B["roundtrip"]:.8f} arcsec')
print("A PSF:", A["psf"])
print("B PSF:", B["psf"])

# Strict safety checks
assert 175 <= gap <= 190, "FAIL: not a ~6-month pair"
assert ratio < 0.25, "FAIL: wavelength mismatch too large"
assert A["roundtrip"] < 1.0
assert B["roundtrip"] < 1.0
assert A["bunit"] == B["bunit"], "FAIL: BUNIT mismatch"

if np.isfinite(A["psf"]) and np.isfinite(B["psf"]):
    assert abs(A["psf"] - B["psf"]) < 0.15, "FAIL: PSF mismatch"

print("\nChecks PASS. Reprojecting B -> A WCS...")

# Align later epoch B onto earlier epoch A grid
B_aligned, footprint = reproject_interp(
    (B["data"], B["wcs"]),
    A["wcs"],
    shape_out=A["data"].shape,
    order="bilinear",
    return_footprint=True
)

B_aligned = np.asarray(B_aligned, dtype=np.float32)

valid = (
    np.isfinite(A["data"]) &
    np.isfinite(B_aligned) &
    (footprint > 0.5)
)

if not np.any(valid):
    raise RuntimeError("FAIL: epochs have no valid common overlap")

# Verify target itself survives reprojection
tx, ty = A["wcs"].world_to_pixel(TARGET)
tx = float(np.asarray(tx).squeeze())
ty = float(np.asarray(ty).squeeze())
txi, tyi = int(round(tx)), int(round(ty))

assert 0 <= txi < valid.shape[1]
assert 0 <= tyi < valid.shape[0]
assert valid[tyi, txi], "FAIL: target coordinate not in common overlap"

# Difference conventions
# B-A: positive = brighter in later epoch
diff_BA = np.full_like(A["data"], np.nan, dtype=np.float32)
diff_BA[valid] = B_aligned[valid] - A["data"][valid]

# A-B also saved because existing Compare UI may use A-B convention
diff_AB = np.full_like(A["data"], np.nan, dtype=np.float32)
diff_AB[valid] = A["data"][valid] - B_aligned[valid]

# Crop to common overlap
ys, xs = np.where(valid)
x0, x1 = xs.min(), xs.max()+1
y0, y1 = ys.min(), ys.max()+1

A_crop = A["data"][y0:y1, x0:x1]
B_crop = B_aligned[y0:y1, x0:x1]
BA_crop = diff_BA[y0:y1, x0:x1]
AB_crop = diff_AB[y0:y1, x0:x1]
mask_crop = valid[y0:y1, x0:x1]

crop_wcs = A["wcs"].slice(
    (slice(y0, y1), slice(x0, x1))
)

hdr = crop_wcs.to_header(relax=True)
hdr["BUNIT"] = A["bunit"]
hdr["DATEA"] = A["date"]
hdr["DATEB"] = B["date"]
hdr["GAPDAYS"] = gap
hdr["WAVEA"] = A["wave"]
hdr["WAVEB"] = B["wave"]
hdr["WDELTA"] = wave_delta
hdr["RA_TARG"] = RA
hdr["DEC_TARG"] = DEC

def save_fits(name, data, difftype=None):
    h = hdr.copy()
    if difftype:
        h["DIFFTYPE"] = difftype
    fits.PrimaryHDU(
        data=np.asarray(data, dtype=np.float32),
        header=h
    ).writeto(OUT / name, overwrite=True)

save_fits("epoch_A_2025-06-19.fits", A_crop)
save_fits("epoch_B_2025-12-17_aligned.fits", B_crop)
save_fits("difference_B_minus_A.fits", BA_crop, "B-A")
save_fits("difference_A_minus_B.fits", AB_crop, "A-B")

fits.PrimaryHDU(
    data=mask_crop.astype(np.uint8),
    header=hdr
).writeto(OUT / "overlap_mask.fits", overwrite=True)

# Same intensity scale for A and B previews
combined = np.concatenate([
    A_crop[mask_crop],
    B_crop[mask_crop]
])

lo, hi = np.nanpercentile(combined, [1, 99])

def save_epoch_png(data, name, title):
    plt.figure(figsize=(9, 8))
    plt.imshow(data, origin="lower", cmap="gray", vmin=lo, vmax=hi)
    plt.title(title)
    plt.xlabel("X pixel")
    plt.ylabel("Y pixel")
    plt.colorbar(label=A["bunit"])
    plt.tight_layout()
    plt.savefig(OUT / name, dpi=180)
    plt.close()

save_epoch_png(
    A_crop,
    "epoch_A.png",
    "SPHEREx Epoch A — 2025-06-19"
)

save_epoch_png(
    B_crop,
    "epoch_B_aligned.png",
    "SPHEREx Epoch B — 2025-12-17 (Aligned to A)"
)

# Symmetric scale for difference
dv = np.abs(BA_crop[np.isfinite(BA_crop)])
lim = np.nanpercentile(dv, 99) if len(dv) else 1

plt.figure(figsize=(9, 8))
plt.imshow(
    BA_crop,
    origin="lower",
    cmap="RdBu_r",
    vmin=-lim,
    vmax=lim
)
plt.title("SPHEREx ~6-Month Difference — B − A")
plt.xlabel("X pixel")
plt.ylabel("Y pixel")
plt.colorbar(label=A["bunit"])
plt.tight_layout()
plt.savefig(OUT / "difference_B_minus_A.png", dpi=180)
plt.close()

metadata = {
    "target": {"ra_deg": RA, "dec_deg": DEC},
    "epoch_A": {
        "date": A["date"],
        "file": A_FILE.name,
        "wavelength_um": A["wave"]
    },
    "epoch_B": {
        "date": B["date"],
        "file": B_FILE.name,
        "wavelength_um": B["wave"]
    },
    "time_gap_days": gap,
    "wavelength_delta_um": wave_delta,
    "delta_over_bandwidth": ratio,
    "difference_primary": "B-A",
    "difference_meaning": "positive values mean brighter in the later epoch",
    "crop": {
        "x0": int(x0), "x1": int(x1),
        "y0": int(y0), "y1": int(y1),
        "width": int(x1-x0),
        "height": int(y1-y0)
    }
}

with open(OUT / "metadata.json", "w", encoding="utf-8") as f:
    json.dump(metadata, f, indent=2)

A["hdul"].close()
B["hdul"].close()

print("\n===================================")
print("SUCCESS: ~6-MONTH DIFFERENCE BUILT")
print("===================================")
print("TIME GAP :", f"{gap:.6f} days")
print("WAVE Δ   :", f"{wave_delta:.6f} um")
print("Δ/BW     :", f"{ratio:.4f}")
print("CROP     :", f"{x1-x0} x {y1-y0} pixels")
print("OUTPUT   :", OUT)
print()
print("Created:")
for p in sorted(OUT.iterdir()):
    print(" -", p.name)

