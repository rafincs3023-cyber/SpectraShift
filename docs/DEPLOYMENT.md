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
| `data/spherex/SpectraShift_Part1_16.fits.gz`, `SpectraShift_Remaining86.fits.gz` (102-channel mosaic) | ~3.1 GB | No — upload to the server volume |
| 31-day Level-2 frames (3 × `level2_*.fits` at the project root) | ~215 MB | Yes |
| `data/time_compare_6month/` (verified ~6-month products) | ~10 MB | Yes |
| Pipeline CSV/JSON outputs at the project root | < 15 MB | Yes |
| Optional `data/spherex/cache/` cube | ~3 GB | No (rebuild with `backend/build_spectral_cache.py`) |

The Spectral View cannot work on a host without the ~3.1 GB mosaic files, so a platform without a persistent volume (or one that only deploys from Git) is not sufficient on its own.

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
4. `GET /api/candidates` → `count: 0`; `GET /api/linking-summary` → 725 tracks, 0 accepted
5. Pages `/`, `/spectral`, `/compare`, `/compare?dataset=31day`, `/candidates`, `/about`, `/help` load without console errors; no request downloads a FITS file.
