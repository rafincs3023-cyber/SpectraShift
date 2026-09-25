"""
Build (and verify) the lossless Spectral View bundle for production (R2).

    python backend/build_r2_spectral_bundle.py              # build + verify
    python backend/build_r2_spectral_bundle.py --verify-only
    python backend/build_r2_spectral_bundle.py --fits-samples 5

Input: the verified local Spectral View data -- the two original mosaic
files in data/spherex/ and the memmap access cache written by
build_spectral_cache.py (run that first).

Output (gitignored), data/spherex/r2_bundle/:

    manifest.json        everything the API needs without opening FITS:
                         schema, source files (size + SHA-256), 102-channel
                         table, exact width/height, dtype, WCS header cards,
                         unit, channel statistics, wavelength range,
                         source-channel mapping, tile index (shape, bytes,
                         SHA-256 per tile), preview index, validation results
    tiles/yNNN_xNNN.npy  numpy .npy v1, little-endian float32 (<f4), C order,
                         shape [tile_h, tile_w, 102] = [y, x, channel] for
                         FITS pixels y in [NNN*T, ...), x in [NNN*T, ...),
                         T = tile size (64). Edge tiles are smaller. Every
                         mosaic pixel appears in exactly one tile; values are
                         copied bit-for-bit (NaN kept), nothing is resampled,
                         cropped or converted.
    previews/chNNN.png   the default Spectral View preview of each channel
                         (display product only, rendered by the same
                         spectral_data.render_preview rules)

Verification (also run after every build) compares every value of every tile
bit-for-bit with the access cache, checks sample pixels bit-for-bit directly
against the original FITS stream, checks tile coverage, dtype, channel order,
WCS and previews, and records the results in manifest["validation"]. The
build fails if any check fails.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))

from spectral_data import (  # noqa: E402
    DEFAULT_MAX_SIZE,
    DEFAULT_PHIGH,
    DEFAULT_PLOW,
    DEFAULT_STRETCH,
    SPHEREX_DIR,
    SpectralError,
    SpectralService,
    read_pixel_series_from_fits,
    render_preview,
    _write_json_atomic,
)
from spectral_r2 import (  # noqa: E402
    BUNDLE_SCHEMA,
    BUNDLE_SCHEMA_VERSION,
    MANIFEST_NAME,
    LocalDirObjectStore,
    R2SpectralService,
    load_tile_bytes,
    preview_key,
    tile_key,
    wcs_from_manifest,
)

DEFAULT_OUT = SPHEREX_DIR / "r2_bundle"
DEFAULT_TILE = 64
SPOT_CHANNELS = (1, 16, 17, 102)


def sha256_file(path: Path, chunk: int = 8 * 1024 * 1024) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while block := f.read(chunk):
            h.update(block)
    return h.hexdigest()


def npy_bytes(arr: np.ndarray) -> bytes:
    buf = io.BytesIO()
    np.save(buf, arr, allow_pickle=False)
    return buf.getvalue()


def same_bits(a: np.ndarray, b: np.ndarray) -> bool:
    """Exact equality of float32 arrays, NaN payloads included."""
    a = np.ascontiguousarray(a, dtype="<f4")
    b = np.ascontiguousarray(b, dtype="<f4")
    return a.shape == b.shape and np.array_equal(a.view("<u4"), b.view("<u4"))


def tile_grid(width: int, height: int, size: int) -> tuple[int, int]:
    return (width + size - 1) // size, (height + size - 1) // size


def load_service() -> tuple[SpectralService, np.ndarray]:
    svc = SpectralService()
    try:
        svc.layout
    except SpectralError as exc:
        raise SystemExit(f"ERROR: {exc.message}")
    cube = svc.cube()
    if cube is None:
        raise SystemExit("ERROR: the local access cache is not built; run `python backend/build_spectral_cache.py` first")
    return svc, cube


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

def build(out: Path, tile_size: int) -> dict[str, Any]:
    svc, cube = load_service()
    lay = svc.layout
    channels = svc.channels()
    if len(channels) != lay.total_channels:
        raise SystemExit(f"ERROR: channel table has {len(channels)} rows, cube has {lay.total_channels} channels")

    if out.exists():
        shutil.rmtree(out)
    (out / "tiles").mkdir(parents=True)
    (out / "previews").mkdir(parents=True)

    print("Hashing source files (source of truth, never modified)...", flush=True)
    sources = []
    for s in lay.sources:
        sources.append({
            "file": s.path.name,
            "size_bytes": s.path.stat().st_size,
            "sha256": sha256_file(s.path),
            "first_channel": s.first_channel,
            "last_channel": s.last_channel,
            "n_channels": s.n_channels,
            "header_wlmin_um": s.wlmin,
            "header_wlmax_um": s.wlmax,
        })

    print(f"Writing {tile_size}x{tile_size} tiles of all {lay.total_channels} channels...", flush=True)
    nx, ny = tile_grid(lay.width, lay.height, tile_size)
    entries: dict[str, Any] = {}
    t0 = time.time()
    for ty in range(ny):
        y0, y1 = ty * tile_size, min((ty + 1) * tile_size, lay.height)
        band = np.asarray(cube[:, y0:y1, :])            # (channels, h, width), float32
        for tx in range(nx):
            x0, x1 = tx * tile_size, min((tx + 1) * tile_size, lay.width)
            tile = np.ascontiguousarray(band[:, :, x0:x1].transpose(1, 2, 0)).astype("<f4", copy=False)
            raw = npy_bytes(tile)
            (out / tile_key(ty, tx)).write_bytes(raw)
            entries[f"y{ty:03d}_x{tx:03d}"] = {
                "y0": y0, "y1": y1, "x0": x0, "x1": x1,
                "shape": list(tile.shape),
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        print(f"  tile row {ty + 1}/{ny}  ({time.time() - t0:.0f}s)", flush=True)

    print("Collecting default previews (display products)...", flush=True)
    preview_entries: dict[str, Any] = {}
    for ch in range(1, lay.total_channels + 1):
        path, info = svc.preview(ch)            # default stretch; renders if not cached
        raw = path.read_bytes()
        (out / preview_key(ch)).write_bytes(raw)
        preview_entries[str(ch)] = {
            "key": preview_key(ch),
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "info": info,
        }

    metadata = svc.metadata()
    metadata.pop("access", None)
    manifest = {
        "schema": BUNDLE_SCHEMA,
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "builder": "backend/build_r2_spectral_bundle.py",
        "description": (
            "Lossless re-organisation of the SPHEREx 102-channel mosaic IMAGE cubes into "
            "spatial tiles. The original FITS files remain the source of truth."
        ),
        "sources": sources,
        "total_channels": lay.total_channels,
        "width": lay.width,
        "height": lay.height,
        "dtype": "float32",
        "byte_order": "little",
        "unit": lay.unit,
        "wcs_header": {k: lay.wcs_header[k] for k in lay.wcs_header},
        "pixel_convention": metadata["image"]["pixel_convention"],
        "channels": channels,
        "channel_stats": svc.channel_stats(),
        "wavelength_range_um": metadata["wavelength_range_um"],
        "source_channel_mapping": [
            {"channel": c["channel"], "source_file": c["source_file"], "source_plane": c["source_plane"]}
            for c in channels
        ],
        "metadata": metadata,
        "tiles": {
            "tile_size": tile_size,
            "nx": nx,
            "ny": ny,
            "key_pattern": "tiles/y{ty:03d}_x{tx:03d}.npy",
            "format": "numpy .npy (allow_pickle=False), little-endian float32, C order",
            "axes": "[y, x, channel]; y/x are FITS 0-based pixel indices minus the tile origin (y0, x0)",
            "entries": entries,
        },
        "previews": {
            "default_params": {
                "stretch": DEFAULT_STRETCH, "percentile_low": DEFAULT_PLOW,
                "percentile_high": DEFAULT_PHIGH, "max_size": DEFAULT_MAX_SIZE, "format": "png",
            },
            "note": "display products only (resized, 8-bit); science values come from tiles",
            "entries": preview_entries,
        },
        "validation": {"passed": False, "note": "pending"},
    }
    _write_json_atomic(out / MANIFEST_NAME, manifest)
    return manifest


# ---------------------------------------------------------------------------
# Verify
# ---------------------------------------------------------------------------

def verify(out: Path, fits_samples: int, random_samples: int = 400, seed: int = 20260925) -> dict[str, Any]:
    svc, cube = load_service()
    lay = svc.layout
    manifest = json.loads((out / MANIFEST_NAME).read_text())
    results: dict[str, Any] = {}
    failures: list[str] = []

    def check(name: str, ok: bool, detail: Any = None) -> None:
        results[name] = {"ok": bool(ok), **({"detail": detail} if detail is not None else {})}
        if not ok:
            failures.append(name)
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f": {detail}" if detail is not None else ""), flush=True)

    print("Verifying bundle...", flush=True)
    check("schema", manifest.get("schema") == BUNDLE_SCHEMA and manifest.get("schema_version") == BUNDLE_SCHEMA_VERSION)
    check("channels_102", manifest["total_channels"] == lay.total_channels == 102 and len(manifest["channels"]) == 102,
          manifest["total_channels"])
    check("dimensions", (manifest["width"], manifest["height"]) == (lay.width, lay.height),
          f"{manifest['width']}x{manifest['height']}")
    check("dtype_float32", manifest["dtype"] == "float32" and cube.dtype == np.float32)
    check("channel_table_unchanged", manifest["channels"] == svc.channels())
    wl = [c["wavelength_um"] for c in manifest["channels"]]
    check("channel_order_and_wavelengths", [c["channel"] for c in manifest["channels"]] == list(range(1, 103))
          and all(a < b for a, b in zip(wl, wl[1:])), f"{wl[0]}..{wl[-1]} um")
    check("sources_match", [(s["file"], s["size_bytes"]) for s in manifest["sources"]]
          == [(s.path.name, s.path.stat().st_size) for s in lay.sources])

    wcs2, hdr2 = wcs_from_manifest(manifest["wcs_header"])
    same_cards = all(hdr2[k] == lay.wcs_header[k] for k in lay.wcs_header) and len(hdr2) == len(lay.wcs_header)
    rng = np.random.default_rng(seed)
    px = rng.uniform(-0.5, lay.width - 0.5, 500)
    py = rng.uniform(-0.5, lay.height - 0.5, 500)
    w1 = np.array(lay.wcs.pixel_to_world_values(px, py))
    w2 = np.array(wcs2.pixel_to_world_values(px, py))
    p1 = np.array(lay.wcs.world_to_pixel_values(*w1))
    p2 = np.array(wcs2.world_to_pixel_values(*w1))
    check("wcs_preserved", same_cards and np.array_equal(w1, w2) and np.array_equal(p1, p2),
          f"{len(hdr2)} header cards; 500 random transforms identical")

    # tiles: coverage, checksums, dtype/shape, bit-exact against the cache
    size = manifest["tiles"]["tile_size"]
    nx, ny = tile_grid(lay.width, lay.height, size)
    entries = manifest["tiles"]["entries"]
    coverage = np.zeros((lay.height, lay.width), dtype=np.uint8)
    bad_checksum, bad_values, bad_shape = [], [], []
    n_values = 0
    t0 = time.time()
    for ty in range(ny):
        y0, y1 = ty * size, min((ty + 1) * size, lay.height)
        band = np.asarray(cube[:, y0:y1, :])
        for tx in range(nx):
            x0, x1 = tx * size, min((tx + 1) * size, lay.width)
            name = f"y{ty:03d}_x{tx:03d}"
            entry = entries.get(name)
            if entry is None:
                bad_shape.append(name)
                continue
            raw = (out / tile_key(ty, tx)).read_bytes()
            if len(raw) != entry["bytes"] or hashlib.sha256(raw).hexdigest() != entry["sha256"]:
                bad_checksum.append(name)
            try:
                tile = load_tile_bytes(raw, (y1 - y0, x1 - x0, lay.total_channels), lay.total_channels)
            except SpectralError:
                bad_shape.append(name)
                continue
            if (entry["y0"], entry["y1"], entry["x0"], entry["x1"]) != (y0, y1, x0, x1):
                bad_shape.append(name)
            coverage[y0:y1, x0:x1] += 1
            if not same_bits(tile, band[:, :, x0:x1].transpose(1, 2, 0)):
                bad_values.append(name)
            n_values += tile.size
    check("tile_count", len(entries) == nx * ny, f"{len(entries)} tiles ({nx} x {ny})")
    check("every_pixel_exactly_once", bool((coverage == 1).all()),
          f"{int((coverage == 1).sum())}/{coverage.size} pixels")
    check("tile_checksums", not bad_checksum, bad_checksum[:5] or None)
    check("tile_dtype_and_shape", not bad_shape, bad_shape[:5] or None)
    check("all_values_bit_identical_to_cache", not bad_values and n_values == cube.size,
          f"{n_values} float32 values compared ({time.time() - t0:.0f}s)")
    nan_cube = int(np.isnan(cube).sum())
    check("nan_count_preserved", not bad_values, f"{nan_cube} NaN values in cube and tiles")

    # spectra through the production code path vs the local service
    r2 = R2SpectralService(store=LocalDirObjectStore(out))
    tw, th = lay.width - (nx - 1) * size, lay.height - (ny - 1) * size
    points = [(0, 0), (lay.width - 1, 0), (0, lay.height - 1), (lay.width - 1, lay.height - 1),
              (size - 1, size - 1), (size, size), ((nx - 1) * size, (ny - 1) * size),
              (lay.width - 1, (ny - 1) * size + th // 2), ((nx - 1) * size + tw // 2, lay.height - 1)]
    points += [(int(x), int(y)) for x, y in zip(rng.integers(0, lay.width, random_samples),
                                                rng.integers(0, lay.height, random_samples))]
    mismatched = []
    n_null = 0
    for x, y in points:
        a = svc.spectrum(x=x, y=y)
        b = r2.spectrum(x=x, y=y)
        va, vb = [s["value"] for s in a["samples"]], [s["value"] for s in b["samples"]]
        n_null += sum(v is None for v in vb)
        strip = lambda d: {k: v for k, v in d.items() if k != "access_mode"}  # noqa: E731
        if va != vb or strip(a) != strip(b) or len(vb) != 102:
            mismatched.append((x, y))
    check("spectra_match_local_service", not mismatched,
          f"{len(points)} pixels incl. corners and edge tiles; {n_null} null (NaN) samples; mismatches {mismatched[:3]}")

    # RA/Dec path through the reconstructed WCS
    sky_bad = []
    for x, y in points[:60]:
        ra, dec = (float(v) for v in lay.wcs.pixel_to_world_values(x, y))
        a, b = svc.spectrum(ra=ra, dec=dec), r2.spectrum(ra=ra, dec=dec)
        if a["pixel"] != b["pixel"] or [s["value"] for s in a["samples"]] != [s["value"] for s in b["samples"]]:
            sky_bad.append((x, y))
    check("radec_lookup_matches_local_service", not sky_bad, f"60 sky positions; mismatches {sky_bad[:3]}")

    # channels 1, 16, 17, 102 at every corner, bit-exact against the cache
    corner_bad = []
    for x, y in points[:4]:
        vals, _ = r2.pixel_series(x, y)
        for ch in SPOT_CHANNELS:
            if not same_bits(vals[ch - 1:ch], np.asarray(cube[ch - 1, y, x]).reshape(1)):
                corner_bad.append((ch, x, y))
    check("spot_channels_1_16_17_102", not corner_bad, corner_bad[:3] or "corners bit-identical")

    # independent path: straight from the original FITS stream (no cache)
    fits_bad = []
    fits_points = [(lay.width // 2, lay.height // 2)] + points[4:4 + max(0, fits_samples - 1)]
    t0 = time.time()
    for x, y in fits_points[:fits_samples]:
        raw_series = read_pixel_series_from_fits(lay, x, y)
        vals, _ = r2.pixel_series(x, y)
        if not same_bits(raw_series, vals):
            fits_bad.append((x, y))
    check("bit_identical_to_original_fits", not fits_bad,
          f"{min(fits_samples, len(fits_points))} pixels x 102 channels read directly from the .fits.gz "
          f"({time.time() - t0:.0f}s); mismatches {fits_bad}")

    # previews: all present, checksums, and re-rendered from the cache for spot channels
    prev = manifest["previews"]["entries"]
    prev_bad = [ch for ch in range(1, 103)
                if str(ch) not in prev
                or hashlib.sha256((out / preview_key(ch)).read_bytes()).hexdigest() != prev[str(ch)]["sha256"]]
    rerender_bad = []
    for ch in SPOT_CHANNELS:
        img, _ = render_preview(np.asarray(cube[ch - 1], dtype=np.float32))
        stored = Image.open(out / preview_key(ch))
        if stored.mode != img.mode or not np.array_equal(np.asarray(stored), np.asarray(img)):
            rerender_bad.append(ch)
    check("previews_present_and_reproducible", not prev_bad and not rerender_bad,
          f"102 previews; channels {list(SPOT_CHANNELS)} re-rendered identically" if not (prev_bad or rerender_bad)
          else {"missing_or_bad": prev_bad, "not_reproducible": rerender_bad})

    meta = r2.metadata()
    local_meta = svc.metadata()
    local_meta.pop("access", None)
    meta_cmp = {k: v for k, v in meta.items() if k != "access"}
    check("frontend_metadata_identical", meta_cmp == local_meta and meta["total_channels"] == 102)

    passed = not failures
    manifest["validation"] = {
        "passed": passed,
        "verified_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "failures": failures,
        "checks": results,
    }
    _write_json_atomic(out / MANIFEST_NAME, manifest)
    return manifest["validation"]


def bundle_sizes(out: Path) -> dict[str, int]:
    def total(pattern: str) -> int:
        return sum(p.stat().st_size for p in out.glob(pattern))
    return {"tiles": total("tiles/*.npy"), "previews": total("previews/*.png"),
            "manifest": (out / MANIFEST_NAME).stat().st_size}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help=f"output directory (default {DEFAULT_OUT})")
    parser.add_argument("--tile-size", type=int, default=DEFAULT_TILE)
    parser.add_argument("--verify-only", action="store_true", help="verify an existing bundle")
    parser.add_argument("--fits-samples", type=int, default=3,
                        help="pixels checked directly against the .fits.gz (slow: ~decompression per pixel)")
    args = parser.parse_args()

    if not args.verify_only:
        build(args.out, args.tile_size)
    validation = verify(args.out, args.fits_samples)
    sizes = bundle_sizes(args.out)
    print(json.dumps({"passed": validation["passed"], "sizes_bytes": sizes,
                      "total_bytes": sum(sizes.values())}, indent=1))
    return 0 if validation["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
