"""
Tests for the production (R2) Spectral View backend.

Part 1 needs no data and no credentials: a small synthetic bundle is served
from an in-memory fake object store (and a botocore Stubber for the R2
client). Part 2 runs only if the real bundle (data/spherex/r2_bundle) and the
local access cache exist, and checks it against the local FITS-backed service.

    cd backend && python -m pytest tests/test_spectral_r2.py -v
"""

import gzip
import hashlib
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from astropy.wcs import WCS
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import spectral_api  # noqa: E402
import spectral_data  # noqa: E402
from spectral_data import OutsideFootprint, SpectralDataInvalid  # noqa: E402
from spectral_r2 import (  # noqa: E402
    BUNDLE_SCHEMA,
    BUNDLE_SCHEMA_VERSION,
    LocalDirObjectStore,
    LRUBytesCache,
    ObjectNotFound,
    R2ObjectStore,
    R2SpectralService,
    RenderUnsupported,
    preview_key,
    tile_key,
)

BACKEND_DIR = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Synthetic bundle (same format as build_r2_spectral_bundle.py)
# ---------------------------------------------------------------------------

W, H, C, T = 150, 70, 5, 64          # 3 x 2 tiles, ragged right and top edges


class FakeStore:
    def __init__(self, objects):
        self.objects = dict(objects)
        self.gets = []

    def get(self, key):
        self.gets.append(key)
        if key not in self.objects:
            raise ObjectNotFound(f"not found: {key}")
        return self.objects[key]

    def describe(self):
        return {"store": "fake"}


def _npy(arr):
    buf = io.BytesIO()
    np.save(buf, arr, allow_pickle=False)
    return buf.getvalue()


