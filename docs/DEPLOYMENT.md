# Deployment notes

No hosting provider is configured in this repository yet. This page records what a public deployment needs.

## Requirements

| Part | Needs |
|---|---|
| Backend (FastAPI) | Python 3.11+, `backend/requirements.txt`, and the data files below on a persistent volume |
| Frontend | Static hosting of `frontend/dist/` (`npm run build`) |

### Data the backend needs at runtime (not all in Git)

| Data | Size | In Git? |
|---|---|---|
| `data/spherex/SpectraShift_Part1_16.fits.gz`, `SpectraShift_Remaining86.fits.gz` (102-channel mosaic, source of truth) | ~3.1 GB | No — kept privately in Cloudflare R2; **not** needed on the server in R2 mode |
| Lossless Spectral View bundle (`data/spherex/r2_bundle/`: manifest, 1,794 tiles, 102 previews) | ~3.1 GB | No — uploaded to private R2 under `spectral-cache/v1/` |
| ~6-month pair source frames (2 × `level2_*.fits`; headers for detector/PSF, FLAGS for the candidate vetoes) | ~143 MB | Yes |
| `data/time_compare_6month/` (verified ~6-month products + `two_epoch_candidates.json`) | ~10 MB | Yes |
| Optional `data/spherex/cache/` cube | ~3 GB | No (rebuild with `backend/build_spectral_cache.py`) |

In production the Spectral View runs in **R2 mode** and never downloads the FITS files (see below). Local mode (the default) still reads the FITS files / local cache directly.

## Railway (backend service)

The repository root contains a `Dockerfile` for the backend (Python 3.11, runs `uvicorn main:app` from `backend/` on `$PORT`). Railway detects it automatically.

1. Service settings: **Root Directory = repository root** (not `/backend` — the backend reads root-level data). Builder: Dockerfile.
2. Environment variables (names only — never commit values):

   | Variable | Value |
   |---|---|
   | `SPECTRASHIFT_SPECTRAL_BACKEND` | `r2` |
   | `R2_ENDPOINT_URL` | the account's S3 API endpoint (`https://<account-id>.r2.cloudflarestorage.com`) |
   | `R2_BUCKET` | `spectrashift-data` |
   | `R2_ACCESS_KEY_ID` | access key of a **read-only** R2 API token |
   | `R2_SECRET_ACCESS_KEY` | its secret |
   | `R2_PREFIX` | `spectral-cache/v1/` |
   | `SPECTRASHIFT_R2_TILE_CACHE_MB` (optional) | in-memory tile cache, default 48 |
   | `SPECTRASHIFT_R2_PREVIEW_CACHE_MB` (optional) | in-memory preview cache, default 48 |

   Create the token in Cloudflare → R2 → *Manage API tokens* with **Object Read only** permission, scoped to the `spectrashift-data` bucket. The deployed backend never writes to R2.
3. Health check path: `/api/health`. Spectral status: `/api/spectral/status` (shows `backend: r2`, bundle version and cache use).
4. No volume and no large download is needed: startup reads nothing from R2; the first Spectral View request fetches the ~0.6 MB manifest, each spectrum fetches one ~1.7 MB tile, each channel view one ~1.2 MB preview (proxied through FastAPI with `Cache-Control: public, max-age=86400`). The bucket stays private.

## Spectral View production bundle (R2)

The bundle is a **lossless** re-organisation of the 102-channel IMAGE cubes — same float32 values, bit for bit, every pixel, NaN preserved — so a spectrum needs one small object instead of the whole 3 GB cube.

| Object | Format |
|---|---|
| `spectral-cache/v1/manifest.json` | schema, source files (size + SHA-256), 102-channel table, 2927 × 2487 grid, `float32`, WCS header cards, unit, channel statistics, wavelength range, source-channel mapping, tile index (bounds, shape, bytes, SHA-256), preview index, validation results |
| `spectral-cache/v1/tiles/yNNN_xNNN.npy` | NumPy `.npy`, little-endian float32, shape `[tile_h, tile_w, 102]` (`[y, x, channel]`); 64 × 64 pixels (edge tiles smaller); 46 × 39 = 1,794 tiles covering every pixel exactly once |
| `spectral-cache/v1/previews/chNNN.png` | default display preview per channel (asinh, 0.5–99.5 %, ≤ 1200 px, north up, transparent no-data) — display only |

Build and verify locally (needs the two FITS files in `data/spherex/`):

```bash
python backend/build_spectral_cache.py          # local memmap cube (~3 GB, once)
python backend/build_r2_spectral_bundle.py      # tiles + previews + manifest, then full verification
python backend/build_r2_spectral_bundle.py --verify-only
```

Verification compares all 742,503,798 values bit for bit with the cube, checks sample pixels bit for bit directly against the `.fits.gz` files, coverage, checksums, dtype, channel order, WCS, previews and the frontend metadata, and stores the result in the manifest. The upload script refuses a bundle whose validation did not pass.

Upload (one-off, from your machine, with a **separate read-and-write** R2 token that is not given to Railway):

```bash
# set R2_ENDPOINT_URL, R2_BUCKET, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY (write token), R2_PREFIX in your shell
python backend/upload_r2_spectral_bundle.py --dry-run
python backend/upload_r2_spectral_bundle.py --verify-remote
```

The uploader writes only under the prefix (never the FITS objects), never deletes, resumes by skipping identical objects, and uploads `manifest.json` last.

Test R2 mode locally without credentials:

```bash
cd backend
SPECTRASHIFT_SPECTRAL_BACKEND=r2 SPECTRASHIFT_R2_LOCAL_BUNDLE_DIR=../data/spherex/r2_bundle python -m uvicorn main:app --port 8000
```

In R2 mode only the default preview rendering is served; other `stretch` / `plow` / `phigh` / `max_size` values return HTTP 422 `render_unsupported_in_r2_mode` (they need the full plane — use local mode). The website only uses the default.

### R2 storage

| Content | Bytes | GB |
|---|---|---|
| Original FITS (source of truth) | 3,112,969,223 | 3.11 |
| Tiles (1,794) | 2,970,244,824 | 2.97 |
| Previews (102) + manifest | 124,965,508 | 0.12 |
| **Total** | **6,208,179,555** | **6.21 (5.78 GiB)** |

## API URL configuration

- Leave `VITE_API_BASE_URL` **unset** when the frontend and backend are served from the same origin (e.g. a reverse proxy routing `/api/*` to the backend). A production build then calls same-origin `/api/...` paths and contains no localhost URLs.
- Set `VITE_API_BASE_URL=https://<backend-host>` at build time when the API is on a different origin. The backend already allows cross-origin requests.

## Suggested single-host layout

```
https://<host>/          → frontend/dist (static)
https://<host>/api/*     → uvicorn main:app (backend/, working directory backend/)
```

Start command for the backend: `python -m uvicorn main:app --host 0.0.0.0 --port $PORT` (run from `backend/`).

## Production smoke test

1. `GET /api/health` → `status: ok`
2. `GET /api/spectral/metadata` → `total_channels: 102`
3. `GET /api/compare/6month` → baseline 181.77 days; previews return PNG
4. `GET /api/candidates` → two-epoch results with `earlier_date` 2025-06-19 and `later_date` 2025-12-17; `GET /api/candidates/markers?image=earlier` → markers
5. Pages `/`, `/spectral`, `/compare`, `/explore`, `/candidates`, `/candidates/SX6M-001`, `/about`, `/help` load without console errors; no request downloads a FITS file.
