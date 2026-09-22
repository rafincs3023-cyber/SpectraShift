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
3. `three_epoch_compare.py` — full source detection (DAOStarFinder) on all 3 epochs, A→C→B motion matching → **23 preliminary candidates**
   - Fixed a real bug: `unhashable type: numpy.ndarray` from astropy's scalar `match_to_catalog_sky` returning 0-d arrays; also updated deprecated photutils `xcentroid`→`x_centroid`
4. `validate_candidates.py` — scientific validation (trajectory consistency, rate consistency, C-prediction error, flux consistency) → **22 validated candidates** (1 rejected: 3EPOCH-010, inconsistent trajectory)
   - Output: `validated_three_epoch_candidates.csv`, `top_candidate_tracks.png`
5. **Catalogue cross-match** (`catalogue_crossmatch_v2.py`) — Gaia DR3 + SIMBAD (both reachable) + SkyBoT/MPC (both **unreachable** from this network, confirmed repeatedly) + JPL Horizons (19 major/bright bodies only, not full minor-planet catalogue)
   - Found & fixed a real bug: mistakenly treated "matched *some* star each epoch" as "matched the *same* object" — fixed to require same object recurring
   - Result: **all 22 candidates → UNCERTAIN** (comprehensive SSO check impossible; field is at ecliptic latitude −48.7°, far from where minor planets are typically found)
   - Output: `catalogue_crossmatch_results.csv` (330-row audit trail), `validated_candidates_with_catalogue.csv`
6. `final_ranking.py` — combined priority score (70% validation + 20% catalogue confidence + 10% SSO check) → `final_ranked_candidates.csv`

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
| `GET /api/candidates` | all 22 candidates, ranked |
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
- **Candidates** — full ranked list (final priority rank), live from API
- **Candidate Detail** — ranking, positions, motion, validation scores, catalogue cross-match table, **+ Visual Evidence section**: real per-epoch cutouts, A→C→B motion-track SVG, flux-vs-wavelength spectrum chart, brightness-vs-time light curve, "Inspect in Explore" / "Open in Compare" links
- **Explore** — zoom/pan sky viewer, epoch/band selector (only real band: Detector 3 SWIR), clickable candidate markers → RA/Dec, spectrum, catalogue match, motion
- **Compare** — 5 modes: **Side-by-Side, Slider, Blink, Difference (A−B only), Overlay** (red/cyan composite); honest alignment-caveat banner for non-A/B pairs
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

**Current status:** both servers were stopped by the system (low memory, idle) — code is untouched, just needs restarting when ready to demo.
