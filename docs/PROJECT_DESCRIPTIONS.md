# SpectraShift — Project Descriptions

## A. ~100 words

SpectraShift is a web explorer for real NASA SPHEREx data that shows the same sky across wavelength and across time.

- **Spectral View** steps through all 102 near-infrared channels (0.74–5.01 µm) of a SPHEREx mosaic and plots the spectrum of any clicked position.
- **Time Compare** aligns two SPHEREx observations from June 19 and December 17, 2025 (181.77 days apart), with side-by-side, slider, blink, difference and overlay views.
- **Explore** inspects either observation in detail.
- **Candidates** lists possible moving-source candidates from those two dates, after measured, conservative quality checks.

Candidates are for inspection only; nothing is claimed as a discovery.

## B. ~250 words

SpectraShift is our response to the NASA Space Apps "Planet X and SPHEREx" challenge: an interactive, scientifically careful way to explore NASA's SPHEREx all-sky spectral survey.

SpectraShift turns real IRSA data products into connected tools:

- **Spectral View** shows one 5° × 4.25° region in all 102 channels (0.74–5.01 µm, detectors D1–D6). Users change channels, see each channel's wavelength range and sky coverage, and click any position to plot its spectrum.
- **Time Compare** shows the same sky on June 19 and December 17, 2025. The two images are 181.77 days apart, on the same detector, with wavelengths within 0.003 µm. They are registered onto one pixel grid, with five viewing modes including a Later − Earlier difference.
- **Explore** inspects either observation with zoom and pan.

The **two-epoch candidate pipeline** screens that same pair for possible moving sources:

1. Detect sources in both images after PSF matching.
2. Set aside everything at the same place on both dates. The position-error model is measured from thousands of stationary stars, and the tolerance is 5σ.
3. Reject artifacts: flagged or corrupted pixels, bright-star glare, blends, non-star-like shapes, and changes the difference image does not confirm.

Of about 6,500 matched sources, 11 candidates passed: 10 small shifts within the image blur and 1 source seen only in June. None is a clear position change. Two observations cannot establish a trajectory or orbit, so every candidate is only for further inspection; SpectraShift never claims a discovery.

## C. Detailed submission description

### What it is
SpectraShift, "a SPHEREx spectral and ~6-month two-epoch sky explorer", is a web application built entirely on real NASA SPHEREx data from NASA/IPAC IRSA. It has a React frontend on Cloudflare Workers and a FastAPI backend on Railway, with spectral tiles in private Cloudflare R2.

Live: https://spectrashift.rafincs3023.workers.dev

### Spectral View: same sky, same time, 102 wavelengths
- A 102-channel SPHEREx spectral mosaic (5.0° × 4.25°, 6.15″ pixels), centred on RA 155.352°, Dec −42.700°.
- All 102 channels, 0.743–5.009 µm, across detectors D1–D6, with measured sky coverage per channel.
- Click-to-spectrum, or RA/Dec lookup, returns the brightness of that position in every channel.

### Time Compare: same sky, about six months apart
- **Earlier observation:** Level-2 detector-3 exposure from 2025-06-19T00:00:58.754 at 1.684886 µm.
- **Later observation:** Level-2 detector-3 exposure from 2025-12-17T18:35:43.129 at 1.681677 µm.
- Baseline 181.774125 days (~5.97 months); PSF FWHM 5.22″ in both images; units MJy/sr.
- The later image is reprojected onto the earlier grid. Every view uses the same 1016 × 346 px frame, which lies inside the common footprint.
- Modes: Side by Side, Slider, Blink, Difference (Later − Earlier) and Overlay.

### Two-epoch candidate screening
The inputs are only the two ~6-month images, their overlap mask, the difference image and the pixel flags of the two source frames.

- **Measured image properties:**
  - image sharpness: 9.1″ and 10.9″ FWHM
  - noise
  - alignment residual: about 0.1″ from 1,252 bright stars
  - position-error model: floor 0.63″, k = 3.0″
- **Stationary tolerance:** 5σ of the measured position error, corrected for about 6,500 trials.
- **Vetoes:** footprint edge, SPHEREx-flagged pixels, corrupted pixels, star-likeness, bright-star halo, crowding and blends, centroid quality, and difference-image sign/significance.
- **Result:** 11 candidates passed.
  - 0 possible position changes
  - 10 small position shifts (3.8–9.1″)
  - 1 source seen only in the earlier image
- **Validation:** synthetic injection tests recover a large position change and a small shift, reject every stationary star and reject edge, flagged-pixel and spike artifacts.

### Scientific integrity
- No discovery claims.
- Two epochs cannot give a trajectory or orbit, so every candidate is labelled "preliminary two-epoch candidate".
- The difference image is supporting evidence only.
- Missing values are never invented.
- The interface always distinguishes wavelength (Spectral View) from time (Time Compare).