def _synthetic():
    rng = np.random.default_rng(1)
    cube = rng.normal(5.0, 2.0, (C, H, W)).astype(np.float32)   # (channel, y, x)
    cube[:, :3, :3] = np.nan                                      # no-data corner
    cube[2, 40, 100] = np.nan                                     # single NaN sample
    header = {
        "NAXIS": 2, "NAXIS1": W, "NAXIS2": H,
        "CTYPE1": "RA---TAN", "CTYPE2": "DEC--TAN",
        "CRPIX1": W / 2, "CRPIX2": H / 2, "CRVAL1": 155.352, "CRVAL2": -42.7,
        "CDELT1": -6.15 / 3600, "CDELT2": 6.15 / 3600, "CUNIT1": "deg", "CUNIT2": "deg",
    }
    channels = [{
        "channel": i + 1, "source_file": "fake.fits.gz", "source_plane": i + 1,
        "detector": 1, "subchannel": i + 1, "wavelength_um": 0.75 + 0.01 * i,
        "wavelength_min_um": 0.745 + 0.01 * i, "wavelength_max_um": 0.755 + 0.01 * i,
        "bandwidth_um": 0.01, "resolving_power": 41.0, "resolving_power_std": 1.0,
    } for i in range(C)]
    objects, entries, previews = {}, {}, {}
    for ty in range((H + T - 1) // T):
        for tx in range((W + T - 1) // T):
            y0, y1, x0, x1 = ty * T, min(H, ty * T + T), tx * T, min(W, tx * T + T)
            tile = np.ascontiguousarray(cube[:, y0:y1, x0:x1].transpose(1, 2, 0)).astype("<f4")
            raw = _npy(tile)
            objects[tile_key(ty, tx)] = raw
            entries[f"y{ty:03d}_x{tx:03d}"] = {"y0": y0, "y1": y1, "x0": x0, "x1": x1,
                                                "shape": list(tile.shape), "bytes": len(raw),
                                                "sha256": hashlib.sha256(raw).hexdigest()}
    for ch in range(1, C + 1):
        img = Image.new("LA", (W, H), (ch * 40, 255))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        raw = buf.getvalue()
        objects[preview_key(ch)] = raw
        previews[str(ch)] = {"key": preview_key(ch), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
                             "info": {"stretch": "asinh", "percentile_low": 0.5, "percentile_high": 99.5,
                                      "finite_fraction": 0.99, "vmin": 1.0, "vmax": 9.0,
                                      "width": W, "height": H, "channel": ch}}
    manifest = {
        "schema": BUNDLE_SCHEMA, "schema_version": BUNDLE_SCHEMA_VERSION,
        "sources": [{"file": "fake.fits.gz", "size_bytes": 123, "sha256": "0" * 64}],
        "total_channels": C, "width": W, "height": H, "dtype": "float32", "unit": "MJy/sr",
        "wcs_header": header, "channels": channels,
        "metadata": {"total_channels": C, "channels": channels, "image": {"width": W, "height": H}},
        "tiles": {"tile_size": T, "entries": entries},
        "previews": {"default_params": {"stretch": "asinh", "percentile_low": 0.5, "percentile_high": 99.5,
                                        "max_size": 1200, "format": "png"}, "entries": previews},
        "validation": {"passed": True},
    }
    objects["manifest.json"] = json.dumps(manifest).encode()
    return cube, objects, header


@pytest.fixture()
def synth():
    cube, objects, header = _synthetic()
    store = FakeStore(objects)
    return cube, store, R2SpectralService(store=store), header


def test_spectrum_exact_values_every_tile_and_edge(synth):
    cube, _, svc, _ = synth
    points = [(0, 0), (W - 1, 0), (0, H - 1), (W - 1, H - 1), (63, 63), (64, 64), (127, 5), (128, 69), (100, 40)]
    for x, y in points:
        body = svc.spectrum(x=x, y=y)
        assert body["n_channels"] == C and body["access_mode"] == "r2_tile"
        for ch, sample in enumerate(body["samples"]):
            v = cube[ch, y, x]
            if np.isfinite(v):
                assert sample["value"] == float(v) and sample["valid"] is True
            else:
                assert sample["value"] is None and sample["valid"] is False


def test_nan_preserved_as_null(synth):
    _, _, svc, _ = synth
    corner = svc.spectrum(x=1, y=1)
    assert corner["n_valid"] == 0 and corner["has_data"] is False
    single = svc.spectrum(x=100, y=40)
    assert single["samples"][2]["value"] is None and single["n_valid"] == C - 1


def test_radec_uses_preserved_wcs(synth):
    cube, _, svc, header = synth
    wcs = WCS(header)
    for x, y in [(10, 12), (140, 60), (64, 33)]:
        ra, dec = (float(v) for v in wcs.pixel_to_world_values(x, y))
        body = svc.spectrum(ra=ra, dec=dec)
        assert (body["pixel"]["x_index"], body["pixel"]["y_index"]) == (x, y)
        assert body["samples"][0]["value"] == float(cube[0, y, x])


def test_outside_footprint(synth):
    _, _, svc, _ = synth
    with pytest.raises(OutsideFootprint):
        svc.spectrum(x=W, y=0)
    with pytest.raises(OutsideFootprint):
        svc.spectrum(x=-1, y=5)


def test_one_tile_per_spectrum_and_lru_reuse(synth):
    _, store, svc, _ = synth
    svc.manifest
    store.gets.clear()
    svc.spectrum(x=5, y=5)
    assert store.gets == [tile_key(0, 0)]
    svc.spectrum(x=6, y=7)                       # same tile: served from the cache
    assert store.gets == [tile_key(0, 0)]
    svc.spectrum(x=130, y=66)
    assert store.gets == [tile_key(0, 0), tile_key(1, 2)]
    assert svc.tiles.stats()["hits"] >= 1


def test_lru_is_bounded():
    cache = LRUBytesCache(max_bytes=100)
    for i in range(10):
        cache.put(f"k{i}", i, 30)
    stats = cache.stats()
    assert stats["bytes"] <= 100 and stats["entries"] == 3
    assert cache.get("k0") is None and cache.get("k9") == 9
    cache.put("huge", 1, 1000)                    # larger than the cache: not stored
    assert cache.get("huge") is None


@pytest.mark.parametrize("first_call", ["metadata", "spectrum", "channels", "status"])
def test_lazy_store_first_call_does_not_deadlock(synth, monkeypatch, first_call):
    """Production creates the service without a store (it is built from the
    environment on first use). Whatever the first request is -- the
    frontend calls /metadata first -- it must complete, and /status after
    it must too. Regression test for a non-reentrant-lock deadlock."""
    import threading

    import spectral_r2

    _, store, _, _ = synth
    monkeypatch.setattr(spectral_r2, "store_from_env", lambda: store)
    svc = R2SpectralService()
    calls = {
        "metadata": svc.metadata,
        "spectrum": lambda: svc.spectrum(x=1, y=1),
        "channels": svc.channels,
        "status": svc.status,
    }
    done = {}

    def run(name, fn):
        fn()
        done[name] = True

    for name in (first_call, "status"):
        t = threading.Thread(target=run, args=(name, calls[name]), daemon=True)
        t.start()
        t.join(10)
        assert done.get(name), f"{name}() hung after first call {first_call}()"
    assert svc.status()["available"] is True


def test_corrupt_tile_rejected(synth):
    _, store, svc, _ = synth
    raw = bytearray(store.objects[tile_key(0, 0)])
    raw[-1] ^= 0xFF
    store.objects[tile_key(0, 0)] = bytes(raw)
    with pytest.raises(SpectralDataInvalid):
        svc.spectrum(x=1, y=1)


def test_missing_manifest_reported():
    svc = R2SpectralService(store=FakeStore({}))
    status = svc.status()
    assert status["available"] is False and status["error"]["code"] == "spectral_object_missing"
    with pytest.raises(ObjectNotFound):
        svc.metadata()


def test_no_fits_access_in_r2_mode(synth, monkeypatch):
    _, _, svc, _ = synth

    def forbidden(*args, **kwargs):
        raise AssertionError("R2 mode must not open FITS / gzip data")

    monkeypatch.setattr(gzip, "open", forbidden)
    monkeypatch.setattr(spectral_data, "load_layout", forbidden)
    assert svc.status()["available"] is True
    svc.metadata()
    svc.spectrum(x=70, y=30)
    svc.preview_response(3)


def test_previews_default_only(synth):
    _, store, svc, _ = synth
    png, media = svc.preview_response(2)
    assert media == "image/png" and png == store.objects[preview_key(2)]
    jpg, media = svc.preview_response(2, fmt="jpeg")
    assert media == "image/jpeg" and Image.open(io.BytesIO(jpg)).mode == "L"
    with pytest.raises(RenderUnsupported):
        svc.preview_response(2, stretch="linear")
    with pytest.raises(RenderUnsupported):
        svc.channel_info(2, plow=1.0)
    info = svc.channel_info(2)
    assert info["preview"]["vmin"] == 1.0 and info["unit"] == "MJy/sr"


@pytest.fixture()
def api(synth, monkeypatch):
    _, _, svc, _ = synth
    monkeypatch.setattr(spectral_api, "service", svc)
    monkeypatch.setitem(spectral_api._STATUS, RenderUnsupported, 422)
    monkeypatch.setitem(spectral_api._STATUS, ObjectNotFound, 503)
    app = FastAPI()
    app.include_router(spectral_api.router)
    return TestClient(app)


def test_api_routes_in_r2_mode(api):
    assert api.get("/api/spectral/status").json()["access_mode"] == "r2_tiles"
    meta = api.get("/api/spectral/metadata").json()
    assert meta["total_channels"] == C and meta["access"]["mode"] == "r2_tiles"
    r = api.get("/api/spectral/channels/3/preview")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    assert "max-age" in r.headers["cache-control"]
    assert api.get("/api/spectral/channels/3").json()["channel"] == 3
    body = api.get("/api/spectral/spectrum?x=10&y=10").json()
    assert body["n_channels"] == C
    unsupported = api.get("/api/spectral/channels/3/preview?stretch=linear")
    assert unsupported.status_code == 422 and unsupported.json()["detail"]["code"] == "render_unsupported_in_r2_mode"
    assert api.get("/api/spectral/channels/99/preview").status_code == 404
    assert api.get("/api/spectral/spectrum?x=9999&y=0").status_code == 404


def test_backend_selected_by_environment():
    code = ("import spectral_api, sys; "
            "sys.stdout.write(type(spectral_api.service).__name__)")
    env = {**os.environ, "SPECTRASHIFT_SPECTRAL_BACKEND": "r2"}
    for k in ("R2_ENDPOINT_URL", "R2_BUCKET", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"):
        env.pop(k, None)
    out = subprocess.run([sys.executable, "-c", code], cwd=BACKEND_DIR, env=env, capture_output=True, text=True)
    assert out.returncode == 0 and out.stdout == "R2SpectralService"   # import needs no credentials
    env["SPECTRASHIFT_SPECTRAL_BACKEND"] = "bogus"
    bad = subprocess.run([sys.executable, "-c", code], cwd=BACKEND_DIR, env=env, capture_output=True, text=True)
    assert bad.returncode != 0 and "must be 'local' or 'r2'" in bad.stderr


def test_r2_object_store_uses_prefix_and_maps_errors():
    import boto3
    from botocore.stub import Stubber

    client = boto3.client("s3", region_name="auto", endpoint_url="https://example.invalid",
                          aws_access_key_id="test", aws_secret_access_key="test")
    store = R2ObjectStore(client, "bucket", "spectral-cache/v1/")
    with Stubber(client) as stub:
        stub.add_response("get_object", {"Body": io.BytesIO(b"abc")},
                          {"Bucket": "bucket", "Key": "spectral-cache/v1/manifest.json"})
        stub.add_client_error("get_object", service_error_code="NoSuchKey", http_status_code=404)
        assert store.get("manifest.json") == b"abc"
        with pytest.raises(ObjectNotFound):
            store.get("tiles/y000_x000.npy")


def test_r2_from_env_requires_all_variables(monkeypatch):
    for k in ("R2_ENDPOINT_URL", "R2_BUCKET", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "super-secret-value")
    with pytest.raises(spectral_data.SpectralDataMissing) as err:
        R2ObjectStore.from_env()
    assert "super-secret-value" not in str(err.value.as_dict())


# ---------------------------------------------------------------------------
# Part 2: the real bundle against the local FITS-backed service
# ---------------------------------------------------------------------------

BUNDLE = spectral_data.SPHEREX_DIR / "r2_bundle"


def _real():
    if not (BUNDLE / "manifest.json").is_file():
        pytest.skip("real bundle not built (backend/build_r2_spectral_bundle.py)")
    local = spectral_data.SpectralService()
    try:
        cube = local.cube()
    except spectral_data.SpectralError:
        pytest.skip("local SPHEREx files not present")
    if cube is None:
        pytest.skip("local access cache not built")
    return local, cube, R2SpectralService(store=LocalDirObjectStore(BUNDLE))


def test_real_bundle_manifest_and_coverage():
    local, cube, r2 = _real()
    m = r2.manifest
    assert m["validation"]["passed"] is True
    assert m["total_channels"] == 102 and len(m["channels"]) == 102 and m["dtype"] == "float32"
    assert (m["width"], m["height"]) == (local.layout.width, local.layout.height)
    coverage = np.zeros((m["height"], m["width"]), dtype=np.uint8)
    for e in m["tiles"]["entries"].values():
        coverage[e["y0"]:e["y1"], e["x0"]:e["x1"]] += 1
        assert e["shape"] == [e["y1"] - e["y0"], e["x1"] - e["x0"], 102]
    assert (coverage == 1).all()
    assert [c["channel"] for c in m["channels"]] == list(range(1, 103))


def test_real_bundle_bit_identical_spectra():
    local, cube, r2 = _real()
    lay = local.layout
    rng = np.random.default_rng(7)
    pts = [(0, 0), (lay.width - 1, 0), (0, lay.height - 1), (lay.width - 1, lay.height - 1)]
    pts += [(int(x), int(y)) for x, y in zip(rng.integers(0, lay.width, 40), rng.integers(0, lay.height, 40))]
    for x, y in pts:
        vals, _ = r2.pixel_series(x, y)
        ref = np.asarray(cube[:, y, x], dtype=np.float32)
        assert np.array_equal(vals.view(np.uint32), ref.view(np.uint32)), (x, y)
        for ch in (1, 16, 17, 102):
            assert vals[ch - 1].tobytes() == ref[ch - 1].tobytes()
        a, b = local.spectrum(x=x, y=y), r2.spectrum(x=x, y=y)
        a.pop("access_mode"), b.pop("access_mode")
        assert a == b


def test_real_bundle_metadata_matches_frontend_contract():
    local, _, r2 = _real()
    a, b = local.metadata(), r2.metadata()
    a.pop("access"), b.pop("access")
    assert a == b
    assert b["wavelength_range_um"]["min"] == pytest.approx(0.743, abs=1e-3)
    assert b["wavelength_range_um"]["max"] == pytest.approx(5.009, abs=1e-3)
    assert sorted({c["detector"] for c in b["channels"]}) == [1, 2, 3, 4, 5, 6]
