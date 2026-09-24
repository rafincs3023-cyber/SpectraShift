from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote
import http.client, threading, time, csv, math, warnings

from astropy.io import fits
from astropy.wcs import WCS
from astropy.wcs import FITSFixedWarning

warnings.simplefilter("ignore", FITSFixedWarning)

RA = 155.352
DEC = -42.700

# Epoch A = 2025-05-09T13:57:35.710
# Exact 6 calendar months later = 2025-11-09T13:57:35.710
TARGET_MJD = 60988.58166331

HOST = "nasa-irsa-spherex.s3.us-east-1.amazonaws.com"
RANGE = "bytes=0-65535"
tls = threading.local()

def connection():
    if not hasattr(tls, "conn"):
        tls.conn = http.client.HTTPSConnection(HOST, timeout=20)
    return tls.conn

def reset_connection():
    try:
        tls.conn.close()
    except:
        pass
    if hasattr(tls, "conn"):
        del tls.conn

def get_first_64k(key):
    path = "/" + quote(key, safe="/")
    last = None

    for attempt in range(3):
        try:
            c = connection()
            c.request("GET", path, headers={
                "Range": RANGE,
                "Connection": "keep-alive"
            })
            r = c.getresponse()

            if r.status != 206:
                r.read()
                raise RuntimeError(f"HTTP {r.status}")

            return r.read()

        except Exception as e:
            last = e
            reset_connection()
            time.sleep(0.4 * (attempt + 1))

    raise last

def read_header(data, offset):
    cards = []
    p = offset

    while p + 80 <= len(data):
        card = data[p:p+80].decode("ascii", errors="replace")
        cards.append(card)
        p += 80

        if card[:8].strip() == "END":
            next_offset = ((p + 2879) // 2880) * 2880
            header = fits.Header.fromstring("".join(cards), sep="")
            return header, next_offset

    raise RuntimeError("Header END not found in first 64 KB")

def inspect(key):
    data = get_first_64k(key)

    primary, off = read_header(data, 0)

    if primary.get("NAXIS", 0) != 0:
        raise RuntimeError("Unexpected PRIMARY data")

    image, off2 = read_header(data, off)

    if image.get("EXTNAME") != "IMAGE":
        raise RuntimeError(f"Unexpected HDU1: {image.get('EXTNAME')}")

    w = WCS(image, relax=True).celestial
    x, y = w.world_to_pixel_values(RA, DEC)

    nx = int(image["NAXIS1"])
    ny = int(image["NAXIS2"])

    inside = (
        math.isfinite(x) and math.isfinite(y)
        and -0.5 <= x < nx - 0.5
        and -0.5 <= y < ny - 0.5
    )

    if not inside:
        return None

    mjd = float(image["MJD-OBS"])

    return {
        "key": key,
        "date_obs": image.get("DATE-OBS", ""),
        "mjd_obs": mjd,
        "delta_from_exact_6m_days": abs(mjd - TARGET_MJD),
        "x": x,
        "y": y,
        "crval1": image.get("CRVAL1"),
        "crval2": image.get("CRVAL2"),
    }

lines = Path("nov_D3_candidates.txt").read_text(
    encoding="utf-8", errors="ignore"
).splitlines()

keys = []

for line in lines:
    parts = line.strip().split(maxsplit=3)
    if len(parts) == 4:
        key = parts[3]
        if "/2025W45_" in key and "D3_" in key:
            keys.append(key)

print(f"W45 D3 headers to scan: {len(keys)}")
print("Target: RA 155.352, Dec -42.700")
print("Exact 6-month target MJD:", TARGET_MJD)

matches = []
errors = 0
done = 0

with ThreadPoolExecutor(max_workers=24) as ex:
    futures = {ex.submit(inspect, k): k for k in keys}

    for f in as_completed(futures):
        done += 1
        try:
            result = f.result()
            if result:
                matches.append(result)
        except Exception:
            errors += 1

        if done % 250 == 0:
            print(f"Checked {done}/{len(keys)} | matches={len(matches)} | errors={errors}")

matches.sort(key=lambda r: r["delta_from_exact_6m_days"])

with open("W45_target_matches.csv", "w", newline="", encoding="utf-8") as fp:
    fields = [
        "date_obs", "mjd_obs", "delta_from_exact_6m_days",
        "x", "y", "crval1", "crval2", "key"
    ]
    writer = csv.DictWriter(fp, fieldnames=fields)
    writer.writeheader()
    writer.writerows(matches)

print()
print("========================================")
print("W45 TARGET MATCHES:", len(matches))
print("HEADER ERRORS:", errors)
print("========================================")

for r in matches[:20]:
    print()
    print("DATE :", r["date_obs"])
    print("MJD  :", r["mjd_obs"])
    print("GAP  :", f'{r["delta_from_exact_6m_days"]:.6f} days from exact 6-month target')
    print("PIXEL:", f'{r["x"]:.2f}, {r["y"]:.2f}')
    print("FILE :", r["key"])

print()
print("Saved: W45_target_matches.csv")
