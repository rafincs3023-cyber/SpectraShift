# SpectraShift — Architecture & Data Flow

SpectraShift has two layers:

1. **FastAPI backend** (`backend/`), which is read-only over real SPHEREx products. It serves:
   - the 102-channel spectral data
   - the verified ~6-month pair
   - the two-epoch candidates found in that pair

   The candidate pipeline is a small, deterministic module whose results are stored as JSON and regenerated with one command.
2. **React frontend** (`frontend/`), the public interface.

The current product story runs like this. SPHEREx data feeds two tracks:

- **Wavelength:** the 102-channel spectral mosaic, for spectral exploration.
- **Time:** the Jun 19, 2025 and Dec 17, 2025 observations are registered into a ~6-month comparison, then screened for two-epoch change/motion candidates.

Both tracks end in public web exploration.

## End-to-end flow

```mermaid
flowchart TB
    IRSA["NASA SPHEREx data<br/>NASA/IPAC IRSA"]
    IRSA --> MOS["102-channel spectral mosaic<br/>IRSA SPHEREx Mosaic Tool<br/>RA 155.352°, Dec −42.700°"]
    IRSA --> L2["Level-2 images, detector D3<br/>2025-06-19 and 2025-12-17"]

    subgraph B1["Spectral: same sky, same time, 102 wavelengths"]
        MOS --> CT["Channel table + wavelength<br/>calibration (D1–D6, 0.743–5.009 µm)"]
        CT --> PV["Channel previews"]
        CT --> SPEC["Spectrum API<br/>(pixel or RA/Dec → 102 values)"]
    end

    subgraph B2["Temporal: same sky, 181.77 days apart"]
        L2 --> REG["Later image reprojected<br/>onto the earlier grid"]
        REG --> FRAME["Largest fully-valid common frame<br/>1016 × 346 px, 99.97% valid"]
        FRAME --> DIFF["Difference: Later − Earlier"]
    end

    subgraph B3["Two-epoch candidate screening"]
        REG --> BKG["Background / noise maps"]
        BKG --> PSF["PSF matching<br/>(sharper image blurred)"]
        PSF --> DET["Matched-filter detection ≥ 5σ<br/>in each image"]
        DET --> XM["Cross-match + measured<br/>position-error model"]
        XM --> FORCED["Forced photometry in<br/>the other image"]
        FORCED --> VETO["Vetoes: edge · SPHEREx flags ·<br/>corrupted pixels · shape · halo ·<br/>blend · centroid · difference sign"]
        VETO --> OUT["two_epoch_candidates.json"]
    end

    subgraph API["FastAPI backend"]
        A1["/api/spectral/*"]
        A2["/api/compare/6month/*"]
        A3["/api/candidates/*"]
    end

    PV --> A1
    SPEC --> A1
    FRAME --> A2
    DIFF --> A2
    OUT --> A3

    A1 --> UI["React public web interface"]
    A2 --> UI
    A3 --> UI
    UI --> P1["Spectral View"]
    UI --> P2["Time Compare<br/>(Side by Side · Slider · Blink · Difference · Overlay)"]
    UI --> P3["Explore · Candidates · Candidate Detail · About · Help"]
```

## Components

| Component | Files | Role |
|---|---|---|
| Spectral data service | `backend/spectral_data.py`, `backend/spectral_api.py`, `backend/spectral_r2.py`, `backend/build_spectral_cache.py`, `backend/build_r2_spectral_bundle.py` | 102-channel mosaic: channel table, previews, spectra (local FITS/cache or private R2 tiles) |
| ~6-month compare | `backend/time_compare_6month.py`, `data/time_compare_6month/`, `build_6month_difference.py` | Serves the verified registered pair; chooses the fully-valid display frame from `overlap_mask.fits` |
| Two-epoch pipeline | `backend/two_epoch_candidates.py` | Detection, matching, vetoes, pairing; writes `two_epoch_candidates.json` |
| Candidate API | `backend/candidates_api.py` | Candidate list, markers on the display frame, details, real-pixel cutouts |
| Rendering helpers | `backend/images.py` | asinh stretch and red/blue difference rendering |
| Tests | `backend/tests/` | Spectral, ~6-month and two-epoch (synthetic + real-data sanity + API) tests |
| Frontend | `frontend/src/` | Home, Spectral View, Time Compare, Explore, Candidates, Candidate Detail, About, Help |

The earlier short-baseline work is kept in `archive/short_baseline_31day/` for repository history only. Nothing there is imported by the backend or shown in the product, and it is excluded from the production image (`.dockerignore`).

## Design principles

- **Only the ~6-month pair** feeds temporal exploration and candidates.
- **Measured, not assumed:** the FWHM, noise, alignment residual and position-error model are all measured from the two images. Thresholds are derived from trial counts (for example, the 5σ stationary tolerance).
- **No hidden failures:** missing values are `null`/"—"; every rejection reason is counted and reported.
- **Small browser payloads:** the browser receives only PNG previews, cutouts and JSON; FITS files are never sent to it.
