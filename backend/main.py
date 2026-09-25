"""
SpectraShift API -- NASA Space Apps 2026 "Planet X and SPHEREx".

Read-only FastAPI service with three parts:
  - Spectral View: the 102-channel SPHEREx mosaic (spectral_api.py)
  - Time Compare: the verified ~6-month pair, earlier observation
    2025-06-19 and later observation 2025-12-17 (time_compare_6month.py)
  - Candidates: two-epoch position/brightness-change candidates found in
    that same pair (candidates_api.py, two_epoch_candidates.py)

Nothing here is labelled Planet X, a discovery, a new planet or a confirmed
moving object: candidates are possible changes that passed the current
checks, for further inspection.
"""

from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import time_compare_6month
from candidates_api import router as candidates_router
from spectral_api import router as spectral_router
from time_compare_6month import router as six_month_router
import two_epoch_candidates

app = FastAPI(
    title="SpectraShift API",
    description=(
        "SpectraShift -- a SPHEREx spectral and ~6-month two-epoch sky "
        "explorer. Read-only API over the 102-channel SPHEREx mosaic, the "
        "Jun 19 / Dec 17 2025 observation pair and the two-epoch candidates "
        "found in it. Candidates are preliminary; nothing here is a "
        "confirmed discovery."
    ),
    version="2.0.0",
)

# CORS: permissive; the API is read-only and serves public data.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(spectral_router)
app.include_router(six_month_router)
app.include_router(candidates_router)


@app.get("/api/health")
def health() -> dict[str, Any]:
    """Service + data-availability health check."""
    missing = time_compare_6month._missing()
    results = two_epoch_candidates.RESULT_JSON
    return {
        "status": "ok" if not missing else "degraded",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "time_compare_6month": {"available": not missing, "missing_files": missing},
        "two_epoch_candidates": {
            "results_file": results.name,
            "precomputed": results.is_file(),
            "pipeline": two_epoch_candidates.PIPELINE_VERSION,
        },
        "note": (
            "Preliminary two-epoch candidates only. No candidate is labelled "
            "Planet X, a discovery, or a confirmed moving object."
        ),
    }
