"""
Tests for the two-epoch (~6-month) candidate pipeline.

1. Synthetic: controlled star fields (never the real FITS files) with an
   injected large position change, a small bright shift, and look-alikes
   (edge source, flagged pixel, single-pixel spike) that must be rejected.
2. Real results: sanity checks on two_epoch_candidates.json -- it matches a
   fresh run, uses only the Jun 19 / Dec 17 2025 pair, every candidate lies
   in the shared footprint, and rates use the 181.774125-day baseline.
3. API: /api/candidates routes serve those results.

    cd backend && python -m pytest tests/ -v
"""

import io
import json
import math
import sys
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from scipy.special import erf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import two_epoch_candidates as tec  # noqa: E402

# ---------------------------------------------------------------------------
# 1. synthetic star fields
# ---------------------------------------------------------------------------

SKY, NOISE, FWHM = 0.2, 0.02, 1.6
SHAPE = (300, 400)


def _psf(shape, x, y, flux, fwhm=FWHM):
    """Pixel-integrated Gaussian point source (undersampled, like SPHEREx)."""
    s = fwhm / 2.3548 * math.sqrt(2)
    yy, xx = np.mgrid[0:shape[0], 0:shape[1]]
    fx = 0.5 * (erf((xx + 0.5 - x) / s) - erf((xx - 0.5 - x) / s))
    fy = 0.5 * (erf((yy + 0.5 - y) / s) - erf((yy - 0.5 - y) / s))
    return flux * fx * fy


MOVER_A = (100.3, 150.6)
MOVER_B = (180.4, 190.2)
SHIFT_A = (250.2, 80.3)
SHIFT_B = (251.7, 80.3)
EDGE_ONLY_A = (2.2, 60.4)
FLAGGED_ONLY_A = (60.4, 250.3)
SPIKE_B = (300, 120)
INJECTED = [MOVER_A, MOVER_B, SHIFT_A, SHIFT_B, EDGE_ONLY_A, FLAGGED_ONLY_A, SPIKE_B]


@pytest.fixture(scope="module")
def synthetic():
    rng = np.random.default_rng(20250619)
    stars = []
    while len(stars) < 250:
        x, y = rng.uniform(10, SHAPE[1] - 10), rng.uniform(10, SHAPE[0] - 10)
        if all(math.hypot(x - sx, y - sy) > 8 for sx, sy, _ in stars) and \
                all(math.hypot(x - ix, y - iy) > 12 for ix, iy in INJECTED):
            stars.append((x, y, float(10 ** rng.uniform(0.0, 1.5))))
    a = np.full(SHAPE, SKY) + rng.normal(0, NOISE, SHAPE)
    b = np.full(SHAPE, SKY) + rng.normal(0, NOISE, SHAPE)
    for x, y, f in stars:
        a += _psf(SHAPE, x, y, f)
        b += _psf(SHAPE, x + rng.normal(0, 0.02), y + rng.normal(0, 0.02), f)
    a += _psf(SHAPE, *MOVER_A, 1.2)
    b += _psf(SHAPE, *MOVER_B, 1.2)
    a += _psf(SHAPE, *SHIFT_A, 20.0)
    b += _psf(SHAPE, *SHIFT_B, 20.0)
    a += _psf(SHAPE, *EDGE_ONLY_A, 1.5)
    a += _psf(SHAPE, *FLAGGED_ONLY_A, 1.5)
    b[SPIKE_B[1], SPIKE_B[0]] += 2.0
    bad_a = np.zeros(SHAPE, bool)
    bad_a[250, 60] = True
    valid = np.ones(SHAPE, bool)
    res = tec.find_candidates(a, b, valid, bad_a=bad_a, bad_b=np.zeros(SHAPE, bool))
    return res


def _near(src, xy, r=1.0):
    return src is not None and math.hypot(src["x"] - xy[0], src["y"] - xy[1]) <= r


