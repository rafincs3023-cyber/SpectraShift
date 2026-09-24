# SpectraShift — Project Descriptions

## A. ~100 words

SpectraShift is a web explorer for real NASA SPHEREx data that shows the same sky across wavelength and across time. Spectral View steps through all 102 near-infrared channels (0.74–5.01 µm) of a SPHEREx mosaic and plots the spectrum of any clicked position. Time Compare aligns SPHEREx observations taken 181.8 days apart and offers side-by-side, slider, blink, difference and overlay views of apparent change. A three-epoch moving-source pipeline links detections across dates and rejects stationary-star, blend and catalogue false positives. In the current data no candidate passes, and the site explains why — without claiming any discovery.

## B. ~250 words

SpectraShift is our response to the NASA Space Apps "Planet X and SPHEREx" challenge: an interactive, scientifically careful way to explore NASA's SPHEREx all-sky spectral survey.

SPHEREx observes every part of the sky in 102 near-infrared wavelength channels and revisits it over time. SpectraShift turns those real IRSA data products into three connected tools. **Spectral View** shows one 5° × 4.25° region in all 102 channels (0.74–5.01 µm, detectors D1–D6); users change channels, see each channel's wavelength range and measured sky coverage, and click any position to plot its spectrum. **Time Compare** shows the same sky at different times: a verified pair from June 19 and December 17, 2025 (181.77 days, same detector, wavelengths within 0.003 µm), registered onto one pixel grid and cut to a fully valid common frame, plus a 31-day three-epoch set. Five modes — side by side, slider, blink, difference (later minus earlier) and overlay — make apparent changes visible.

The third part searches for moving sources across three epochs. Because crowded star fields produce many false "movers", SpectraShift applies a calibrated stationary-source veto, a blend and bright-star-halo veto, trajectory validation and epoch-propagated catalogue matching against Gaia, SIMBAD and JPL's small-body database. In the current data, all 725 linked tracks were rejected, so no candidate is reported; an injection test confirms the pipeline can still recover synthetic movers. SpectraShift never claims a discovery, and it explains empty results instead of hiding them.

## C. Detailed submission description

### What it is
SpectraShift — "A SPHEREx Spectral & Multi-Epoch Sky Explorer" — is a web application (React frontend, FastAPI backend, Python science pipeline) built entirely on real NASA SPHEREx data from NASA/IPAC IRSA.

### Spectral View — same sky, same time, 102 wavelengths
- A 102-channel SPHEREx spectral mosaic (5.0° × 4.25°, 6.15″ pixels) centred on RA 155.352°, Dec −42.700°, created with the official IRSA SPHEREx Mosaic Tool.
- All 102 channels from 0.743 to 5.009 µm across detectors D1–D6, navigable by slider, wavelength bar, buttons, channel number or keyboard.
- For each channel: detector, subchannel, wavelength range, bandwidth and measured sky coverage (97.08–99.76%).
- Click-to-spectrum or RA/Dec lookup returns the brightness of that position in every channel.

### Time Compare — same sky, different times
- **Primary ~6-month pair:** SPHEREx Level-2 detector-3 exposures from 2025-06-19T00:00:58.754 and 2025-12-17T18:35:43.129 — a 181.774-day baseline (~5.97 months); wavelengths 1.684886 and 1.681677 µm (Δλ = 0.003209 µm, 0.08 of the bandwidth); PSF FWHM 5.22″ in both; units MJy/sr.
- Epoch B reprojected onto Epoch A's WCS grid; every browser view uses the same 1016 × 346 px frame lying entirely inside the common footprint (99.97% valid pixels), so all modes are pixel-registered.
- Modes: Side by Side, Slider, Blink, Difference (B − A: positive = brighter in the later epoch) and Overlay.
- The metadata panel separates the target (RA 155.352°, Dec −42.700°) from the displayed frame centre.
- **Secondary 31-day set:** Epochs A/C/B (May 9, May 27, June 9, 2025) with an A − B difference.

### Moving-source search with false-positive rejection
- Source extraction in three epochs, A → C → B linking with a constant-velocity prediction.
- An astrometric model calibrated from ~75,000 stationary source pairs (centroid σ ≈ 0.48–0.58″, registration σ ≈ 0.08–0.11″).
- Stationary-source veto (same source at the same sky position in other epochs), blend / bright-star-halo veto, uncertainty-aware trajectory check.
- Catalogue classification: Gaia DR3 propagated to each epoch with proper motion, SIMBAD, and a full known-asteroid/comet search (JPL Small-Body Identification + Horizons from the SPHEREx spacecraft position), with statuses `KNOWN_OBJECT`, `UNMATCHED_AFTER_CHECKS` or `UNCERTAIN` and a written reason.
- **Result:** 725 linked tracks, 0 accepted (673 stationary source, 52 blend/mislink). An earlier version's 22 "candidates" were shown to be chance links of stationary stars and were withdrawn.
- **Sensitivity:** ~10% chance that the veto rejects a genuine mover; 43% end-to-end recovery of 150 injected synthetic movers.

### Scientific integrity
No discovery claims; "unmatched" never means "new"; an empty candidate list is explained and not interpreted as "no movers exist"; missing values are never invented; the interface always distinguishes wavelength (Spectral View) from time (Time Compare).
