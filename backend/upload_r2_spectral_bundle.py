"""
Upload the verified Spectral View bundle to the private R2 bucket.

    python backend/upload_r2_spectral_bundle.py --dry-run
    python backend/upload_r2_spectral_bundle.py
    python backend/upload_r2_spectral_bundle.py --verify-remote

Credentials come ONLY from environment variables (use an Object Read & Write
token scoped to the bucket for this one-off upload -- NOT the read-only token
the deployed backend uses):

    R2_ENDPOINT_URL        https://<account>.r2.cloudflarestorage.com
    R2_BUCKET              spectrashift-data
    R2_ACCESS_KEY_ID
    R2_SECRET_ACCESS_KEY
    R2_PREFIX              default spectral-cache/v1/

Safety:
  * uploads only tiles/*.npy, previews/*.png and manifest.json under the
    prefix; never deletes anything and never writes outside the prefix, so the
    original FITS objects in the bucket are untouched
  * refuses to run unless the local manifest records a passed validation
  * resumable: objects already present with the same size and SHA-256
    (stored as object metadata) are skipped
  * manifest.json is uploaded last, so a partial upload is never visible to
    the backend
  * never prints credentials or the endpoint URL
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from spectral_r2 import (  # noqa: E402
    DEFAULT_PREFIX,
    MANIFEST_NAME,
    R2ObjectStore,
    R2SpectralService,
    normalize_prefix,
)

DEFAULT_BUNDLE = Path(__file__).resolve().parent.parent / "data" / "spherex" / "r2_bundle"
CONTENT_TYPES = {".npy": "application/octet-stream", ".png": "image/png", ".json": "application/json"}


def plan(bundle: Path) -> list[tuple[str, Path, str]]:
    manifest = json.loads((bundle / MANIFEST_NAME).read_text())
    if not manifest.get("validation", {}).get("passed"):
        raise SystemExit("ERROR: the bundle manifest does not record a passed validation; "
                         "run build_r2_spectral_bundle.py (or --verify-only) first")
    items = []
    for name, entry in manifest["tiles"]["entries"].items():
        items.append((f"tiles/{name}.npy", bundle / "tiles" / f"{name}.npy", entry["sha256"]))
    for entry in manifest["previews"]["entries"].values():
        items.append((entry["key"], bundle / entry["key"], entry["sha256"]))
    for key, path, _ in items:
        if not path.is_file():
            raise SystemExit(f"ERROR: {key} listed in the manifest is missing locally")
    return items


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--bundle", type=Path, default=DEFAULT_BUNDLE)
    parser.add_argument("--dry-run", action="store_true", help="show what would be uploaded; no network access")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--verify-remote", action="store_true",
                        help="after uploading, read the manifest and sample tiles back through the backend code")
    args = parser.parse_args()

    items = plan(args.bundle)
    manifest_path = args.bundle / MANIFEST_NAME
    total = sum(p.stat().st_size for _, p, _ in items) + manifest_path.stat().st_size
    prefix = normalize_prefix(os.environ.get("R2_PREFIX", DEFAULT_PREFIX))
    if not prefix:
        raise SystemExit("ERROR: R2_PREFIX must not be empty (objects must stay under a dedicated prefix)")
    print(f"Bundle: {len(items)} objects + manifest, {total / 1e9:.3f} GB, target prefix '{prefix}'")
    if args.dry_run:
        print("Dry run: nothing uploaded.")
        return 0

    store = R2ObjectStore.from_env()
    client, bucket = store._client, store.bucket  # noqa: SLF001 - same module family

    def upload(key: str, path: Path, sha: str) -> str:
        full = prefix + key
        if full.lower().endswith((".fits", ".fits.gz")):
            raise RuntimeError(f"refusing to write a FITS key: {full}")
        size = path.stat().st_size
        try:
            head = client.head_object(Bucket=bucket, Key=full)
            if head.get("ContentLength") == size and head.get("Metadata", {}).get("sha256") == sha:
                return "skipped"
        except client.exceptions.ClientError:
            pass
        for attempt in range(5):
            try:
                with open(path, "rb") as f:
                    client.put_object(Bucket=bucket, Key=full, Body=f,
                                      ContentType=CONTENT_TYPES.get(path.suffix, "application/octet-stream"),
                                      Metadata={"sha256": sha})
                return "uploaded"
            except Exception:  # noqa: BLE001 - transient network errors: back off and retry
                if attempt == 4:
                    raise
                time.sleep(2 ** attempt)
        return "uploaded"

    counts = {"uploaded": 0, "skipped": 0}
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(upload, *item): item[0] for item in items}
        for i, fut in enumerate(as_completed(futures), 1):
            counts[fut.result()] += 1
            if i % 100 == 0 or i == len(items):
                print(f"  {i}/{len(items)} objects ({counts}) {time.time() - t0:.0f}s", flush=True)

    manifest_sha = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    counts[upload(MANIFEST_NAME, manifest_path, manifest_sha)] += 1
    print(f"Done: {counts}")

    if args.verify_remote:
        svc = R2SpectralService(store=store)
        meta = svc.metadata()
        mid = svc.spectrum(x=meta["image"]["width"] // 2, y=meta["image"]["height"] // 2)
        corner = svc.spectrum(x=meta["image"]["width"] - 1, y=meta["image"]["height"] - 1)
        png, _ = svc.preview_response(102)
        print(f"Remote check: {meta['total_channels']} channels, spectra with {mid['n_channels']} and "
              f"{corner['n_channels']} samples, preview 102 = {len(png)} bytes -- OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