def test_synthetic_position_change_recovered(synthetic):
    pairs = [c for c in synthetic["candidates"] if c["kind"] == "possible_position_change"]
    assert len(pairs) == 1
    c = pairs[0]
    assert _near(c["A"], MOVER_A) and _near(c["B"], MOVER_B)
    expected = math.hypot(MOVER_B[0] - MOVER_A[0], MOVER_B[1] - MOVER_A[1])
    assert c["separation_px"] == pytest.approx(expected, abs=0.3)


def test_synthetic_small_shift_recovered(synthetic):
    shifts = [c for c in synthetic["candidates"] if c["kind"] == "shifted_match"]
    assert len(shifts) == 1
    assert _near(shifts[0]["A"], SHIFT_A, 0.3) and _near(shifts[0]["B"], SHIFT_B, 0.3)
    assert shifts[0]["significance"] > tec.STATIONARY_NSIGMA


def test_synthetic_stationary_stars_rejected(synthetic):
    """Only the injected mover and shift survive: every one of the 250
    stationary stars is rejected, as are the edge / flagged / spike cases."""
    assert len(synthetic["candidates"]) == 2
    assert synthetic["rejected"][tec.VETO_STATIONARY] >= 200
    for c in synthetic["candidates"]:
        for src in (c["A"], c["B"]):
            assert any(_near(src, xy) for xy in (MOVER_A, MOVER_B, SHIFT_A, SHIFT_B))


def test_synthetic_lookalikes_rejected_for_the_right_reason(synthetic):
    rejected = synthetic["rejected"]
    assert rejected.get(tec.VETO_EDGE, 0) >= 1
    assert rejected.get(tec.VETO_FLAGGED, 0) >= 1
    assert rejected.get(tec.VETO_MORPHOLOGY, 0) >= 1


def test_synthetic_position_error_model_is_measured(synthetic):
    model = synthetic["position_scatter"]
    assert 0 < model["sigma_sys_px"] < 0.2
    assert model["bins"], "error model must come from matched sources"


