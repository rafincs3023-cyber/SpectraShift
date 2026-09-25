"""
Spectral View backend for production: the lossless R2 bundle.

Selected with SPECTRASHIFT_SPECTRAL_BACKEND=r2 (see spectral_api.py). The
default (``local``) keeps using spectral_data.SpectralService on the original
FITS files / local memmap cache.

The bundle (built by build_r2_spectral_bundle.py) holds the complete
102-channel IMAGE cube re-organised -- not reduced -- into spatial tiles:

    <prefix>manifest.json          metadata, WCS, channel table, tile index
    <prefix>tiles/yNNN_xNNN.npy    float32 [tile_h, tile_w, 102], every pixel
                                   of the mosaic exactly once
    <prefix>previews/chNNN.png     default display previews (display only)

Nothing here opens or downloads the source FITS files. Startup reads only the
manifest; a spectrum request fetches the ONE tile containing the pixel
(verified against the manifest's SHA-256) and keeps it in a small bounded LRU
cache. Values are returned exactly as stored (float32 -> float), non-finite
values as null.

Objects are read through an ObjectStore:
  * R2ObjectStore        private Cloudflare R2 bucket via boto3 (S3 API);
                         credentials come only from environment variables
  * LocalDirObjectStore  a bundle directory on disk (local testing of this
                         code path, no credentials)
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Any, Optional, Protocol

import numpy as np
from astropy.io import fits
from astropy.wcs import WCS
from PIL import Image

from spectral_data import (
    DEFAULT_MAX_SIZE,
    DEFAULT_PHIGH,
    DEFAULT_PLOW,
    DEFAULT_STRETCH,
    ChannelOutOfRange,
    SpectralDataInvalid,
    SpectralDataMissing,
    SpectralError,
    spectrum_response,
)

BUNDLE_SCHEMA = "spectrashift.spectral_bundle"
BUNDLE_SCHEMA_VERSION = 1
MANIFEST_NAME = "manifest.json"
DEFAULT_PREFIX = "spectral-cache/v1/"
DEFAULT_TILE_CACHE_MB = 48
DEFAULT_PREVIEW_CACHE_MB = 48


class RenderUnsupported(SpectralError):
    """Non-default preview rendering needs the full-resolution plane, which
    the production bundle deliberately does not download."""

    code = "render_unsupported_in_r2_mode"


class ObjectNotFound(SpectralError):
    code = "spectral_object_missing"


# ---------------------------------------------------------------------------
# Object stores
# ---------------------------------------------------------------------------

class ObjectStore(Protocol):
    def get(self, key: str) -> bytes: ...

    def describe(self) -> dict[str, Any]: ...


class LocalDirObjectStore:
    """Reads bundle objects from a directory laid out like the R2 prefix."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def get(self, key: str) -> bytes:
        path = (self.root / key).resolve()
        if self.root.resolve() not in path.parents and path != self.root.resolve():
            raise ObjectNotFound(f"object key escapes the bundle directory: {key}")
        if not path.is_file():
            raise ObjectNotFound(f"bundle object not found: {key}")
        return path.read_bytes()

    def describe(self) -> dict[str, Any]:
        return {"store": "local_directory", "root": str(self.root)}


