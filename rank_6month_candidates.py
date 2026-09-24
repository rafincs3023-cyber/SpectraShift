import csv, subprocess, os
from pathlib import Path
from astropy.io import fits
from astropy.wcs import WCS
from astropy.coordinates import SkyCoord
import astropy.units as u

ROOT = Path(r"C:\SPHEREx_Data_Processing")
AWS = r"C:\Program Files\Amazon\AWSCLIV2\aws.exe"
BUCKET = "s3://nasa-irsa-spherex/"
RA, DEC = 155.352, -42.700

OLD = ROOT / "level2_2025W19_2B_0166_3D3_spx_l2b-v20-2025-247.fits"

rows = list(csv.DictReader(open(ROOT / "W45_target_matches.csv", encoding="utf-8")))

print("Downloading missing candidate FITS files...")

for r in rows:
    key = r["key"]
    name = Path(key).name
    dest = ROOT / name

    if dest.exists():
        print("Already exists:", name)
        continue

    print("Downloading:", name)

    subprocess.run([
        AWS, "s3", "cp",
        BUCKET + key,
        str(dest),
        "--no-sign-request",
        "--region", "us-east-1"
    ], check=True)

target = SkyCoord(RA*u.deg, DEC*u.deg, frame="icrs")

def measure(path):
    with fits.open(path) as h:
        hdr = h["IMAGE"].header

        spatial = WCS(hdr)
        x, y = spatial.world_to_pixel(target)

        # Round-trip spatial verification
        back = spatial.pixel_to_world(x, y)
        sep_arcsec = target.separation(back).arcsec

        spectral = WCS(header=hdr, fobj=h, key="W")
        spectral.sip = None

        wavelength, bandwidth = spectral.pixel_to_world(x, y)

        return {
            "date": hdr["DATE-OBS"],
            "mjd": float(hdr["MJD-OBS"]),
            "x": float(x),
            "y": float(y),
            "wave": float(wavelength.to_value(u.um)),
            "bw": float(bandwidth.to_value(u.um)),
            "roundtrip_arcsec": float(sep_arcsec),
            "file": path.name
        }

old = measure(OLD)
print("\nOLD WAVELENGTH:", f'{old["wave"]:.6f} um')

results = []

for r in rows:
    p = ROOT / Path(r["key"]).name
    m = measure(p)

    m["wave_delta"] = abs(m["wave"] - old["wave"])
    m["time_gap"] = m["mjd"] - old["mjd"]
    results.append(m)

results.sort(key=lambda x: (x["wave_delta"], abs(x["time_gap"] - 183.0)))

print("\n============================================================")
print("RANKED BY WAVELENGTH MATCH")
print("============================================================")

for i, r in enumerate(results, 1):
    print(f"\n#{i}")
    print("DATE       :", r["date"])
    print("TIME GAP   :", f'{r["time_gap"]:.6f} days')
    print("WAVELENGTH :", f'{r["wave"]:.6f} um')
    print("WAVE DELTA :", f'{r["wave_delta"]:.6f} um')
    print("BANDWIDTH  :", f'{r["bw"]:.6f} um')
    print("ROUNDTRIP  :", f'{r["roundtrip_arcsec"]:.6f} arcsec')
    print("FILE       :", r["file"])
