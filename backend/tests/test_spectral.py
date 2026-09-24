"""
Spectral View backend tests, run against the REAL SPHEREx mosaic files in
data/spherex/ (no mock data). Skipped if those files are not present.

    cd backend && python -m pytest tests/ -v

Without the access cache (build_spectral_cache.py) these still pass, but
channels 17-102 are read by decompressing the gzip stream and are slow.
Set SPECTRASHIFT_SLOW_TESTS=1 to also cross-check every cached channel at
one pixel against a direct read of the .fits.gz files (~1 min).
"""

import io
import math
import os
import sys
from pathlib import Path

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import spectral_data  # noqa: E402
from spectral_api import router  # noqa: E402

if any(not (spectral_data.SPHEREX_DIR / n).is_file() for n in spectral_data.SOURCE_FILENAMES):
    pytest.skip("real SPHEREx mosaic files not present in data/spherex/", allow_module_level=True)

CENTER_RA, CENTER_DEC = 155.352, -42.7   # CRVAL of both cubes

app = FastAPI()
app.include_router(router)
client = TestClient(app)


@pytest.fixture(scope="module")
def metadata():
    r = client.get("/api/spectral/metadata")
    assert r.status_code == 200, r.text
    return r.json()


def test_metadata_reports_102_channels(metadata):
    assert metadata["total_channels"] == 102
    chans = metadata["channels"]
    assert [c["channel"] for c in chans] == list(range(1, 103))
    assert metadata["image"]["width"] == 2927
    assert metadata["image"]["height"] == 2487
    for c in chans:
        for key in ("detector", "subchannel", "wavelength_um", "wavelength_min_um",
                    "wavelength_max_um", "bandwidth_um", "source_file", "source_plane"):
            assert c[key] is not None, (c["channel"], key)
        assert c["wavelength_min_um"] <= c["wavelength_um"] <= c["wavelength_max_um"]
    assert metadata["checks"]["wavelengths_strictly_increasing"]
    wr = metadata["wavelength_range_um"]
    assert 0.7 < wr["min"] < 0.8 and 4.9 < wr["max"] < 5.1


def test_metadata_source_mapping(metadata):
    src = {s["file"]: s for s in metadata["sources"]}
    assert (src["SpectraShift_Part1_16.fits.gz"]["first_channel"],
            src["SpectraShift_Part1_16.fits.gz"]["last_channel"]) == (1, 16)
    assert (src["SpectraShift_Remaining86.fits.gz"]["first_channel"],
            src["SpectraShift_Remaining86.fits.gz"]["last_channel"]) == (17, 102)
    by_ch = {c["channel"]: c for c in metadata["channels"]}
    assert by_ch[16]["source_file"] == "SpectraShift_Part1_16.fits.gz" and by_ch[16]["source_plane"] == 16
    assert by_ch[17]["source_file"] == "SpectraShift_Remaining86.fits.gz" and by_ch[17]["source_plane"] == 1
    assert by_ch[102]["source_plane"] == 86
    # wavelength continuity across the file boundary
    assert by_ch[16]["wavelength_um"] < by_ch[17]["wavelength_um"]


@pytest.mark.parametrize("channel", [1, 16, 17, 102])
def test_channel_preview(channel):
    r = client.get(f"/api/spectral/channels/{channel}/preview")
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "image/png"
    img = Image.open(io.BytesIO(r.content))
    assert img.mode == "LA" and max(img.size) == spectral_data.DEFAULT_MAX_SIZE
    lum = np.asarray(img)[..., 0]
    assert lum.std() > 0, "preview is blank"


