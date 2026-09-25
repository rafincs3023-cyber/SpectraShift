# SpectraShift — NASA Space Apps Submission Draft

**Challenge:** Planet X and SPHEREx
**Project:** SpectraShift, a SPHEREx spectral and ~6-month two-epoch sky explorer
**Live:** https://spectrashift.rafincs3023.workers.dev

## Project summary
SpectraShift is a web application that lets anyone explore real NASA SPHEREx data across wavelength and across time:

- **Spectral View** presents all 102 SPHEREx near-infrared channels of one sky region, with click-to-spectrum.
- **Time Compare** shows the same sky observed on June 19 and December 17, 2025 (181.77 days apart), pixel-registered, in five comparison modes.
- **Explore** inspects either observation.
- **Candidates** lists possible moving-source candidates from those two dates, after measured quality checks.

Candidates are preliminary and never presented as discoveries.

## Problem
Looking for faint, distant, slowly moving bodies requires comparing the same sky at different times. In crowded fields, most apparent change is not real:

- blended sources shift their centroids
- bright-star halos and flagged or corrupted pixels create spurious detections
- the undersampled PSF makes positions scatter

SPHEREx adds 102 wavelengths per position, but its data products are large FITS files that are difficult for non-specialists to explore.

## Solution
- **Spectral View:** browse 102 channels (0.743–5.009 µm, detectors D1–D6). See each channel's wavelength range and sky coverage, and click any position for its 102-channel spectrum.
- **Time Compare:** a verified pair of SPHEREx exposures from 2025-06-19 and 2025-12-17, 181.774 days apart, on the same detector D3, with wavelengths within 0.0032 µm.
  - Registered onto one grid and cut to a fully valid common frame.
  - Viewable side by side, with a slider, blinking, as a Later − Earlier difference, or as a colour overlay.
- **Two-epoch candidates:** detection in both images, cross-matching with a measured position-error model, forced photometry and conservative quality vetoes. The results are marked on the images and explained with real cutouts.

## NASA data used
- SPHEREx Level-2 spectral images and a 102-channel SPHEREx spectral mosaic, from NASA/IPAC IRSA (SPHEREx Quick Release, DOI 10.26131/IRSA652), including the official IRSA SPHEREx Mosaic Tool.
- SPHEREx Level-2 pixel-quality flags for both observations.

## How it works
1. The later image is reprojected onto the earlier image's WCS grid. The largest fully valid rectangle in the overlap mask becomes the common display frame, and a Later − Earlier difference is computed.
2. The spectral mosaic's channel table and wavelength calibration are read from the FITS files; previews and spectra are served on demand (from private R2 tiles in production).
3. The two-epoch pipeline (`backend/two_epoch_candidates.py`) works in these steps:
   1. Measure each image's noise and sharpness, and blur the sharper image to match the other.
   2. Detect sources in both images with a matched filter (≥ 5σ).
   3. Match them on the shared grid.
   4. Fit a position-error model to the thousands of stationary matches, and treat a source as stationary within 5σ, corrected for about 6,500 trials.
   5. Check unmatched sources with forced photometry in the other image.
   6. Reject look-alikes: edge, SPHEREx-flagged pixels, corrupted pixels, non-star-like shape, bright-star halo, blends, poor centroid, and a change the difference image does not confirm.
4. A read-only FastAPI backend serves PNG previews, cutouts and JSON, and a React interface presents everything. The browser never downloads FITS files.

## Result
- About 7,500 sources in the earlier image and 6,800 in the later one; 6,472 matched as stationary.
- **11 candidates passed the current checks:**
  - 0 possible position changes (an earlier-only source paired with a later-only source)
  - 10 small position shifts of 3.8–9.1″, within the image blur
  - 1 faint source seen only in the earlier image
- The small shifts sit in the measured long tail of position errors: 141 matches lie beyond 5σ, versus 0.02 expected for Gaussian errors. They are therefore most likely blends or pixel-sampling effects, and are listed for inspection only.

## Technologies
- **Frontend:** React 19, TypeScript, Vite, React Router (Cloudflare Workers).
- **Backend:** Python, FastAPI, Uvicorn, NumPy, SciPy, Astropy, Pillow, boto3 (Railway; Cloudflare R2).
- **Testing:** pytest and oxlint.

## Innovation
- One interface for both of SPHEREx's dimensions, wavelength and time, with a clear distinction between them.
- A pixel-registered long-baseline comparison whose display frame comes from the actual overlap mask.
- A two-epoch screening in which every threshold is measured from the data or derived from stated trial counts. Every rejection is counted and shown, and synthetic injection tests verify recovery and rejection.

## Impact
SpectraShift makes SPHEREx's spectral and time dimensions explorable in a browser for students, educators and citizen scientists. It demonstrates a transparent screening workflow in which false positives are rejected and explained instead of being presented as discoveries.

## Challenges
- The two images differ in sharpness: the later one is reprojected, and bilinear interpolation blurs it. Without PSF matching, faint sources in the sharper image looked like disappearances.
- Unflagged corrupted pixels in one image mimicked vanished stars; a dedicated veto was needed.
- Position errors have longer tails than a Gaussian model predicts, so small shifts are reported with explicit caution.

## Accomplishments
- All 102 SPHEREx channels browsable, with click-to-spectrum.
- A verified 181.77-day registered comparison with five modes.
- A reproducible, tested two-epoch candidate pipeline with real-pixel cutouts for every candidate.

## Lessons learned
- Two epochs can flag changes but cannot establish motion; that limitation belongs in the interface, not just the paper.
- Instrument details (an undersampled PSF, reprojection blur, pixel flags) decide which checks are necessary.
- Distinguishing *apparent* change from *physical* change must be built into the wording.

## Future improvements
- Additional epochs of the same field, to test candidates for a consistent path.
- Catalogue checks (Gaia, SIMBAD, known Solar System bodies) for two-epoch candidates.
- PSF-fitting photometry and deblending.
- More sky regions and detectors.
