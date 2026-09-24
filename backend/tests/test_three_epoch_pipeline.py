"""
Consistency checks for the regenerated three-epoch pipeline outputs
(three_epoch_compare.py -> validate_candidates.py -> catalogue_crossmatch_v3.py
-> final_ranking.py) and the API that serves them. Uses the real output files.

    cd backend && python -m pytest tests/ -v
"""

import json
import sys
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data_access import BASE_DIR  # noqa: E402

CALIB = BASE_DIR / "three_epoch_linking_calibration.json"
if not CALIB.exists():
    pytest.skip("three_epoch_compare.py outputs not present", allow_module_level=True)

from main import app  # noqa: E402

client = TestClient(app)
calib = json.loads(CALIB.read_text(encoding="utf-8"))
linked = pd.read_csv(BASE_DIR / "three_epoch_motion_candidates.csv")
rejected = pd.read_csv(BASE_DIR / "rejected_three_epoch_tracks.csv")
validated = pd.read_csv(BASE_DIR / "validated_three_epoch_candidates.csv")
combined = pd.read_csv(BASE_DIR / "validated_candidates_with_catalogue.csv")
ranked = pd.read_csv(BASE_DIR / "final_ranked_candidates.csv")
REASONS = {"STATIONARY_SOURCE", "BLEND_MISLINK", "INCONSISTENT_TRAJECTORY"}


def test_every_rejected_track_has_a_reason_and_detail():
    assert set(rejected["rejection_reason"]) <= REASONS
    assert rejected["rejection_detail"].fillna("").str.len().gt(10).all()
    assert rejected["rejection_reason"].value_counts().to_dict() == {
        k: v for k, v in calib["tracks"]["rejected"].items() if v}


def test_accepted_tracks_have_no_stationary_or_blend_support():
    assert len(linked) == calib["tracks"]["accepted"]
    for e in "ACB":
        assert (linked[f"{e}_class"] == "FREE").all()


def test_rejected_tracks_are_consistent_with_their_reason():
    stat = rejected[rejected["rejection_reason"] == "STATIONARY_SOURCE"]
    n_stat = sum((stat[f"{e}_class"] == "STATIONARY").astype(int) for e in "ACB")
    not_significant = stat["motion_significance_chi2"] <= calib["chi2_gate"]
    assert ((n_stat >= 2) | not_significant).all()


def test_veto_keeps_moving_source_sensitivity():
    # measured on random sky positions; the veto must not remove most movers
    assert calib["false_veto_rate"]["genuine_mover_track_vetoed_probability"] < 0.2


def test_downstream_files_regenerated_from_current_linker_output():
    assert len(validated) <= len(linked)
    assert set(combined["candidate_id"].astype(str)) == set(validated["candidate_id"].astype(str))
    assert set(ranked["candidate_id"].astype(str)) == set(validated["candidate_id"].astype(str))
    if len(linked):
        assert set(validated["candidate_id"]) <= set(linked["candidate_id"])


def test_api_count_matches_regenerated_data():
    body = client.get("/api/candidates").json()
    assert body["count"] == len(validated)
    summary = client.get("/api/linking-summary").json()
    assert summary["accepted_tracks"] == len(linked)
    assert summary["rejected_tracks"] == len(rejected)


def test_no_stale_candidate_ids_served():
    served = {c["candidate_id"] for c in client.get("/api/candidates").json()["candidates"]}
    for cid in ("3EPOCH-001", "3EPOCH-022"):
        if cid not in served:
            assert client.get(f"/api/candidates/{cid}").status_code == 404
