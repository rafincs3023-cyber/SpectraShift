"""
One-time build of the Spectral View access cache.

    python backend/build_spectral_cache.py [--skip-previews] [--force]

Makes one forward pass over the IMAGE cube of each gzip-compressed SPHEREx
mosaic file (data/spherex/*.fits.gz) and writes, under
data/spherex/cache/<fingerprint>/ (gitignored):

  image_cube.f32.npy   all 102 IMAGE planes, channel-major (102, y, x),
                       native float32, opened later with mmap_mode="r"
                       (~3 GB; a derived access cache, not a FITS copy --
                       delete it any time, the API falls back to reading
                       the .fits.gz directly)
  channel_stats.json   per-channel finite-pixel fraction and percentiles
  channels.json        SPECTRAL_CHANNELS table for all 102 channels
  previews/            default-stretch PNG preview of every channel

Only one plane (~29 MB) is held in memory at a time. The source FITS files
are only read, never modified.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from spectral_data import (  # noqa: E402
    CUBE_FILENAME,
    STATS_FILENAME,
    SpectralError,
    SpectralService,
    iter_planes_from_fits,
    _write_json_atomic,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--skip-previews", action="store_true", help="do not pre-render default previews")
    parser.add_argument("--force", action="store_true", help="rebuild the cube even if it already exists")
    args = parser.parse_args()

    svc = SpectralService()
    try:
        layout = svc.layout
    except SpectralError as exc:
        print(f"ERROR: {exc.message}", file=sys.stderr)
        return 1

    cache_dir = svc.cache_dir
    cache_dir.mkdir(parents=True, exist_ok=True)
    cube_path = cache_dir / CUBE_FILENAME
    shape = (layout.total_channels, layout.height, layout.width)
    print(f"Sources: {[s.path.name for s in layout.sources]}")
    print(f"Cube shape (channels, y, x): {shape}; cache dir: {cache_dir}")

    if cube_path.is_file() and not args.force:
        print(f"Cube cache already present: {cube_path}")
    else:
        need = int(np.prod(shape)) * 4 + 128
        free = shutil.disk_usage(cache_dir).free
        if free < need * 1.05:
            print(f"ERROR: need {need / 1e9:.2f} GB free in {cache_dir}, have {free / 1e9:.2f} GB", file=sys.stderr)
            return 1

        partial = cube_path.with_name(cube_path.name + ".partial")
        cube = np.lib.format.open_memmap(partial, mode="w+", dtype=np.float32, shape=shape)
        stats: dict[str, dict] = {}
        t0 = time.time()
        try:
            for src in layout.sources:
                for channel, plane in iter_planes_from_fits(layout, src):
                    cube[channel - 1] = plane
                    finite = np.isfinite(plane)
                    vals = plane[finite]
                    p = np.percentile(vals, [0.5, 50, 99.5]) if vals.size else [None] * 3
                    stats[str(channel)] = {
                        "finite_fraction": round(float(finite.mean()), 6),
                        "p0_5": None if p[0] is None else float(p[0]),
                        "median": None if p[1] is None else float(p[1]),
                        "p99_5": None if p[2] is None else float(p[2]),
                    }
                    if channel % 8 == 0:
                        cube.flush()
                    print(f"  channel {channel:3d}/{layout.total_channels} "
                          f"({src.path.name}, coverage {stats[str(channel)]['finite_fraction']:.4f}) "
                          f"{time.time() - t0:6.1f}s", flush=True)
            cube.flush()
            del cube
            os.replace(partial, cube_path)
        except BaseException:
            del cube
            partial.unlink(missing_ok=True)
            raise
        _write_json_atomic(cache_dir / STATS_FILENAME, stats)
        print(f"Cube cache written: {cube_path} ({cube_path.stat().st_size / 1e9:.2f} GB)")

    svc.reset_cache_handles()

    print("Reading SPECTRAL_CHANNELS tables (decompresses each file once)...", flush=True)
    t0 = time.time()
    channels = svc.channels()
    print(f"  {len(channels)} channels in {time.time() - t0:.1f}s")

    if not args.skip_previews:
        print("Rendering default previews...", flush=True)
        t0 = time.time()
        for ch in range(1, layout.total_channels + 1):
            svc.preview(ch)
        print(f"  {layout.total_channels} previews in {time.time() - t0:.1f}s")

    print(json.dumps(svc.status(), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
