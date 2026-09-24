from astropy.io import fits
from astropy.wcs import WCS
from astropy.coordinates import SkyCoord
import astropy.units as u
import numpy as np

RA, DEC = 155.352, -42.700
target = SkyCoord(RA*u.deg, DEC*u.deg)

files = [
("A", r"C:\SPHEREx_Data_Processing\level2_2025W25_1B_0652_1D3_spx_l2b-v20-2025-253.fits"),
("B", r"C:\SPHEREx_Data_Processing\level2_2025W51_1A_0594_2D3_spx_l2b-v21-2025-354.fits")
]

res=[]

for label,path in files:
    with fits.open(path) as h:
        ph = h[0].header
        ih = h["IMAGE"].header

        w = WCS(ih)
        x,y = w.world_to_pixel(target)
        back = w.pixel_to_world(x,y)
        sep = target.separation(back).arcsec

        sw = WCS(ih, fobj=h, key="W")
        sw.sip = None
        wl,bw = sw.pixel_to_world(x,y)

        wl=float(wl.to_value(u.um))
        bw=float(bw.to_value(u.um))

        print("\n====================")
        print(label)
        print("DATE-OBS :", ih.get("DATE-OBS"))
        print("MJD-OBS  :", ih.get("MJD-OBS"))
        print("OBSID    :", ih.get("OBSID"))
        print("DETECTOR :", ih.get("DETECTOR"))
        print("BUNIT    :", ih.get("BUNIT"))
        print("VERSION PRIMARY:", ph.get("VERSION"))
        print("VERSION IMAGE  :", ih.get("VERSION"))
        print("PIXEL    :", f"{x:.3f}, {y:.3f}")
        print("INSIDE   :", 0 <= x < ih["NAXIS1"] and 0 <= y < ih["NAXIS2"])
        print("ROUNDTRIP:", f"{sep:.8f} arcsec")
        print("WAVELENGTH:", f"{wl:.6f} um")
        print("BANDWIDTH :", f"{bw:.6f} um")
        print("PSF_FWHM  :", ih.get("PSF_FWHM"))

        print("\nCAL/VERSION RELATED HEADER:")
        for hdrname,hdr in [("PRIMARY",ph),("IMAGE",ih)]:
            for k in hdr:
                ku=k.upper()
                if any(s in ku for s in ["VERS","CAL","GAIN","DARK","PSF"]):
                    print(hdrname, k, "=", hdr[k])

        res.append((float(ih["MJD-OBS"]),wl,bw))

print("\n====================")
print("PAIR")
print("TIME GAP :", f"{res[1][0]-res[0][0]:.6f} days")
print("WAVE DELTA:", f"{abs(res[1][1]-res[0][1]):.6f} um")
print("DELTA/BW:", f"{abs(res[1][1]-res[0][1])/((res[0][2]+res[1][2])/2):.4f}")
