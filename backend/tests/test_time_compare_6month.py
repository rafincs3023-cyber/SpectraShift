"""
~6-month Time Compare route tests, run against the REAL products in
data/time_compare_6month/ (no mock data), plus a regression check that the
original A/C/B 31-day Compare routes still respond. Skipped if the
~6-month products are not present.

    cd backend && python -m pytest tests/ -v
"""

import io
import json
import sys
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import time_compare_6month  # noqa: E402

if time_compare_6month._missing():
    pytest.skip("data/time_compare_6month products not present", allow_module_level=True)

from main import app  # noqa: E402

client = TestClient(app)


@pytest.fixture(scope="module")
def pair():
    r = client.get("/api/compare/6month")
    assert r.status_code == 200, r.text
    return r.json()


def test_pair_values_come_from_metadata_json(pair):
    meta = json.loads(time_compare_6month.METADATA_JSON.read_text(encoding="utf-8"))
    assert pair["time_gap_days"] == meta["time_gap_days"]
    assert pair["wavelength_delta_um"] == meta["wavelength_delta_um"]
    assert pair["epoch_a"]["wavelength_um"] == meta["epoch_A"]["wavelength_um"]
    assert pair["epoch_b"]["wavelength_um"] == meta["epoch_B"]["wavelength_um"]
    assert pair["epoch_a"]["observation"]["date_obs"] == meta["epoch_A"]["date"]
    assert pair["epoch_b"]["observation"]["date_obs"] == meta["epoch_B"]["date"]
    assert pair["difference_primary"] == "B-A"


def test_pair_verified_values(pair):
    assert pair["time_gap_days"] == pytest.approx(181.774125, abs=1e-5)
    assert pair["time_gap_months"] == pytest.approx(5.97, abs=0.005)
    assert pair["bunit"] == "MJy / sr"
    assert (pair["crop"]["width"], pair["crop"]["height"]) == (1057, 468)
    for side in ("epoch_a", "epoch_b"):
        assert pair[side]["observation"]["detector"] == 3
        assert pair[side]["psf_fwhm_arcsec"] == pytest.approx(5.222648214064271)


@pytest.mark.parametrize("kind", ["A", "B", "difference"])
def test_previews_share_the_display_region(kind, pair):
    r = client.get(f"/api/compare/6month/preview/{kind}")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    region = pair["display_region"]
    # native resolution, identical size for A, B and B - A
    assert Image.open(io.BytesIO(r.content)).size == (region["width"], region["height"])


def test_display_region_lies_inside_common_footprint(pair):
    region = pair["display_region"]
    mask = time_compare_6month._overlap_mask()
    inside = mask[region["y0"]:region["y1"], region["x0"]:region["x1"]]
    # no invalid band: every row and column is (almost) entirely valid;
    # only isolated interior NaN pixels may remain
    assert inside.mean(axis=0).min() > 0.95
    assert inside.mean(axis=1).min() > 0.95
    assert region["invalid_pixels"] == int((~inside).sum()) < 0.001 * inside.size
    # a substantial part of the footprint is shown
    assert region["valid_pixels"] > 0.8 * pair["overlap_pixels"]


def test_region_cut_preserves_registration():
    """A, B and B - A are cut with one slice from the same aligned grid:
    the cut difference must equal cut(B) - cut(A) pixel for pixel."""
    a, b, diff, valid = time_compare_6month._region_arrays()
    assert a.shape == b.shape == diff.shape == valid.shape
    assert np.allclose(diff[valid], (b - a)[valid], atol=1e-4)


def test_frame_center_is_not_the_target(pair):
    center = pair["frame_center"]
    obs = pair["epoch_a"]["observation"]
    assert (obs["ra_center_deg"], obs["dec_center_deg"]) == (center["ra_deg"], center["dec_deg"])
    assert (pair["target"]["ra_deg"], pair["target"]["dec_deg"]) == (155.352, -42.7)
    assert pair["target"]["in_display_region"] is (pair["target"]["offset_from_display_px"] == 0)


@pytest.mark.parametrize(
    "name", ["epoch_A.png", "epoch_B_aligned.png", "difference_B_minus_A.png"]
)
def test_reference_figures_served(name):
    r = client.get(f"/api/compare/6month/figure/{name}")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"


@pytest.mark.parametrize(
    "path",
    [
        "/api/compare/6month/preview/C",
        "/api/compare/6month/figure/metadata.json",
        "/api/compare/6month/figure/epoch_A_2025-06-19.fits",
    ],
)
def test_unknown_assets_404(path):
    assert client.get(path).status_code == 404


@pytest.mark.parametrize(
    "path",
    [
        "/api/observations",
        "/api/compare/pair?epoch_a=A&epoch_b=B",
        "/api/compare/pair?epoch_a=A&epoch_b=C",
        "/api/observations/A/preview",
        "/api/observations/B/preview-aligned",
        "/api/compare/difference-preview",
        "/api/compare/candidate-markers?epoch=B_aligned",
    ],
)
def test_31day_compare_routes_still_work(path):
    assert client.get(path).status_code == 200