class R2ObjectStore:
    """Private Cloudflare R2 bucket through the S3 API. Needs only read
    access (GetObject). Credentials are never logged or returned."""

    def __init__(self, client: Any, bucket: str, prefix: str) -> None:
        self._client = client
        self.bucket = bucket
        self.prefix = prefix

    @classmethod
    def from_env(cls) -> "R2ObjectStore":
        missing = [k for k in ("R2_ENDPOINT_URL", "R2_BUCKET", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY")
                   if not os.environ.get(k)]
        if missing:
            raise SpectralDataMissing(
                "R2 spectral backend is not configured; missing environment variable(s): "
                + ", ".join(missing),
                missing_env=missing,
            )
        import boto3  # imported lazily: only the R2 backend needs it
        from botocore.config import Config

        client = boto3.client(
            "s3",
            endpoint_url=os.environ["R2_ENDPOINT_URL"],
            aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
            region_name="auto",
            config=Config(
                signature_version="s3v4",
                retries={"max_attempts": 4, "mode": "standard"},
                connect_timeout=10,
                read_timeout=60,
            ),
        )
        return cls(client, os.environ["R2_BUCKET"], normalize_prefix(os.environ.get("R2_PREFIX", DEFAULT_PREFIX)))

    def get(self, key: str) -> bytes:
        from botocore.exceptions import ClientError

        full_key = f"{self.prefix}{key}"
        try:
            resp = self._client.get_object(Bucket=self.bucket, Key=full_key)
            return resp["Body"].read()
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in ("NoSuchKey", "404", "NotFound"):
                raise ObjectNotFound(f"R2 object not found: {full_key}") from exc
            # message only carries the S3 error code, never credentials
            raise SpectralDataMissing(f"R2 request failed for {full_key} ({code or 'error'})") from exc

    def describe(self) -> dict[str, Any]:
        return {"store": "cloudflare_r2", "bucket": self.bucket, "prefix": self.prefix}


def normalize_prefix(prefix: str) -> str:
    prefix = prefix.strip().lstrip("/")
    return prefix if not prefix or prefix.endswith("/") else prefix + "/"


def store_from_env() -> ObjectStore:
    """SPECTRASHIFT_R2_LOCAL_BUNDLE_DIR (a built bundle on disk) takes
    precedence for local testing; otherwise the private R2 bucket."""
    local = os.environ.get("SPECTRASHIFT_R2_LOCAL_BUNDLE_DIR")
    if local:
        return LocalDirObjectStore(Path(local))
    return R2ObjectStore.from_env()


# ---------------------------------------------------------------------------
# Bounded LRU byte cache
# ---------------------------------------------------------------------------

class LRUBytesCache:
    """Thread-safe LRU keyed by object key, bounded by total payload bytes."""

    def __init__(self, max_bytes: int) -> None:
        self.max_bytes = max_bytes
        self._items: "OrderedDict[str, tuple[Any, int]]" = OrderedDict()
        self._bytes = 0
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Any:
        with self._lock:
            item = self._items.get(key)
            if item is None:
                self.misses += 1
                return None
            self._items.move_to_end(key)
            self.hits += 1
            return item[0]

    def put(self, key: str, value: Any, nbytes: int) -> None:
        if nbytes > self.max_bytes:
            return
        with self._lock:
            old = self._items.pop(key, None)
            if old is not None:
                self._bytes -= old[1]
            self._items[key] = (value, nbytes)
            self._bytes += nbytes
            while self._bytes > self.max_bytes and self._items:
                _, (_, n) = self._items.popitem(last=False)
                self._bytes -= n

    def stats(self) -> dict[str, Any]:
        with self._lock:
            return {"entries": len(self._items), "bytes": self._bytes, "max_bytes": self.max_bytes,
                    "hits": self.hits, "misses": self.misses}


# ---------------------------------------------------------------------------
# Manifest-backed layout
# ---------------------------------------------------------------------------

def wcs_from_manifest(cards: dict[str, Any]) -> tuple[WCS, fits.Header]:
    header = fits.Header()
    for key, value in cards.items():
        header[key] = value
    return WCS(header), header


class ManifestLayout:
    """The subset of spectral_data.Layout the API needs, from the manifest."""

    def __init__(self, manifest: dict[str, Any]) -> None:
        self.width = int(manifest["width"])
        self.height = int(manifest["height"])
        self.total_channels = int(manifest["total_channels"])
        self.unit = manifest.get("unit")
        self.wcs, self.wcs_header = wcs_from_manifest(manifest["wcs_header"])

    def source_for(self, channel: int) -> None:
        if not isinstance(channel, (int, np.integer)) or not (1 <= channel <= self.total_channels):
            raise ChannelOutOfRange(
                f"channel must be an integer from 1 to {self.total_channels}; got {channel!r}",
                valid_range=[1, self.total_channels],
            )


def tile_key(ty: int, tx: int) -> str:
    return f"tiles/y{ty:03d}_x{tx:03d}.npy"


def preview_key(channel: int) -> str:
    return f"previews/ch{channel:03d}.png"


def load_tile_bytes(raw: bytes, expected_shape: tuple[int, ...], n_channels: int) -> np.ndarray:
    """Decode a bundle tile (.npy, no pickle) and check shape / dtype."""
    arr = np.load(io.BytesIO(raw), allow_pickle=False)
    if arr.dtype != np.dtype("<f4") or arr.ndim != 3 or tuple(arr.shape) != tuple(expected_shape) \
            or arr.shape[2] != n_channels:
        raise SpectralDataInvalid(
            f"tile has dtype {arr.dtype} shape {arr.shape}; expected <f4 {tuple(expected_shape)}"
        )
    return arr


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class R2SpectralService:
    """Same public interface as spectral_data.SpectralService (status,
    metadata, channel_info, preview_response, spectrum), served from the
    lossless bundle."""

    def __init__(
        self,
        store: Optional[ObjectStore] = None,
        tile_cache_bytes: Optional[int] = None,
        preview_cache_bytes: Optional[int] = None,
    ) -> None:
        self._store = store
        # reentrant: lazy properties (manifest -> store) may nest
        self._lock = threading.RLock()
        self._manifest: Optional[dict[str, Any]] = None
        self._layout: Optional[ManifestLayout] = None
        mb = 1024 * 1024
        self.tiles = LRUBytesCache(tile_cache_bytes if tile_cache_bytes is not None else
                                   int(float(os.environ.get("SPECTRASHIFT_R2_TILE_CACHE_MB", DEFAULT_TILE_CACHE_MB)) * mb))
        self.previews = LRUBytesCache(preview_cache_bytes if preview_cache_bytes is not None else
                                      int(float(os.environ.get("SPECTRASHIFT_R2_PREVIEW_CACHE_MB",
                                                               DEFAULT_PREVIEW_CACHE_MB)) * mb))

    # -- lazy state -----------------------------------------------------------

    @property
    def store(self) -> ObjectStore:
        if self._store is None:
            with self._lock:
                if self._store is None:
                    self._store = store_from_env()
        return self._store

    @property
    def manifest(self) -> dict[str, Any]:
        if self._manifest is None:
            # resolve the store BEFORE taking the lock: the store property
            # takes the same lock, and doing it inside deadlocked a fresh
            # service whose first call was metadata()/spectrum()/preview
            store = self.store
            with self._lock:
                if self._manifest is None:
                    raw = store.get(MANIFEST_NAME)
                    try:
                        manifest = json.loads(raw)
                    except ValueError as exc:
                        raise SpectralDataInvalid(f"manifest.json is not valid JSON ({exc})") from exc
                    if manifest.get("schema") != BUNDLE_SCHEMA or manifest.get("schema_version") != BUNDLE_SCHEMA_VERSION:
                        raise SpectralDataInvalid(
                            f"unsupported bundle schema {manifest.get('schema')!r} v{manifest.get('schema_version')!r}"
                        )
                    if manifest.get("dtype") != "float32":
                        raise SpectralDataInvalid(f"bundle dtype {manifest.get('dtype')!r} is not float32")
                    self._layout = ManifestLayout(manifest)
                    self._manifest = manifest
        return self._manifest

    @property
    def layout(self) -> ManifestLayout:
        self.manifest  # noqa: B018 - loads layout too
        return self._layout  # type: ignore[return-value]

    def channels(self) -> list[dict[str, Any]]:
        return self.manifest["channels"]

    # -- data access ----------------------------------------------------------

    def _tile_entry(self, ty: int, tx: int) -> dict[str, Any]:
        entry = self.manifest["tiles"]["entries"].get(f"y{ty:03d}_x{tx:03d}")
        if entry is None:
            raise SpectralDataInvalid(f"tile y{ty:03d}_x{tx:03d} is missing from the manifest")
        return entry

    def tile(self, ty: int, tx: int) -> np.ndarray:
        key = tile_key(ty, tx)
        cached = self.tiles.get(key)
        if cached is not None:
            return cached
        entry = self._tile_entry(ty, tx)
        raw = self.store.get(key)
        if len(raw) != entry["bytes"] or hashlib.sha256(raw).hexdigest() != entry["sha256"]:
            raise SpectralDataInvalid(f"{key} does not match the manifest checksum (corrupt or stale object)")
        arr = load_tile_bytes(raw, tuple(entry["shape"]), self.layout.total_channels)
        arr.setflags(write=False)
        self.tiles.put(key, arr, arr.nbytes)
        return arr

    def pixel_series(self, x: int, y: int) -> tuple[np.ndarray, str]:
        size = int(self.manifest["tiles"]["tile_size"])
        ty, tx = y // size, x // size
        tile = self.tile(ty, tx)
        return np.asarray(tile[y - ty * size, x - tx * size, :], dtype=np.float32), "r2_tile"

    # -- public API -----------------------------------------------------------

    def status(self) -> dict[str, Any]:
        out: dict[str, Any] = {"backend": "r2"}
        try:
            store_info = self.store.describe()
            manifest = self.manifest
        except SpectralError as exc:
            out.update(available=False, error=exc.as_dict())
            return out
        out.update(
            available=True,
            source_files=[
                {"file": s["file"], "found": True, "size_bytes": s["size_bytes"], "location": "object storage (source of truth)"}
                for s in manifest["sources"]
            ],
            total_channels=manifest["total_channels"],
            access_mode="r2_tiles",
            store=store_info,
            bundle={
                "schema_version": manifest["schema_version"],
                "created_utc": manifest.get("created_utc"),
                "tile_size": manifest["tiles"]["tile_size"],
                "n_tiles": len(manifest["tiles"]["entries"]),
                "validation_passed": manifest.get("validation", {}).get("passed"),
            },
            tile_cache=self.tiles.stats(),
            preview_cache=self.previews.stats(),
        )
        return out

    def metadata(self) -> dict[str, Any]:
        meta = dict(self.manifest["metadata"])
        meta["access"] = {"mode": "r2_tiles"}
        return meta

    def _check_default_render(self, stretch: str, plow: float, phigh: float, max_size: int) -> None:
        d = self.manifest["previews"]["default_params"]
        if (stretch, float(plow), float(phigh), int(max_size)) != (
                d["stretch"], float(d["percentile_low"]), float(d["percentile_high"]), int(d["max_size"])):
            raise RenderUnsupported(
                "In production (R2) mode only the default preview rendering is available "
                f"(stretch={d['stretch']}, plow={d['percentile_low']:g}, phigh={d['percentile_high']:g}, "
                f"max_size={d['max_size']}). Other renderings need the full-resolution plane; "
                "run the backend in local mode for them.",
                default_params=d,
            )

    def _preview_png(self, channel: int) -> bytes:
        key = preview_key(channel)
        cached = self.previews.get(key)
        if cached is not None:
            return cached
        entry = self.manifest["previews"]["entries"][str(channel)]
        raw = self.store.get(key)
        if len(raw) != entry["bytes"] or hashlib.sha256(raw).hexdigest() != entry["sha256"]:
            raise SpectralDataInvalid(f"{key} does not match the manifest checksum (corrupt or stale object)")
        self.previews.put(key, raw, len(raw))
        return raw

    def channel_info(
        self,
        channel: int,
        stretch: str = DEFAULT_STRETCH,
        plow: float = DEFAULT_PLOW,
        phigh: float = DEFAULT_PHIGH,
        max_size: int = DEFAULT_MAX_SIZE,
    ) -> dict[str, Any]:
        self.layout.source_for(channel)
        self._check_default_render(stretch, plow, phigh, max_size)
        meta = next(c for c in self.channels() if c["channel"] == channel)
        info = self.manifest["previews"]["entries"][str(channel)]["info"]
        query = f"stretch={stretch}&plow={plow:g}&phigh={phigh:g}&max_size={max_size}"
        return {
            **meta,
            "unit": self.layout.unit,
            "preview": {**info, "url": f"/api/spectral/channels/{channel}/preview?{query}"},
        }

    def preview_response(
        self,
        channel: int,
        stretch: str = DEFAULT_STRETCH,
        plow: float = DEFAULT_PLOW,
        phigh: float = DEFAULT_PHIGH,
        max_size: int = DEFAULT_MAX_SIZE,
        fmt: str = "png",
    ) -> tuple[bytes, str]:
        self.layout.source_for(channel)
        self._check_default_render(stretch, plow, phigh, max_size)
        png = self._preview_png(channel)
        if fmt == "png":
            return png, "image/png"
        # JPEG exactly as local mode derives it (spectral_data.save_image):
        # the same grayscale+alpha image converted to L, quality 90.
        buf = io.BytesIO()
        Image.open(io.BytesIO(png)).convert("L").save(buf, format="JPEG", quality=90)
        return buf.getvalue(), "image/jpeg"

    def spectrum(
        self,
        ra: Optional[float] = None,
        dec: Optional[float] = None,
        x: Optional[int] = None,
        y: Optional[int] = None,
    ) -> dict[str, Any]:
        return spectrum_response(self.layout, self.channels, self.pixel_series, ra=ra, dec=dec, x=x, y=y)