@pytest.mark.parametrize("channel", [1, 16, 17, 102])
def test_channel_info(channel):
    r = client.get(f"/api/spectral/channels/{channel}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["channel"] == channel
    p = body["preview"]
    assert p["vmin"] < p["vmax"]
    assert 0.9 < p["finite_fraction"] <= 1.0


def test_preview_jpeg_and_linear():
    r = client.get("/api/spectral/channels/17/preview?format=jpeg&stretch=linear&max_size=256")
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
    assert max(Image.open(io.BytesIO(r.content)).size) == 256


@pytest.mark.parametrize("channel", [0, 103, -5])
def test_invalid_channel_rejected(channel):
    for url in (f"/api/spectral/channels/{channel}/preview", f"/api/spectral/channels/{channel}"):
        r = client.get(url)
        assert r.status_code == 404
        assert r.json()["detail"]["code"] == "invalid_channel"


def test_non_integer_channel_rejected():
    assert client.get("/api/spectral/channels/abc/preview").status_code == 422
    assert client.get("/api/spectral/channels/1.5/preview").status_code == 422


def test_invalid_stretch_params_rejected():
    assert client.get("/api/spectral/channels/1/preview?stretch=bogus").status_code == 422
    assert client.get("/api/spectral/channels/1/preview?plow=60").status_code == 422
    assert client.get("/api/spectral/channels/1/preview?max_size=10").status_code == 422


def test_spectrum_at_center(metadata):
    r = client.get(f"/api/spectral/spectrum?ra={CENTER_RA}&dec={CENTER_DEC}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["n_channels"] == 102 and len(body["samples"]) == 102
    assert body["pixel"]["x_index"] == 1463 and body["pixel"]["y_index"] == 1243
    assert body["in_footprint"] and body["n_valid"] > 0
    wl = [s["wavelength_um"] for s in body["samples"]]
    assert wl == sorted(wl) and len(set(wl)) == 102
    for s in body["samples"]:
        assert s["valid"] == (s["value"] is not None)
        if s["value"] is not None:
            assert math.isfinite(s["value"])


def test_spectrum_matches_raw_fits_part1():
    """Channels 1-16 at the center pixel equal an astropy read of Part1."""
    from astropy.io import fits

    body = client.get("/api/spectral/spectrum?x=1463&y=1243").json()
    path = spectral_data.SPHEREX_DIR / "SpectraShift_Part1_16.fits.gz"
    with fits.open(path) as hdul:
        ref = hdul["IMAGE"].section[:, 1243, 1463]
    for s, v in zip(body["samples"][:16], ref):
        assert (s["value"] is None and not np.isfinite(v)) or s["value"] == pytest.approx(float(v), rel=0, abs=0)


def test_spectrum_nan_pixel_returns_nulls():
    """Pick a real pixel with no coverage in channel 51 (the lowest-coverage
    channel): its sample must be null/invalid, never 0 or interpolated."""
    plane = spectral_data.service.plane(51)
    bad = np.argwhere(~np.isfinite(plane))
    assert len(bad), "expected some non-finite pixels in channel 51"
    y, x = (int(v) for v in bad[len(bad) // 2])
    body = client.get(f"/api/spectral/spectrum?x={x}&y={y}").json()
    s51 = body["samples"][50]
    assert s51["channel"] == 51 and s51["value"] is None and s51["valid"] is False
    assert body["n_valid"] == sum(s["value"] is not None for s in body["samples"])


@pytest.mark.parametrize("query", ["ra=0&dec=0", "ra=155.352&dec=-30", "ra=180&dec=89", "x=5000&y=10", "x=-1&y=0"])
def test_spectrum_outside_footprint(query):
    r = client.get(f"/api/spectral/spectrum?{query}")
    assert r.status_code == 404, r.text
    assert r.json()["detail"]["code"] == "outside_footprint"


@pytest.mark.parametrize("query", ["", "ra=155", "dec=-42", "ra=155&dec=-42&x=1&y=1", "ra=400&dec=0", "ra=10&dec=-91"])
def test_spectrum_bad_input(query):
    assert client.get(f"/api/spectral/spectrum?{query}").status_code == 422


def test_missing_files_reported(tmp_path):
    svc = spectral_data.SpectralService(spherex_dir=tmp_path, cache_root=tmp_path / "cache")
    with pytest.raises(spectral_data.SpectralDataMissing) as info:
        svc.layout
    assert set(info.value.extra["missing_files"]) == set(spectral_data.SOURCE_FILENAMES)
    assert svc.status()["available"] is False


def test_malformed_fits_reported(tmp_path):
    for name in spectral_data.SOURCE_FILENAMES:
        (tmp_path / name).write_bytes(b"this is not a gzip FITS file")
    svc = spectral_data.SpectralService(spherex_dir=tmp_path, cache_root=tmp_path / "cache")
    with pytest.raises(spectral_data.SpectralDataInvalid):
        svc.layout


def test_routes_registered_in_main_app():
    import main

    paths = set(main.app.openapi()["paths"])
    assert {"/api/spectral/metadata", "/api/spectral/status", "/api/spectral/spectrum",
            "/api/spectral/channels/{channel}", "/api/spectral/channels/{channel}/preview"} <= paths
    # Time Compare routes untouched
    assert {"/api/observations/{epoch}/preview", "/api/compare/pair",
            "/api/candidates/{candidate_id}/spectrum"} <= paths


@pytest.mark.skipif(os.environ.get("SPECTRASHIFT_SLOW_TESTS") != "1", reason="set SPECTRASHIFT_SLOW_TESTS=1")
def test_cache_matches_direct_fits_all_channels():
    svc = spectral_data.service
    if svc.cube() is None:
        pytest.skip("access cache not built")
    x, y = 1000, 900
    cached = np.asarray(svc.cube()[:, y, x])
    direct = spectral_data.read_pixel_series_from_fits(svc.layout, x, y)
    assert np.array_equal(cached, direct, equal_nan=True)


def test_fresh_service_cube_and_channels_do_not_deadlock():
    """cube()/channels() hold the service lock while reading .layout; on a
    fresh service that must not self-deadlock (regression)."""
    import threading

    result = {}

    def run():
        svc = spectral_data.SpectralService()
        svc.cube()
        result["channels"] = len(spectral_data.SpectralService().channels())

    t = threading.Thread(target=run, daemon=True)
    t.start()
    t.join(timeout=120)
    assert not t.is_alive(), "SpectralService deadlocked"
    assert result["channels"] == 102
