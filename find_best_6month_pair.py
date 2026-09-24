import csv, re, logging
from concurrent.futures import ThreadPoolExecutor, as_completed

import astropy.units as u
from astropy.io import fits
from astropy.wcs import WCS
from astropy.coordinates import SkyCoord
from astropy.utils.data import conf

logging.getLogger("astropy").setLevel(logging.ERROR)
conf.remote_timeout = 120

RA, DEC = 155.352, -42.700
TARGET = SkyCoord(RA*u.deg, DEC*u.deg, frame="icrs")

rows = list(csv.DictReader(open(
    "target_D3_all.csv", encoding="utf-8"
)))

def process(row):
    uri = row["uri"].strip()

    url = (
        "https://irsa.ipac.caltech.edu/" + uri +
        f"?center={RA},{DEC}d&size=0.01"
    )

    try:
        with fits.open(url, cache=False) as h:
            hdr = h["IMAGE"].header

            spatial = WCS(hdr)
            x, y = spatial.world_to_pixel(TARGET)

            spectral = WCS(hdr, fobj=h, key="W")
            spectral.sip = None

            wl, bw = spectral.pixel_to_world(x, y)

            version = re.search(r"(l2b-v\d+)", uri)
            version = version.group(1) if version else ""

            return {
                "uri": uri,
                "mjd": float(row["time_bounds_lower"]),
                "date": hdr.get("DATE-OBS", ""),
                "wave": float(wl.to_value(u.um)),
                "bw": float(bw.to_value(u.um)),
                "version": version,
                "obsid": hdr.get("OBSID", "")
            }

    except Exception as e:
        return None

results = []

print("Scanning IRSA D3 cutouts...")

with ThreadPoolExecutor(max_workers=8) as ex:
    fs = [ex.submit(process, r) for r in rows]

    for i, f in enumerate(as_completed(fs), 1):
        r = f.result()
        if r:
            results.append(r)

        if i % 20 == 0:
            print(f"{i}/{len(fs)} checked | valid={len(results)}")

results.sort(key=lambda x: x["mjd"])

with open("target_D3_wavelengths.csv", "w",
          newline="", encoding="utf-8") as f:
    fields = ["date","mjd","wave","bw","version","obsid","uri"]
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    w.writerows(results)

pairs = []

for i in range(len(results)):
    for j in range(i+1, len(results)):

        a = results[i]
        b = results[j]

        gap = b["mjd"] - a["mjd"]

        # ~6-month window
        if not (175 <= gap <= 190):
            continue

        wave_delta = abs(b["wave"] - a["wave"])
        mean_bw = (a["bw"] + b["bw"]) / 2
        ratio = wave_delta / mean_bw

        pairs.append({
            "A": a,
            "B": b,
            "gap": gap,
            "wave_delta": wave_delta,
            "mean_bw": mean_bw,
            "ratio": ratio,
            "same_version": a["version"] == b["version"]
        })

pairs.sort(key=lambda p: (
    p["ratio"],
    abs(p["gap"] - 182.62)
))

print("\n========================================")
print("BEST ~6-MONTH WAVELENGTH-MATCHED PAIRS")
print("========================================")

for n, p in enumerate(pairs[:15], 1):
    a, b = p["A"], p["B"]

    print(f"\n#{n}")
    print("A DATE       :", a["date"])
    print("B DATE       :", b["date"])
    print("TIME GAP     :", f'{p["gap"]:.6f} days')

    print("A WAVELENGTH :", f'{a["wave"]:.6f} um')
    print("B WAVELENGTH :", f'{b["wave"]:.6f} um')

    print("WAVE DELTA   :", f'{p["wave_delta"]:.6f} um')
    print("MEAN BW      :", f'{p["mean_bw"]:.6f} um')
    print("DELTA/BW     :", f'{p["ratio"]:.4f}')

    print("A VERSION    :", a["version"])
    print("B VERSION    :", b["version"])
    print("SAME VERSION :", p["same_version"])

    print("A FILE       :", a["uri"].split("/")[-1])
    print("B FILE       :", b["uri"].split("/")[-1])

print("\nSaved: target_D3_wavelengths.csv")
