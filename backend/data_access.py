"""
Shared paths for the SpectraShift backend.

Every active route reads only:
  - data/time_compare_6month/  (the verified Jun 19 / Dec 17 2025 pair and
    its two-epoch candidate results), plus the two Level-2 source frames of
    that pair named in its metadata.json, and
  - the 102-channel spectral data (local cache or private R2; spectral_*.py).
"""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
