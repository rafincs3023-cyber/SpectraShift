# SpectraShift — Demo Flow (2–4 minutes)

Open https://spectrashift.rafincs3023.workers.dev (or run locally as described in the README).

| # | Time | Screen | Action | What to say |
|---|---|---|---|---|
| 1 | 0:00 | **Home** | Show the hero and four cards | "SpectraShift explores real NASA SPHEREx data across wavelength and across time, and screens two observations six months apart for possible moving sources, without over-claiming." |
| 2 | 0:15 | **Spectral View** | Open it; point at the Spectral View / Time Compare cards | "Spectral View is the same sky at the same time in 102 wavelengths, 0.74 to 5 µm, from all six SPHEREx detectors." |
| 3 | 0:35 | Spectral View | Drag the slider across D1 → D6; click a bright star | "Each channel is a real mosaic plane. Clicking a position reads its brightness in all 102 channels: a spectrum straight from the data." |
| 4 | 1:05 | **Time Compare** | Open Compare | "Time Compare is the same sky on June 19 and December 17, 2025: 181.77 days apart, same detector, wavelengths within 0.003 µm." |
| 5 | 1:20 | Slider / **Blink** | Drag the divider, then blink | "The later image was reprojected onto the earlier grid, so stars line up exactly and anything that changed flickers." |
| 6 | 1:40 | **Difference** | Read the colour key | "Later minus earlier: red is brighter in December, blue brighter in June. A difference does not automatically mean that an object moved." |
| 7 | 2:00 | **Candidates** | Show the counts and the disclaimer | "Our two-epoch pipeline found about 7,500 and 6,800 sources and matched 6,472 of them as stationary. After quality checks, 11 candidates remain, and none is a clear position change: 10 are small shifts inside the image blur, 1 is a faint source seen only in June." |
| 8 | 2:30 | Candidate Detail | Open SX6M-001 | "Every candidate has real cutouts from both dates and the difference, with its caveats. A shift this small in six months would need a very high proper-motion star, so these are for inspection, not discoveries." |
| 9 | 2:55 | Candidates → Technical details | Open it | "Every threshold is measured: noise, sharpness, alignment, and a position-error model fitted to thousands of stationary stars. Every rejection is counted. Two observations cannot give an orbit." |
| 10 | 3:20 | Home | Return | "SpectraShift makes SPHEREx explorable across wavelength and time, and is honest about what two observations can and cannot show." |

**Backup plan:** if the spectral data are slow on first load, start in Time Compare (previews are cached) and return to Spectral View afterwards.
