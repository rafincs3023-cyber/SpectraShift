# SpectraShift — Presentation Content (slide by slide)

---

### 1. Title
**SpectraShift**
*A SPHEREx Spectral & Multi-Epoch Sky Explorer*
NASA Space Apps 2026 · "Planet X and SPHEREx"
Visual: Spectral View channel image beside the ~6-month B − A difference.

---

### 2. Problem
- Searching for distant, slowly moving Solar System objects means comparing the same sky at different times.
- In crowded star fields most apparent "movers" are artifacts: chance links of stationary stars, blends, bright-star halos.
- SPHEREx data are rich (102 wavelengths, repeat visits) but locked in large FITS files and specialist tools.

---

### 3. The SPHEREx opportunity
- NASA's SPHEREx maps the whole sky in **102 near-infrared channels** (0.75–5 µm).
- It revisits the sky, so the same field can be compared across months.
- Public data through NASA/IPAC IRSA.

---

### 4. The challenge
- Use SPHEREx data to explore the sky and look for possible moving objects — the idea behind "Planet X" searches.
- Do it transparently: show evidence, not claims.

---

### 5. SpectraShift
Three connected views on real data:
- **Spectral View** — same sky, same time, 102 wavelengths
- **Time Compare** — same sky, different times
- **Candidates** — a moving-source search with false-positive vetoes

---

### 6. Architecture
NASA SPHEREx / IRSA → Level-2 images + 102-channel mosaic → offline Python pipeline → read-only FastAPI backend → React web interface.
Three branches: spectral processing · multi-epoch registration and differencing · source extraction → linking → vetoes → catalogue validation.
Visual: Mermaid diagram from `docs/ARCHITECTURE.md`.

---

### 7. 102-channel Spectral View
- 102 channels, 0.743–5.009 µm, detectors D1–D6
- Per-channel wavelength range, bandwidth, measured sky coverage (97.08–99.76%)
- Click any position (or enter RA/Dec) → spectrum across all 102 channels
Visual: screenshot with the wavelength bar and spectrum chart.

---

### 8. Multi-epoch Time Compare
- Five modes: Side by Side · Slider · Blink · Difference · Overlay
- Primary ~6-month pair and secondary 31-day A/C/B set
- Pixel-registered; metadata panel with dates, baseline, wavelengths, target and frame centre

---

### 9. Verified ~6-month example
- 2025-06-19 → 2025-12-17: **181.77 days (~5.97 months)**
- Same detector (D3, SWIR), wavelengths 1.6849 / 1.6817 µm (Δλ 0.0032 µm)
- PSF FWHM 5.22″ in both; units MJy/sr
- Common frame 1016 × 346 px, 99.97% valid
- Difference **B − A**: positive = brighter in the later epoch — an *apparent* change
Visual: slider screenshot + difference with caption.

---

### 10. Candidate pipeline
Detect (3 epochs) → link A → C → B → stationary-source veto → blend/halo veto → trajectory validation → catalogue classification (Gaia DR3 epoch-propagated, SIMBAD, JPL small bodies) → ranking.

---

### 11. False-positive filtering
- Astrometry calibrated from ~75,000 stationary source pairs (σ ≈ 0.5″)
- **725 linked tracks → 0 accepted** (673 stationary source, 52 blend/mislink)
- An earlier version's 22 "candidates" were all chance links of stationary stars — withdrawn
- Veto cost measured: ~10% of genuine movers; injection test recovers 43% of 150 synthetic movers

---

### 12. Scientific integrity
- Real data only; missing values never invented
- No "Planet X", "discovery" or "confirmed" claims
- "Unmatched after checks" ≠ unknown object
- An empty candidate list ≠ no moving objects
- Wavelength (Spectral View) and time (Time Compare) never conflated

---

### 13. Demo
Home → Spectral View (channels, click-to-spectrum) → Time Compare (slider, blink, difference) → Candidates (vetoes, empty-state explanation). See `docs/DEMO_FLOW.md`.

---

### 14. Impact
- Makes SPHEREx's spectral and time dimensions explorable in a browser — for students, educators and citizen scientists.
- Demonstrates a transparent search workflow in which false positives are rejected and explained rather than promoted.
- Reusable components: registered multi-epoch comparison, 102-channel spectral browsing, calibrated stationary-source veto.

---

### 15. Limitations
- One sky region; Time Compare on one detector (D3)
- Detection completeness in a crowded field (43% injected recovery); zero candidates ≠ no movers
- Linear motion, 5–120″ over 31 days
- The ~6-month pair differs slightly in wavelength; differences are apparent changes

---

### 16. Future work
- PSF-fitting photometry and deblending
- Shift-and-stack across more epochs for fainter movers
- More fields and all six detectors in Time Compare
- Wavelength-matched differencing
- Public deployment with a persistent data volume

---

### 17. Conclusion
SpectraShift shows the same sky across **wavelength** and **time** using real NASA SPHEREx data — and applies the same care to what it does *not* find as to what it shows.
