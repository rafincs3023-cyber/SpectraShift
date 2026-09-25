# SpectraShift — Presentation Content (slide by slide)

---

### 1. Title
**SpectraShift**
*A SPHEREx spectral and ~6-month two-epoch sky explorer*
NASA Space Apps 2026 · "Planet X and SPHEREx"
Visual: a Spectral View channel image beside the ~6-month Later − Earlier difference.

---

### 2. Problem
- Searching for distant, slowly moving objects means comparing the same sky at different times.
- In crowded star fields, most apparent changes are artifacts: blends, bright-star halos, flagged pixels, centroid scatter.
- SPHEREx data are rich (102 wavelengths, repeat visits) but locked in large FITS files and specialist tools.

---

### 3. The SPHEREx opportunity
- NASA's SPHEREx maps the whole sky in **102 near-infrared channels** (0.75–5 µm).
- It revisits the sky, so the same field can be compared across months.
- Public data are available through NASA/IPAC IRSA.

---

### 4. SpectraShift
Four connected views on real data:
- **Spectral View:** same sky, same time, 102 wavelengths
- **Time Compare:** same sky, June 19 → December 17, 2025
- **Explore:** either observation in detail
- **Candidates:** possible two-epoch moving-source candidates

---

### 5. Architecture
SPHEREx data feeds two tracks:
- **Wavelength:** 102-channel spectral exploration.
- **Time:** the Jun 19 and Dec 17, 2025 observations are registered into a ~6-month comparison, then screened for two-epoch candidates.

Both tracks end in the public web interface: FastAPI backend (Railway, R2) → React (Cloudflare Workers).

Visual: Mermaid diagram from `docs/ARCHITECTURE.md`.

---

### 6. 102-channel Spectral View
- 102 channels, 0.743–5.009 µm, detectors D1–D6
- Per-channel wavelength range, bandwidth and measured sky coverage
- Click any position → its spectrum across all 102 channels

---

### 7. ~6-month Time Compare
- 2025-06-19 → 2025-12-17: **181.77 days (~5.97 months)**
- Same detector (D3, SWIR); wavelengths 1.6849 / 1.6817 µm (Δλ 0.0032 µm)
- Common frame 1016 × 346 px, 99.97% valid
- Five modes: Side by Side · Slider · Blink · Difference · Overlay
- Later − Earlier: red = brighter later, blue = brighter earlier. A difference does not automatically mean that something moved.

---

### 8. Two-epoch candidate pipeline
Measure noise and sharpness → PSF-match → detect ≥ 5σ in each image → cross-match → measured position-error model → 5σ stationary tolerance → forced photometry → vetoes (edge, SPHEREx flags, corrupted pixels, shape, halo, blend, centroid, difference sign) → candidates.

---

### 9. Result
- ~7,500 and ~6,800 sources; 6,472 matched as stationary
- **11 candidates passed the current checks:** 0 possible position changes, 10 small shifts (3.8–9.1″), 1 seen only in June
- Every candidate has real earlier / later / difference cutouts
- Small shifts sit in the measured error tail, so they are listed for inspection, not claimed

---

### 10. Validation
- Synthetic star fields: an injected large move is recovered as a pair, and an injected small shift is recovered
- 250 stationary stars all rejected; edge, flagged-pixel and spike artifacts rejected for the right reason
- Real data: stored results equal a fresh run, only the Jun 19 / Dec 17 files are used, and rate = displacement / 181.774125 days

---

### 11. Scientific integrity
- Real data only; missing values are never invented
- No "Planet X", "discovery" or "confirmed" claims
- Two epochs cannot establish a trajectory or an orbit
- The difference image is supporting evidence only
- Wavelength (Spectral View) and time (Time Compare) are never conflated

---

### 12. Demo
Home → Spectral View → Time Compare (slider, blink, difference) → Candidates → Candidate Detail. See `docs/DEMO_FLOW.md`.

---

### 13. Impact
- Makes SPHEREx's spectral and time dimensions explorable in a browser.
- Demonstrates a transparent screening workflow in which false positives are rejected and explained.

---

### 14. Limitations
- Two epochs: no trajectory, orbit or acceleration
- One sky region; Time Compare on one detector (D3)
- Detection completeness in a crowded field: a short list does not mean no movers
- Small wavelength and sharpness differences between the two images

---

### 15. Future work
- More epochs of the same field, to test candidates for a consistent path
- Catalogue checks for candidates
- PSF-fitting photometry and deblending
- More fields and detectors

---

### 16. Conclusion
SpectraShift shows the same sky across **wavelength** and **time** using real NASA SPHEREx data, and is careful about what two observations can and cannot show.
