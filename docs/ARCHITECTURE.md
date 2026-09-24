# SpectraShift — Architecture & Data Flow

SpectraShift has three layers:

1. **Offline science pipeline** (Python scripts at the project root) that turns real SPHEREx FITS products into verified derived data.
2. **FastAPI backend** (`backend/`) — read-only over those products; it renders previews and serves JSON, but never re-runs detection, linking or catalogue classification.
3. **React frontend** (`frontend/`) — the public interface.

## End-to-end flow

```mermaid
flowchart TB
    IRSA["NASA SPHEREx data<br/>NASA/IPAC IRSA"]
    IRSA --> L2["Level-2 spectral images<br/>(single exposures, FITS)"]
    IRSA --> MOS["102-channel spectral mosaic<br/>IRSA SPHEREx Mosaic Tool<br/>RA 155.352°, Dec −42.700°"]

    subgraph B1["Branch 1 — Spectral (same sky, same time, 102 wavelengths)"]
        MOS --> CT["Channel table + wavelength<br/>calibration (D1–D6, 0.743–5.009 µm)"]
        CT --> PV["Channel previews<br/>(asinh stretch, NaN transparent)"]
        CT --> SPEC["Spectrum API<br/>(pixel or RA/Dec → 102 values)"]
    end

    subgraph B2["Branch 2 — Multi-epoch (same sky, different times)"]
        L2 --> PAIR["~6-month pair<br/>2025-06-19 / 2025-12-17, D3"]
        L2 --> E31["31-day epochs A / C / B"]
        PAIR --> REG["WCS registration<br/>(B reprojected onto A's grid)"]
        REG --> FRAME["Largest fully-valid common frame<br/>1016 × 346 px, 99.97% valid"]
        FRAME --> DIFF["Difference B − A"]
        E31 --> REG31["A/B registration + A − B difference"]
    end

    subgraph B3["Branch 3 — Moving-source search"]
        E31 --> EXT["Source extraction<br/>DAOStarFinder 7σ, flagged pixels masked"]
        EXT --> LINK["A → C → B linking<br/>constant-velocity prediction"]
        LINK --> STAT["Stationary-source veto<br/>calibrated astrometry, sky coordinates"]
        STAT --> BLEND["Blend / bright-star-halo<br/>mislink veto"]
        BLEND --> TRAJ["Trajectory validation"]
        TRAJ --> CATV["Catalogue classification<br/>Gaia DR3 (epoch-propagated),<br/>SIMBAD, JPL sb_ident + Horizons"]
        CATV --> RANK["Priority ranking"]
    end

    subgraph API["FastAPI backend"]
        A1["/api/spectral/*"]
        A2["/api/compare/6month/*<br/>/api/compare/* · /api/observations/*"]
        A3["/api/linking-summary<br/>/api/candidates/*"]
    end

    PV --> A1
    SPEC --> A1
    FRAME --> A2
    DIFF --> A2
    REG31 --> A2
    RANK --> A3
    STAT -. "rejected tracks + reasons" .-> A3

    A1 --> UI["React public web interface"]
    A2 --> UI
    A3 --> UI
    UI --> P1["Spectral View"]
    UI --> P2["Time Compare<br/>(Side by Side · Slider · Blink · Difference · Overlay)"]
    UI --> P3["Candidates · Explore · About · Help"]
```

## Components

| Component | Files | Role |
|---|---|---|
| Spectral data service | `backend/spectral_data.py`, `backend/spectral_api.py`, `backend/build_spectral_cache.py` | Reads the two mosaic FITS files (16 + 86 channels) directly or from an optional memory-mapped cube; channel table, previews, spectra |
| ~6-month compare | `backend/time_compare_6month.py`, `data/time_compare_6month/`, `build_6month_difference.py` | Serves the verified registered pair; chooses the fully-valid display frame from `overlap_mask.fits` |
| 31-day compare + candidates | `backend/main.py`, `backend/images.py`, `backend/data_access.py`, `backend/spectrum.py` | Epoch previews, A − B difference, candidate JSON, linking summary |
| Linker + vetoes | `three_epoch_compare.py` | Detection, calibration, linking, stationary/blend/trajectory vetoes; writes candidates, rejected tracks, calibration |
| Validation | `validate_candidates.py` | Trajectory, rate, C-prediction and flux consistency |
| Catalogue classification | `catalogue_crossmatch_v3.py` | Epoch-propagated, uncertainty-aware catalogue matching and status reasons |
| Ranking | `final_ranking.py` | Combines validation and catalogue status |
| Sensitivity test | `test_linker_injection.py` | Injection–recovery of synthetic movers |
| Frontend | `frontend/src/` | Pages: Home, Spectral View, Compare, Explore, Candidates, Candidate Detail, About, Help |

## Design principles

- **Read-only API:** the web tier serves verified products; heavy science runs offline and is reproducible from scripts.
- **Sky coordinates everywhere** for cross-epoch tests; pixel registration only where a product was explicitly reprojected.
- **No hidden failures:** missing values are `null`/"—"; rejected tracks and failed services are recorded, not dropped.
- **Small browser payloads:** the browser only receives PNG previews and JSON; FITS files are never sent to it.
