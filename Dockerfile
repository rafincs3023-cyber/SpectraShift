# SpectraShift backend (FastAPI) for Railway.
#
# Built from the repository ROOT because the backend reads root-level runtime
# data (31-day Level-2 FITS frames, pipeline CSV/JSON outputs) and
# data/time_compare_6month/ via BASE_DIR = project root.
#
# The ~3.1 GB 102-channel spectral mosaic is not in Git: mount a persistent
# volume at /app/data/spherex containing SpectraShift_Part1_16.fits.gz and
# SpectraShift_Remaining86.fits.gz (or set SPECTRASHIFT_SPHEREX_DIR to the
# volume path). Everything else works without it.

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
