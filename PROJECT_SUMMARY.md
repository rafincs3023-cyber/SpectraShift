# SPHEREx Data Processing → SpectraShift — Full Project Summary

**Project:** NASA Space Apps 2026 — "Planet X and SPHEREx" challenge
**Location:** `C:\SPHEREx_Data_Processing`
**Final product name:** **SpectraShift** — "A SPHEREx Spectral & Multi-Epoch Sky Explorer"

---

## 1. Scientific Data Pipeline (Python)

**Input data:** 3 real SPHEREx FITS observations (Detector 3 / SWIR band only)
- Epoch A: `level2_2025W19_2B_0166_3D3_spx_l2b-v20-2025-247.fits` (2025-05-09, MJD 60804.58)
- Epoch C: `level2_2025W22_1B_0226_1D3_spx_l2b-v20-2025-250.fits` (2025-05-27, MJD 60822.31)
- Epoch B: `level2_2025W24_1A_0099_1D3_spx_l2b-v20-2025-252.fits` (2025-06-09, MJD 60835.42)

**Pipeline steps (in order run):**
1. `process_spherex.py` — WCS alignment of B onto A's pixel grid (reproject_interp), A−B difference image
2. `detect_candidates.py` — significance-based change detection
3. `three_epoch_compare.py` — source detection (DAOStarFinder, 7σ) on all 3 epochs, A→C→B linking, **stationary-source veto**
   - Earlier version: linked the full source lists with no stationarity test → 23 "candidates", every one of which later proved to be linked stationary stars (a different Gaia star at each epoch). Two causes: (1) nothing required a track's detections to be absent from the other epochs; (2) DAOStarFinder's default sharpness cut (≤ 1.0) drops about half of SPHEREx's undersampled point sources depending on sub-pixel phase, so a stationary star vanished from some epochs' lists and looked "unmatched".
   - Current version: shape limits relaxed and SPHEREx-flagged pixels masked; astrometric model calibrated from ~75k stationary source pairs (centroid σ 0.48–0.58″, registration σ 0.08–0.11″); every linked track is tested in sky coordinates and rejected as `STATIONARY_SOURCE`, `BLEND_MISLINK` or `INCONSISTENT_TRAJECTORY` (log: `rejected_three_epoch_tracks.csv`; model: `three_epoch_linking_calibration.json`; classified sources: `three_epoch_detections.csv`)
   - Result: 725 tracks formed → **0 accepted** (673 stationary source, 52 blend/mislink). Measured false-veto probability for a genuine mover ≈ 10%; injection–recovery (`test_linker_injection.py`) recovers ~43% of injected movers end to end (5% with the old detection settings), limited by detection completeness, not the veto.
   - Previous outputs kept for comparison in `data/pipeline_v1_backup/` (incl. `old_candidates_new_outcome.csv`, the fate of each old track)
4. `validate_candidates.py` — trajectory/rate/C-prediction/flux validation → `validated_three_epoch_candidates.csv`, `top_candidate_tracks.png` (currently 0 candidates; placeholder figure)
5. **Catalogue classification** (`catalogue_crossmatch_v3.py`) — Gaia DR3 propagated to each epoch with proper motion, uncertainty-aware (χ²) matching, chance-coincidence probability, flux-vs-G check, SIMBAD, full known-asteroid/comet search via JPL sb_ident + Horizons from the SPHEREx spacecraft, forced-photometry persistence → `KNOWN_OBJECT` / `UNMATCHED_AFTER_CHECKS` / `UNCERTAIN` with a reason per candidate (currently 0 candidates to classify)
6. `final_ranking.py` — 70% validation + 20% catalogue status + 10% Solar System check → `final_ranked_candidates.csv` (notes regenerated from current values)

**Scientific integrity rule enforced throughout:** never invent data; every "null" is a real "could not determine," never a guess. No candidate is ever called "Planet X," "discovery," or "confirmed."

---

## 2. Backend — FastAPI (`backend/`)

Read-only API over the completed science outputs — never reruns detection/validation/ranking/cross-match.

