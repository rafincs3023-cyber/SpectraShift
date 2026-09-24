import csv

r = list(csv.DictReader(open("target_D3_wavelengths.csv", encoding="utf-8")))
r.sort(key=lambda x: float(x["mjd"]))

pairs = []

for i in range(len(r)):
    for j in range(i+1, len(r)):
        a, b = r[i], r[j]
        gap = float(b["mjd"]) - float(a["mjd"])

        if 175 <= gap <= 190:
            wa, wb = float(a["wave"]), float(b["wave"])
            bwa, bwb = float(a["bw"]), float(b["bw"])

            d = abs(wb-wa)
            mbw = (bwa+bwb)/2
            ratio = d/mbw

            pairs.append((ratio, abs(gap-182.62), gap, d, mbw, a, b))

pairs.sort()

for n,p in enumerate(pairs[:5],1):
    ratio,_,gap,d,mbw,a,b = p

    print(f"\n#{n}")
    print("A DATE       :", a["date"])
    print("B DATE       :", b["date"])
    print("TIME GAP     :", f"{gap:.6f} days")
    print("A WAVELENGTH :", f'{float(a["wave"]):.6f} um')
    print("B WAVELENGTH :", f'{float(b["wave"]):.6f} um')
    print("WAVE DELTA   :", f"{d:.6f} um")
    print("MEAN BW      :", f"{mbw:.6f} um")
    print("DELTA/BW     :", f"{ratio:.4f}")
    print("A VERSION    :", a["version"])
    print("B VERSION    :", b["version"])
    print("A FILE       :", a["uri"].split("/")[-1])
    print("B FILE       :", b["uri"].split("/")[-1])
