"""
Read-only data access layer for the SpectraShift candidate API (NASA Space
Apps "Planet X and SPHEREx" challenge context).

This module ONLY reads already-completed scientific pipeline outputs
(CSV files) and FITS headers from the project root. It never re-runs
detection, matching, validation, or catalogue cross-match, and it never
writes to or modifies the original FITS files or the scientific CSVs.

All CSVs are loaded once at startup and cached in memory; FITS headers
(not pixel data) are also read once at startup.
"""

import math
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd
from astropy.io import fits

BASE_DIR = Path(__file__).resolve().parent.parent

CSV_FILES = {
    "validated_candidates": BASE_DIR / "validated_three_epoch_candidates.csv",
    "catalogue_crossmatch": BASE_DIR / "catalogue_crossmatch_results.csv",
    "validated_with_catalogue": BASE_DIR / "validated_candidates_with_catalogue.csv",
    "final_ranked": BASE_DIR / "final_ranked_candidates.csv",  # optional
}

FITS_FILES = {
    "A": BASE_DIR / "level2_2025W19_2B_0166_3D3_spx_l2b-v20-2025-247.fits",
    "C": BASE_DIR / "level2_2025W22_1B_0226_1D3_spx_l2b-v20-2025-250.fits",
    "B": BASE_DIR / "level2_2025W24_1A_0099_1D3_spx_l2b-v20-2025-252.fits",
}

VALID_CATALOGUE_STATUSES = {"KNOWN_OBJECT", "UNMATCHED_AFTER_CHECKS", "UNCERTAIN"}


def to_native(value: Any) -> Any:
    """Convert a pandas/numpy scalar to a plain, JSON-safe Python value."""

    if value is None:
        return None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        f = float(value)
        return None if math.isnan(f) else f
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, float) and math.isnan(value):
        return None
    if value is pd.NaT:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


def clean_record(record: dict) -> dict:
    """Recursively replace NaN/NaT/numpy scalars with plain JSON-safe values."""
    return {k: to_native(v) for k, v in record.items()}


def df_records(df: Optional[pd.DataFrame]) -> list[dict]:
    if df is None:
        return []
    return [clean_record(r) for r in df.to_dict(orient="records")]


class DataStore:
    """Loads every CSV/FITS-header input once and serves it read-only."""

    def __init__(self) -> None:
        self.dataframes: dict[str, Optional[pd.DataFrame]] = {}
        self.load_errors: dict[str, str] = {}
        self.observations: list[dict] = []
        self.observation_errors: dict[str, str] = {}
        self._load_csvs()
        self._load_fits_headers()

    def _load_csvs(self) -> None:
        for key, path in CSV_FILES.items():
            if not path.exists():
                self.dataframes[key] = None
                self.load_errors[key] = f"file not found: {path.name}"
                continue
            try:
                self.dataframes[key] = pd.read_csv(path)
            except Exception as exc:  # noqa: BLE001 - surfaced via /api/health
                self.dataframes[key] = None
                self.load_errors[key] = f"{type(exc).__name__}: {exc}"

    def _load_fits_headers(self) -> None:
        for epoch, path in FITS_FILES.items():
            if not path.exists():
                self.observation_errors[epoch] = f"file not found: {path.name}"
                continue
            try:
                with fits.open(path) as hdul:
                    header = hdul["IMAGE"].header
                    self.observations.append({
                        "epoch": epoch,
                        "filename": path.name,
                        "obs_id": header.get("OBSID"),
                        "detector": header.get("DETECTOR"),
                        "mjd_obs": header.get("MJD-OBS"),
                        "date_obs": header.get("DATE-OBS"),
                        "naxis1": header.get("NAXIS1"),
                        "naxis2": header.get("NAXIS2"),
                        "ra_center_deg": header.get("CRVAL1"),
                        "dec_center_deg": header.get("CRVAL2"),
                        "bunit": header.get("BUNIT"),
                    })
            except Exception as exc:  # noqa: BLE001 - surfaced via /api/health
                self.observation_errors[epoch] = f"{type(exc).__name__}: {exc}"

        self.observations.sort(key=lambda o: {"A": 0, "C": 1, "B": 2}.get(o["epoch"], 99))

    # -- convenience accessors -------------------------------------------------

    def get(self, key: str) -> Optional[pd.DataFrame]:
        return self.dataframes.get(key)

    def is_loaded(self, key: str) -> bool:
        return self.dataframes.get(key) is not None

    def find_candidate_row(self, df_key: str, candidate_id: str) -> Optional[dict]:
        df = self.get(df_key)
        if df is None or "candidate_id" not in df.columns:
            return None
        mask = df["candidate_id"].astype(str).str.upper() == candidate_id.strip().upper()
        matches = df[mask]
        if len(matches) == 0:
            return None
        return clean_record(matches.iloc[0].to_dict())

    def find_crossmatch_rows(self, candidate_id: str) -> list[dict]:
        df = self.get("catalogue_crossmatch")
        if df is None or "candidate_id" not in df.columns:
            return []
        mask = df["candidate_id"].astype(str).str.upper() == candidate_id.strip().upper()
        return df_records(df[mask])

    def known_candidate_ids(self) -> set[str]:
        ids: set[str] = set()
        for key in ("validated_with_catalogue", "validated_candidates", "catalogue_crossmatch"):
            df = self.get(key)
            if df is not None and "candidate_id" in df.columns:
                ids.update(df["candidate_id"].astype(str).str.upper().tolist())
        return ids


# Loaded once at process startup; FastAPI endpoints read from this singleton.
store = DataStore()
