# SpectraShift — Demo Flow (2–4 minutes)

Start the backend and frontend (see README), open `http://localhost:5173`.

| # | Time | Screen | Action | What to say |
|---|---|---|---|---|
| 1 | 0:00 | **Home** | Show the hero and four cards | "SpectraShift explores real NASA SPHEREx data in two directions: across wavelength and across time — and searches for moving sources without over-claiming." |
| 2 | 0:15 | **Spectral View** | Open it; point at the Spectral View / Time Compare cards | "Spectral View is the same sky at the same time in 102 wavelengths, 0.74 to 5 µm, from all six SPHEREx detectors." |
| 3 | 0:35 | Spectral View | Drag the slider / click the wavelength bar across D1 → D6; press → a few times | "Each channel is a real mosaic plane. The panel shows detector, wavelength range, bandwidth and measured sky coverage." |
| 4 | 1:00 | Spectral View | Click a bright star in the image | "Clicking a position reads its brightness in all 102 channels…" |
| 5 | 1:10 | Spectral View | Show the spectrum chart | "…giving a near-infrared spectrum straight from the data." |
| 6 | 1:25 | **Time Compare** | Open Compare (~6-Month is the default) | "Time Compare is the same sky at different times: June 19 and December 17, 2025 — 181.77 days apart, same detector, wavelengths within 0.003 µm." |
| 7 | 1:40 | Side by Side | Point at the metadata panel | "Epoch B was reprojected onto Epoch A's grid and both are cut to one frame that is fully inside the common footprint." |
| 8 | 1:50 | **Slider** | Drag the divider | "Pixel-registered, so stars line up exactly." |
| 9 | 2:00 | **Blink** | Let it alternate | "Blinking is the classic way to spot apparent change." |
| 10 | 2:10 | **Difference** | Read the caption | "B minus A: red is brighter in December, blue brighter in June. These are apparent variations, not confirmed physical changes." |
| 11 | 2:30 | **Candidates** | Show the summary line and empty state | "The moving-source pipeline linked 725 candidate tracks across three epochs. Every one was traced to stationary stars at the same sky position, or to blends and bright-star halos — so no candidate is reported." |
| 12 | 2:50 | Candidates / Help | Hover a status or open Help | "Safeguards: calibrated astrometry, stationary and blend vetoes, epoch-propagated Gaia matching. An earlier version reported 22 'candidates'; we showed they were chance links and removed them. We measured that the veto would only reject about 10% of real movers, so an empty list reflects the data, not a broken filter — and it does not mean no movers exist." |
| 13 | 3:20 | Home | Return | "SpectraShift makes SPHEREx explorable across wavelength and time — and is honest about what the data do and do not show." |

**Backup plan:** if the spectral mosaic is slow on first load, start the demo in Time Compare (previews are cached) and return to Spectral View after it has loaded.
