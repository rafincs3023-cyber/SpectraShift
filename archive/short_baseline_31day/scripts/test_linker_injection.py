"""
Injection-recovery test for three_epoch_compare.py (moving-source
sensitivity of the linker + stationary-source veto).

Synthetic linearly-moving point sources (pixel-integrated Gaussian PSF,
FWHM = header PSF_FWHM) are added to IN-MEMORY copies of the A/C/B images
(the FITS files are never modified), the complete detection -> linking ->
veto pipeline is run on them, and each injected track is looked up in the
accepted and rejected outputs. Outputs use the prefix "injection_" so the
real pipeline outputs are untouched.

    python test_linker_injection.py
"""

import json
import os
import subprocess
import sys

import numpy as np
import pandas as pd
from astropy.coordinates import SkyCoord
from astropy.io import fits
from astropy.wcs import WCS
import astropy.units as u

FILES = {
    "A": "level2_2025W19_2B_0166_3D3_spx_l2b-v20-2025-247.fits",
    "C": "level2_2025W22_1B_0226_1D3_spx_l2b-v20-2025-250.fits",
    "B": "level2_2025W24_1A_0099_1D3_spx_l2b-v20-2025-252.fits",
}
N_INJECT = 150
RATE_RANGE = (1.0, 3.8)        # "/day -> 31 d A-B motion ~31-118", inside the linker's 5-120" window
FLUX_RANGE = (3.0, 30.0)       # aperture-flux units, spans the previous candidates (1.3-24)
MATCH_ARCSEC = 2.0
PREFIX = "data/injection_test/"  # prepended to every linker output path
SEED = 7

os.makedirs(PREFIX, exist_ok=True)
rng = np.random.default_rng(SEED)
wcs, valid, mjd = {}, {}, {}
for e, f in FILES.items():
    with fits.open(f) as h:
        wcs[e] = WCS(h["IMAGE"].header)
        valid[e] = np.isfinite(h["IMAGE"].data)
        mjd[e] = float(h["IMAGE"].header["MJD-OBS"])
frac = (mjd["C"] - mjd["A"]) / (mjd["B"] - mjd["A"])
dt = mjd["B"] - mjd["A"]


def covered(e, ra, dec, margin=10):
    x, y = (float(v) for v in wcs[e].world_to_pixel_values(ra, dec))
    xi, yi = int(round(x)), int(round(y))
    h, w = valid[e].shape
    return margin <= xi < w - margin and margin <= yi < h - margin and bool(valid[e][yi, xi])


ra0, dec0 = (float(v) for v in wcs["A"].pixel_to_world_values(1020, 1020))
tracks = []
while len(tracks) < N_INJECT:
    ra_a = ra0 + rng.uniform(-1.5, 1.5) / np.cos(np.radians(dec0))
    dec_a = dec0 + rng.uniform(-1.5, 1.5)
    rate = rng.uniform(*RATE_RANGE)
    pa = rng.uniform(0, 360)
    motion = rate * dt / 3600.0
    ra_b = ra_a + motion * np.sin(np.radians(pa)) / np.cos(np.radians(dec_a))
    dec_b = dec_a + motion * np.cos(np.radians(pa))
    ra_c, dec_c = ra_a + frac * (ra_b - ra_a), dec_a + frac * (dec_b - dec_a)
    if not all(covered(e, r, d) for e, r, d in (("A", ra_a, dec_a), ("C", ra_c, dec_c), ("B", ra_b, dec_b))):
        continue
    flux = float(np.exp(rng.uniform(np.log(FLUX_RANGE[0]), np.log(FLUX_RANGE[1]))))
    tracks.append({"ra_A": ra_a, "dec_A": dec_a, "ra_C": ra_c, "dec_C": dec_c, "ra_B": ra_b, "dec_B": dec_b,
                   "flux": flux, "rate": rate})
tracks = pd.DataFrame(tracks)

inject = {e: [{"ra": r[f"ra_{e}"], "dec": r[f"dec_{e}"], "flux": r["flux"]} for _, r in tracks.iterrows()]
          for e in "ACB"}
with open(PREFIX + "sources.json", "w", encoding="utf-8") as f:
    json.dump(inject, f)

env = dict(os.environ, SPHEREX_INJECT_JSON=PREFIX + "sources.json", SPHEREX_OUTPUT_PREFIX=PREFIX)
print(f"Running the full linker on images with {N_INJECT} injected movers ...", flush=True)
subprocess.run([sys.executable, "three_epoch_compare.py"], env=env, check=True,
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

acc = pd.read_csv(PREFIX + "three_epoch_motion_candidates.csv")
rej = pd.read_csv(PREFIX + "rejected_three_epoch_tracks.csv")


def lookup(table, tr):
    if len(table) == 0:
        return None
    ok = np.ones(len(table), dtype=bool)
    for e in "ACB":
        c1 = SkyCoord(table[f"{e}_ra"].values * u.deg, table[f"{e}_dec"].values * u.deg)
        ok &= c1.separation(SkyCoord(tr[f"ra_{e}"] * u.deg, tr[f"dec_{e}"] * u.deg)).arcsec < MATCH_ARCSEC
    return table[ok].iloc[0] if ok.any() else None


outcome = []
for _, tr in tracks.iterrows():
    a = lookup(acc, tr)
    r = lookup(rej, tr) if a is None else None
    outcome.append("RECOVERED" if a is not None else (r["rejection_reason"] if r is not None else "NOT_LINKED"))
tracks["outcome"] = outcome
tracks.to_csv(PREFIX + "results.csv", index=False)

n = len(tracks)
counts = tracks["outcome"].value_counts().to_dict()
print("\nInjection-recovery summary")
print(f"  injected tracks: {n}")
for k, v in sorted(counts.items()):
    print(f"  {k:<24} {v:>4}  ({v / n:.1%})")
linked = tracks[tracks["outcome"] != "NOT_LINKED"]
if len(linked):
    vetoed = (linked["outcome"] != "RECOVERED").mean()
    print(f"  of the tracks the linker formed, fraction vetoed: {vetoed:.1%}")
bins = [3, 5, 8, 12, 20, 30.01]
tracks["flux_bin"] = pd.cut(tracks["flux"], bins)
print("\n  recovery by injected flux:")
print(tracks.groupby("flux_bin", observed=True)["outcome"].apply(lambda s: f"{(s == 'RECOVERED').mean():.0%} of {len(s)}").to_string())
extra = len(acc) - (tracks["outcome"] == "RECOVERED").sum()
print(f"\n  accepted candidates not matching any injected track: {extra}")
