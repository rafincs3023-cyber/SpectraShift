from astropy.io import fits
from astropy.wcs import WCS
from astropy.coordinates import SkyCoord
import astropy.units as u

ra, dec = 155.352, -42.700
target = SkyCoord(ra=ra*u.deg, dec=dec*u.deg, frame="icrs")

files = [
    ("OLD", r"C:\SPHEREx_Data_Processing\level2_2025W19_2B_0166_3D3_spx_l2b-v20-2025-247.fits"),
    ("NEW", r"C:\SPHEREx_Data_Processing\level2_2025W45_2A_0494_3D3_spx_l2b-v20-2025-314.fits"),
]

results = []

for label, f in files:
    with fits.open(f) as h:
        hdr = h["IMAGE"].header

        spatial = WCS(hdr)
        x, y = spatial.world_to_pixel(target)

        spectral = WCS(header=hdr, fobj=h, key="W")
        spectral.sip = None

        wavelength, bandwidth = spectral.pixel_to_world(x, y)

        wl = float(wavelength.to_value(u.um))
        bw = float(bandwidth.to_value(u.um))
        mjd = float(hdr["MJD-OBS"])

        results.append((label, wl, bw, mjd))

        print("\n==============================")
        print(label)
        print("DATE-OBS   :", hdr.get("DATE-OBS"))
        print("MJD-OBS    :", mjd)
        print("DETECTOR   :", hdr.get("DETECTOR"))
        print("OBSID      :", hdr.get("OBSID"))
        print("TARGET PIX :", f"{x:.3f}, {y:.3f}")
        print("WAVELENGTH :", f"{wl:.6f} um")
        print("BANDWIDTH  :", f"{bw:.6f} um")

old = results[0]
new = results[1]

print("\n==============================")
print("COMPARISON")
print("TIME GAP         :", f"{new[3]-old[3]:.6f} days")
print("WAVELENGTH DELTA :", f"{abs(new[1]-old[1]):.6f} um")
print("OLD BANDWIDTH    :", f"{old[2]:.6f} um")
print("NEW BANDWIDTH    :", f"{new[2]:.6f} um")