def test_zero_displacement_is_stationary():
    rng = np.random.default_rng(1)
    a = np.full(SHAPE, SKY) + rng.normal(0, NOISE, SHAPE)
    b = np.full(SHAPE, SKY) + rng.normal(0, NOISE, SHAPE)
    for k in range(120):
        x, y = 20 + (k % 12) * 30, 20 + (k // 12) * 26
        a += _psf(SHAPE, x + 0.3, y + 0.7, 8.0)
        b += _psf(SHAPE, x + 0.3, y + 0.7, 8.0)
    res = tec.find_candidates(a, b, np.ones(SHAPE, bool))
    assert res["candidates"] == []
    assert res["rejected"][tec.VETO_STATIONARY] == 120


# ---------------------------------------------------------------------------
# 2. real ~6-month results
# ---------------------------------------------------------------------------

real = pytest.mark.skipif(not (tec.DATA_DIR / "metadata.json").is_file(),
                          reason="data/time_compare_6month not present")

BASELINE_DAYS = 181.774125


@pytest.fixture(scope="module")
def stored():
    return json.loads(tec.RESULT_JSON.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def meta():
    return json.loads((tec.DATA_DIR / "metadata.json").read_text(encoding="utf-8"))


@real
def test_stored_results_match_a_fresh_run(stored):
    fresh = tec.run_real_pair()
    assert fresh["pipeline"] == stored["pipeline"] == tec.PIPELINE_VERSION
    assert fresh["counts"] == stored["counts"]
    assert fresh["rejected_by_reason"] == stored["rejected_by_reason"]
    assert [c["candidate_id"] for c in fresh["candidates"]] == [c["candidate_id"] for c in stored["candidates"]]
    for f, s in zip(fresh["candidates"], stored["candidates"]):
        assert f["earlier"] == s["earlier"] and f["later"] == s["later"]


@real
def test_only_the_six_month_pair_is_used(stored, meta):
    assert stored["inputs"]["earlier"]["file"] == meta["epoch_A"]["file"] == \
        "level2_2025W25_1B_0652_1D3_spx_l2b-v20-2025-253.fits"
    assert stored["inputs"]["later"]["file"] == meta["epoch_B"]["file"] == \
        "level2_2025W51_1A_0594_2D3_spx_l2b-v21-2025-354.fits"
    assert stored["inputs"]["earlier"]["date"].startswith("2025-06-19")
    assert stored["inputs"]["later"]["date"].startswith("2025-12-17")
    assert stored["inputs"]["time_baseline_days"] == pytest.approx(BASELINE_DAYS, abs=1e-5)
    source = Path(tec.__file__).read_text(encoding="utf-8")
    for old in ("2025W19", "2025W22", "2025W24", "2025-05-09", "2025-05-27", "2025-06-09", "three_epoch"):
        assert old not in source


@real
def test_every_candidate_is_consistent(stored, meta):
    from astropy.io import fits
    valid = fits.getdata(tec.DATA_DIR / "overlap_mask.fits") > 0
    assert stored["counts"]["total"] == len(stored["candidates"])
    for c in stored["candidates"]:
        assert c["kind"] in ("possible_position_change", "shifted_match", "seen_only_earlier", "seen_only_later")
        assert c["earlier_date"] == meta["epoch_A"]["date"]
        assert c["later_date"] == meta["epoch_B"]["date"]
        assert c["status"] == "passed_current_checks"
        assert c["caveats"]
        for key in ("earlier", "later"):
            if c[key]:
                assert valid[int(round(c[key]["y"])), int(round(c[key]["x"]))]
        if c["earlier"] and c["later"]:
            d = c["angular_displacement_arcsec"]
            assert d is not None and math.isfinite(d) and d >= 0
            assert c["apparent_motion_arcsec_per_day"] == pytest.approx(d / BASELINE_DAYS, abs=1e-4)
        else:
            assert c["angular_displacement_arcsec"] is None
            assert c["apparent_motion_arcsec_per_day"] is None


@real
def test_no_discovery_wording(stored):
    text = json.dumps(stored).lower()
    for word in ("planet", "discover", "confirmed moving", "orbit determined"):
        assert word not in text


# ---------------------------------------------------------------------------
# 3. API
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    from main import app
    return TestClient(app)


@real
def test_candidates_api(client, stored):
    r = client.get("/api/candidates")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == stored["counts"]["total"]
    assert body["earlier_date"].startswith("2025-06-19")
    assert body["later_date"].startswith("2025-12-17")
    assert body["rejected_by_reason"] == stored["rejected_by_reason"]
    assert all("kind_label" in c for c in body["candidates"])


@real
@pytest.mark.parametrize("image", ["earlier", "later"])
def test_markers_api(client, stored, image):
    r = client.get(f"/api/candidates/markers?image={image}")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] + len(body["outside_display"]) == stored["counts"]["total"]
    for m in body["markers"]:
        assert 0 <= m["x_frac"] <= 1 and 0 <= m["y_frac"] <= 1


@real
def test_marker_image_param_validated(client):
    assert client.get("/api/candidates/markers?image=A").status_code == 422


@real
def test_candidate_detail_and_cutouts(client, stored):
    if not stored["candidates"]:
        pytest.skip("no candidates to inspect")
    cid = stored["candidates"][0]["candidate_id"]
    r = client.get(f"/api/candidates/{cid.lower()}")
    assert r.status_code == 200
    detail = r.json()
    assert detail["candidate_id"] == cid and detail["cutouts"]
    for url in detail["cutouts"][0].values():
        if url in ("earlier", "later"):
            continue
        img = client.get(url)
        assert img.status_code == 200 and img.headers["content-type"] == "image/png"
        assert Image.open(io.BytesIO(img.content)).size == (200, 200)


@real
def test_unknown_candidate_404(client):
    assert client.get("/api/candidates/3EPOCH-001").status_code == 404
    assert client.get("/api/candidates/SX6M-999/cutout/earlier").status_code == 404