**Files:** `main.py`, `data_access.py`, `images.py`, `spectrum.py`

**Endpoints:**

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | data/file availability check |
| `GET /api/observations` | 3 epochs' metadata (MJD, WCS center, detector) |
| `GET /api/candidates` | current validated candidates, ranked (0 after the stationary-source veto) |
| `GET /api/linking-summary` | latest linker run: tracks formed / accepted / rejected by reason |
| `GET /api/candidates/{id}` | full candidate detail |
| `GET /api/catalogue-crossmatch/{id}` | full 15-row audit trail per candidate |
| `GET /api/candidates/{id}/spectrum` | real per-epoch (wavelength, flux, uncertainty) from FITS WCS-WAVE + VARIANCE |
| `GET /api/candidates/{id}/cutout/{epoch}` | real 320×320 pixel cutout with crosshair on real detected position |
| `GET /api/observations/{epoch}/preview` | full-frame PNG preview (asinh-stretched) |
| `GET /api/observations/B/preview-aligned` | B reprojected onto A's grid |
| `GET /api/compare/pair`, `/difference-preview`, `/candidate-markers` | Compare-page support |

Run:
```
cd backend
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

---

## 3. Frontend — React + TypeScript + Vite (`frontend/`)

**Pages (all real, live data — zero mock data anywhere):**
- **Home** — hero + feature cards
- **Candidates** — ranked list live from the API, with the linker summary (tracks formed / rejected by reason) and an explained empty state (currently 0 candidates)
- **Candidate Detail** — ranking, positions, motion, validation scores, catalogue cross-match table, **+ Visual Evidence section**: real per-epoch cutouts, A→C→B motion-track SVG, flux-vs-wavelength spectrum chart, brightness-vs-time light curve, "Inspect in Explore" / "Open in Compare" links
- **Explore** — zoom/pan sky viewer, epoch/band selector (only real band: Detector 3 SWIR), clickable candidate markers → RA/Dec, spectrum, catalogue match, motion
- **Compare (Time Compare)** — primary **~6-Month Compare** (2025-06-19 → 2025-12-17, 181.77 days, registered 1016 × 346 px common frame, difference B − A) and secondary **31-Day A/C/B Compare** (difference A − B for the registered A/B pair); 5 modes: **Side-by-Side, Slider, Blink, Difference, Overlay**
- **Spectral View** — all 102 SPHEREx channels (0.743–5.009 µm, D1–D6), per-channel metadata incl. measured sky coverage, click-to-spectrum and RA/Dec lookup
- **About** — Challenge Goal, How SpectraShift Works, Data & Provenance (SPHEREx QR2, DOI 10.26131/IRSA652, via IRSA/AWS), Scientific Limitations, "what this is/is not"
- **Help** — full usage glossary for every feature above

Run:
```
cd frontend
npm run dev
```
→ http://localhost:5173

---

## 4. Real Bugs Found & Fixed During Development
1. `unhashable type: numpy.ndarray` in three-epoch matching
2. Deprecated photutils column names
3. `or` on a pandas DataFrame crashing marker computation
4. **CORS cache-poisoning**: images loaded first without `crossOrigin`, then later with it (for canvas overlay) → browser reused a bad cache entry → fixed by making every image load consistently `crossOrigin="anonymous"` (caught 3 separate times across Compare/Explore via real headless-Chrome testing, not just curl)
5. Passive `onWheel` listener silently failing `preventDefault()` on zoom
6. Stuck-loading edge case if both Compare epochs matched

---

## 5. Branding
Renamed **DeltaScope → SpectraShift** everywhere (nav, titles, About page, README, FastAPI title/OpenAPI schema) — confirmed via full repo scan, zero leftover old-brand references.

---

**Documentation:** `README.md`, `docs/ARCHITECTURE.md`, `docs/DEPLOYMENT.md`, `docs/DEMO_FLOW.md`, `docs/PROJECT_DESCRIPTIONS.md`, `docs/PRESENTATION.md`, `docs/NASA_SUBMISSION.md`.
