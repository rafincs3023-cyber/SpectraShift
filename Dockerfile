# SpectraShift backend (FastAPI) for Railway.
#
# Built from the repository ROOT because the backend reads
# data/time_compare_6month/ and the two root-level Level-2 source frames of
# the ~6-month pair via BASE_DIR = project root.
#
# The ~3.1 GB 102-channel spectral mosaic is not in Git. In production set
# SPECTRASHIFT_SPECTRAL_BACKEND=r2 plus the R2_* variables: Spectral View then
# reads the lossless tile bundle from private Cloudflare R2 on demand and
# never downloads the FITS files (docs/DEPLOYMENT.md). Local mode can instead
# use the FITS files from a volume mounted at /app/data/spherex.

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# dependencies first, so code/data changes don't reinstall them
COPY backend/requirements.txt backend/requirements.txt
RUN pip install -r backend/requirements.txt

COPY . .

# writable render caches; data/spherex is the volume mount point
RUN mkdir -p data/spherex backend/preview_cache backend/cutout_cache

EXPOSE 8000

# Railway provides $PORT; default to 8000 elsewhere
CMD ["sh", "-c", "cd /app/backend && exec python -m uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
