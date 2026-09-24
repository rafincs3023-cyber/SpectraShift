from astropy.io import fits
from astropy.wcs import WCS, NoConvergence
from astropy.coordinates import SkyCoord
import astropy.units as u
import numpy as np

RA, DEC = 155.352, -42.700

files = [
    ("JUNE",
     r"C:\SPHEREx_Data_Processing\level2_2025W25_1B_0049_3D3_spx_l2b-v20-2025-253.fits"),
    ("DEC",
     r"C:\SPHEREx_Data_Processing\level2_2025W51_1A_0594_3D3_spx_l2b-v21-2025-354.fits")
]

results = []

for label, path in files:
    with fits.open(path) as h:
        hdr = h["IMAGE"].header

        spatial = WCS(hdr)

        try:
            p = spatial.all_world2pix(
                np.array([[RA, DEC]]),
                0,
                tolerance=1e-8,
                maxiter=100,
                adaptive=False,
                detect_divergence=True,
                quiet=False
            )[0]
            x, y = float(p[0]), float(p[1])
            converged = True
        except NoConvergence as e:
            x, y = map(float, e.best_solution[0])
            converged = False

        nx, ny = hdr["NAXIS1"], hdr["NAXIS2"]
        inside = 0 <= x < nx and 0 <= y < ny

        back = spatial.pixel_to_world(x, y)
        target = SkyCoord(RA*u.deg, DEC*u.deg)
        roundtrip = target.separation(back).arcsec

        sw = WCS(header=hdr, fobj=h, key="W")
        sw.sip = None
        wl, bw = sw.pixel_to_world(x, y)

        wl = float(wl.to_value(u.um))
        bw = float(bw.to_value(u.um))

        result = {
            "label": label,
            "mjd": float(hdr["MJD-OBS"]),
            "wave": wl,
            "bw": bw
        }
        results.append(result)

        print("\n==========================")
        print(label)
        print("DATE-OBS   :", hdr.get("DATE-OBS"))
        print("MJD-OBS    :", hdr.get("MJD-OBS"))
        print("OBSID      :", hdr.get("OBSID"))
        print("DETECTOR   :", hdr.get("DETECTOR"))
        print("VERSION    :", hdr.get("VERSION"))
        print("BUNIT      :", hdr.get("BUNIT"))
        print("PSF_FWHM   :", hdr.get("PSF_FWHM"))
        print("PIXEL      :", f"{x:.3f}, {y:.3f}")
        print("WCS CONVERGED:", converged)
        print("INSIDE     :", inside)
        print("ROUNDTRIP  :", f"{roundtrip:.6f} arcsec")
        print("WAVELENGTH :", f"{wl:.6f} um")
        print("BANDWIDTH  :", f"{bw:.6f} um")

a, b = results

print("\n==========================")
print("FINAL COMPARISON")
print("TIME GAP       :", f"{b['mjd']-a['mjd']:.6f} days")
print("WAVE DELTA     :", f"{abs(b['wave']-a['wave']):.6f} um")
print("MEAN BANDWIDTH :", f"{(a['bw']+b['bw'])/2:.6f} um")
print("DELTA/BW       :", f"{abs(b['wave']-a['wave'])/((a['bw']+b['bw'])/2):.3f}")
