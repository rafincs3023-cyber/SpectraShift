from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote
from astropy.io import fits
from astropy.coordinates import SkyCoord
import astropy.units as u
import http.client, threading, time, csv

TARGET = SkyCoord(155.352*u.deg, -42.700*u.deg, frame="icrs")
HOST = "nasa-irsa-spherex.s3.us-east-1.amazonaws.com"
tls = threading.local()

def conn():
    if not hasattr(tls, "c"):
        tls.c = http.client.HTTPSConnection(HOST, timeout=20)
    return tls.c

def reset():
    try: tls.c.close()
    except: pass
    if hasattr(tls, "c"): del tls.c

def get_header(key):
    for attempt in range(3):
        try:
            c = conn()
            c.request("GET", "/" + quote(key, safe="/"),
                      headers={"Range":"bytes=0-65535"})
            r = c.getresponse()
            if r.status != 206:
                r.read()
                raise RuntimeError(r.status)
            data = r.read()
            break
        except:
            reset()
            time.sleep(.4*(attempt+1))
    else:
        return None

    # PRIMARY header
    p = 0
    while data[p:p+8].decode("ascii","ignore").strip() != "END":
        p += 80
    p += 80
    p = ((p+2879)//2880)*2880

    # IMAGE header
    cards = []
    while p+80 <= len(data):
        card = data[p:p+80].decode("ascii","replace")
        cards.append(card)
        p += 80
        if card[:8].strip() == "END":
            break

    return fits.Header.fromstring("".join(cards), sep="")

lines = Path("nov_D3_candidates.txt").read_text(
    encoding="utf-8", errors="ignore"
).splitlines()

keys = []
for line in lines:
    parts = line.split(maxsplit=3)
    if len(parts) == 4:
        keys.append(parts[3])

def inspect(key):
    h = get_header(key)
    if h is None:
        return None

    ra = h.get("CRVAL1")
    dec = h.get("CRVAL2")
    if ra is None or dec is None:
        return None

    center = SkyCoord(float(ra)*u.deg, float(dec)*u.deg)
    sep = TARGET.separation(center).deg

    # SPHEREx frame is only a few degrees across.
    # 4 deg is deliberately generous for shortlist.
    if sep > 4.0:
        return None

    return {
        "sep_deg": sep,
        "date_obs": h.get("DATE-OBS",""),
        "mjd_obs": h.get("MJD-OBS",""),
        "crval1": ra,
        "crval2": dec,
        "key": key
    }

matches = []

with ThreadPoolExecutor(max_workers=24) as ex:
    fs = [ex.submit(inspect,k) for k in keys]
    for i,f in enumerate(as_completed(fs),1):
        try:
            r = f.result()
            if r:
                matches.append(r)
        except:
            pass

        if i % 1000 == 0:
            print(f"Checked {i}/{len(keys)} | shortlist={len(matches)}")

matches.sort(key=lambda r: (
    abs(float(r["mjd_obs"]) - 60988.58166331),
    r["sep_deg"]
))

with open("nov_D3_real_shortlist.csv","w",newline="",encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=[
        "sep_deg","date_obs","mjd_obs","crval1","crval2","key"
    ])
    w.writeheader()
    w.writerows(matches)

print("\nREAL SKY-CENTER SHORTLIST:", len(matches))
for r in matches[:20]:
    print()
    print("DATE:", r["date_obs"])
    print("CENTER SEP:", f'{r["sep_deg"]:.4f} deg')
    print("FILE:", r["key"])
