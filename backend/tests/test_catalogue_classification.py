"""
Checks the v3 catalogue classification outputs (catalogue_crossmatch_v3.py)
against its own stated rules, and that the API exposes the evidence.
Runs against the real CSV outputs; skipped if they predate v3.

    cd backend && python -m pytest tests/ -v
"""

import sys
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data_access import BASE_DIR  # noqa: E402

COMBINED = BASE_DIR / "validated_candidates_with_catalogue.csv"
df = pd.read_csv(COMBINED)
if "catalogue_explanation" not in df.columns:
    pytest.skip("catalogue outputs predate v3 classification", allow_module_level=True)

from main import app  # noqa: E402

client = TestClient(app)
STATUSES = {"KNOWN_OBJECT", "UNMATCHED_AFTER_CHECKS", "UNCERTAIN"}
CHI2_ACCEPT = 13.816


def test_every_candidate_classified_with_reason():
    validated = pd.read_csv(BASE_DIR / "validated_three_epoch_candidates.csv")
    assert len(df) == len(validated)
    assert set(df["final_catalogue_status"]) <= STATUSES
    assert df["status_reason"].fillna("").str.len().gt(20).all()


def test_unmatched_only_after_all_required_checks_succeeded():
    unmatched = df[df["final_catalogue_status"] == "UNMATCHED_AFTER_CHECKS"]
    assert unmatched["services_failed"].fillna("").eq("").all()
    for e in "ACB":
        assert (unmatched[f"{e}_chi2"].isna() | (unmatched[f"{e}_chi2"] > CHI2_ACCEPT)).all()


def test_known_objects_are_strong_associations():
    known = df[df["final_catalogue_status"] == "KNOWN_OBJECT"]
    assert known["match_confidence"].isin(["HIGH", "MEDIUM"]).all()
    linked = known[known["catalogue_explanation"] == "LINKED_KNOWN_STARS"]
    for e in "ACB":
        assert (linked[f"{e}_chi2"] <= CHI2_ACCEPT).all()
        assert (linked[f"{e}_n_consistent"] == 1).all()
    assert (linked["joint_p_chance"] <= 1e-3).all()


def test_no_discovery_language_anywhere():
    text = " ".join(df["status_reason"].fillna("")).lower()
    for phrase in ("planet x", "new planet", "discovery", "previously unknown"):
        assert phrase not in text


@pytest.mark.parametrize("cid", df["candidate_id"].astype(str).tolist()[:3])
def test_api_exposes_catalogue_evidence(cid):
    r = client.get(f"/api/candidates/{cid}")
    assert r.status_code == 200
    cat = r.json()["catalogue"]
    assert cat["final_catalogue_status"] in STATUSES
    assert cat["status_reason"]
    assert cat["catalogues_checked"]
    assert [p["epoch"] for p in cat["per_epoch"]] == ["A", "C", "B"]
    assert cat["observed_motion"]["rate_arcsec_per_day"] is not None


def test_candidates_summary_exposes_reason():
    rows = client.get("/api/candidates").json()["candidates"]
    assert len(rows) == len(df)
    assert all(r.get("status_reason") for r in rows)
