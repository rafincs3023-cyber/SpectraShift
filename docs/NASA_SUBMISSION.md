# SpectraShift — NASA Space Apps Submission Draft

**Challenge:** Planet X and SPHEREx
**Project:** SpectraShift — A SPHEREx Spectral & Multi-Epoch Sky Explorer

## Project summary
SpectraShift is a web application that lets anyone explore real NASA SPHEREx data across wavelength and across time. Spectral View presents all 102 SPHEREx near-infrared channels of one sky region with click-to-spectrum; Time Compare shows the same sky observed 181.8 days apart, pixel-registered, in five comparison modes; and a three-epoch moving-source pipeline searches for moving objects while rejecting stationary-star, blend and catalogue false positives. In the current data no candidate passes the checks, and SpectraShift explains why rather than claiming a discovery.

## Problem
Looking for faint, distant, slowly moving Solar System bodies requires comparing the same sky at different times. In crowded fields, most apparent motion is not real: unrelated stationary stars can be linked by chance, blended sources shift their centroids, and bright-star halos create spurious detections. SPHEREx adds 102 wavelengths per position, but its data products are large FITS files that are difficult for non-specialists to explore.

## Solution
- **Spectral View:** browse 102 channels (0.743–5.009 µm, detectors D1–D6) of a SPHEREx mosaic, see each channel's wavelength range, bandwidth and sky coverage, and click any position for its 102-channel spectrum.
- **Time Compare:** a verified pair of SPHEREx exposures from 2025-06-19 and 2025-12-17 (181.774 days apart, same detector D3, wavelengths within 0.0032 µm), registered onto one grid and cut to a fully valid common frame, viewable side by side, with a slider, blinking, as a B − A difference or as a colour overlay; plus a secondary 31-day, three-epoch set.
- **Candidate pipeline:** detection in three epochs, A → C → B linking, a calibrated stationary-source veto, a blend/bright-star-halo veto, trajectory validation and catalogue classification (Gaia DR3 propagated to each epoch, SIMBAD, JPL small-body search).

## NASA data used
- SPHEREx Level-2 spectral images and a 102-channel SPHEREx spectral mosaic, from NASA/IPAC IRSA (SPHEREx Quick Release, DOI 10.26131/IRSA652), including the official IRSA SPHEREx Mosaic Tool.
- JPL Small-Body Identification API and JPL Horizons (known asteroids, comets and planets, with positions computed from the SPHEREx spacecraft).
- Supporting non-NASA catalogues: ESA Gaia DR3 and CDS SIMBAD.

## How it works
1. An offline Python pipeline reads SPHEREx FITS files (Astropy, photutils, reproject).
2. The ~6-month pair is reprojected onto one WCS grid; the largest fully valid rectangle in the overlap mask becomes the common display frame; a B − A difference is computed.
3. The spectral mosaic's channel table and wavelength calibration are read directly from the FITS files; previews and spectra are served on demand.
4. For the motion search, sources are detected in three epochs, linked, and then tested in sky coordinates against an astrometric model calibrated from ~75,000 stationary source pairs. Tracks whose detections stay at the same position in other epochs, or that are built around blends and bright-star halos, are rejected with a recorded reason.
5. Surviving tracks are validated and classified against catalogues with epoch propagation and uncertainty-aware matching.
6. A read-only FastAPI backend serves PNG previews and JSON; a React interface presents everything. The browser never downloads FITS files.

## Technologies
React 19, TypeScript, Vite, React Router; Python, FastAPI, Uvicorn, NumPy, pandas, SciPy, Astropy, photutils, reproject, astroquery, Matplotlib, Pillow; pytest and oxlint.

## Innovation
- One interface for both of SPHEREx's dimensions — wavelength and time — with a clear distinction between them.
- A pixel-registered long-baseline comparison whose display frame is chosen from the actual overlap mask, so no invalid regions distort blink or difference views.
- A stationary-source and blend veto calibrated on the data itself, with a measured cost to sensitivity (≈10% of genuine movers) and an injection–recovery test (43% end-to-end recovery of synthetic movers).
- Catalogue checks that propagate Gaia positions to each observation epoch and compute small-body positions from the spacecraft's location.

## Impact
SpectraShift makes SPHEREx's spectral and multi-epoch data explorable in a browser for students, educators and citizen scientists, and demonstrates a transparent search workflow in which false positives are rejected and explained instead of being presented as discoveries.

## Challenges
- An earlier linker version produced 22 apparent motion candidates; careful checks showed each was a chain of unrelated stationary stars, caused by linking without a stationarity test and by detection gaps from SPHEREx's undersampled PSF. We fixed the root cause and withdrew them.
- Crowded fields and bright-star halos required new, measurable veto criteria.
- Some Solar System services (SkyBoT, MPC Checker) were unreachable; we used the JPL Small-Body Identification service as the equivalent search.
- Working with multi-gigabyte FITS mosaics required streaming reads and cached previews.

## Accomplishments
- All 102 SPHEREx channels browsable with click-to-spectrum.
- A verified 181.77-day registered comparison with five modes.
- A reproducible pipeline that rejects 725 of 725 false linked tracks with logged reasons, with its sensitivity measured rather than assumed.
- A tested backend (pytest suite) and a clean frontend build.

## Lessons learned
- In crowded fields, "no candidate" is a far more likely honest answer than a detection — and it needs to be measured and explained.
- Instrument details (an undersampled PSF, per-pixel wavelength) change which software defaults are safe.
- Distinguishing *apparent* change from *physical* change must be built into the interface wording.

## Future improvements
- PSF-fitting photometry and deblending for higher completeness.
- Shift-and-stack searches across more epochs for fainter movers.
- More sky regions and all six detectors in Time Compare.
- Wavelength-matched differencing using SPHEREx wavelength maps.
- Public hosting with a persistent data volume for the spectral mosaic.
