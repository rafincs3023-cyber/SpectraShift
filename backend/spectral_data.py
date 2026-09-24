"""
Spectral View data service -- the 102-channel SPHEREx mosaic cubes.

This is a SEPARATE feature from the A/C/B Time Compare system (see
data_access.py / images.py / spectrum.py). Those modules serve three
single-exposure Level-2 images taken at different times; this module
serves two SPHEREx *mosaic* cubes of one sky region that together hold
102 spectral channels (~0.75-5.0 um). The mosaics are for spectral
exploration only -- they carry no temporal/motion information.

Source files (gitignored, never committed, never sent to the browser):

    data/spherex/SpectraShift_Part1_16.fits.gz      -> channels   1-16
    data/spherex/SpectraShift_Remaining86.fits.gz   -> channels  17-102

Each file has HDUs: PRIMARY, IMAGE (float32 cube, NAXIS3 = n channels),
NHITS, FLAGS, SPECTRAL_CHANNELS (per-plane detector / subchannel /
wavelength table) and WCS-WAVE. Only IMAGE and the channel tables are used.

Access strategy (the cubes are ~3 GB of IMAGE data once decompressed, and
gzip has no random access):

1.  Fast header parse: the PRIMARY and IMAGE headers are read straight off
    the gzip stream (a few KB), which yields the cube shape, the celestial
    WCS and the byte offset of the IMAGE data. astropy's fits.open() is
    avoided for this because on .gz files it decompresses the whole stream
    before returning.

2.  Derived access cache (optional, built once by build_spectral_cache.py):
    the IMAGE planes of both files are written, channel-major, into one
    uncompressed float32 .npy file that is opened with np.load(mmap_mode="r").
    A spectrum lookup then touches 102 single pixels and a preview touches
    one plane; the cube is never loaded into RAM. The cache lives in a
    fingerprinted directory (source file sizes + mtimes), so replacing a
    source file automatically orphans the old cache.

3.  Direct fallback (no cache built): planes / pixels are read by seeking
    forward in the gzip stream to the exact byte offset. This is correct
    but slow for high channels (decompression up to that plane), so it is
    serialized per file.

Values are never invented: non-finite pixels are reported as null.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import math
import os
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator, Optional

import numpy as np
from astropy.io import fits
from astropy.wcs import WCS
from astropy.wcs.utils import proj_plane_pixel_scales
from PIL import Image

BASE_DIR = Path(__file__).resolve().parent.parent
SPHEREX_DIR = Path(os.environ.get("SPECTRASHIFT_SPHEREX_DIR", BASE_DIR / "data" / "spherex"))
CACHE_ROOT = Path(os.environ.get("SPECTRASHIFT_SPECTRAL_CACHE_DIR", SPHEREX_DIR / "cache"))

# Ordered: channels are numbered consecutively across these files.
SOURCE_FILENAMES = (
    "SpectraShift_Part1_16.fits.gz",
    "SpectraShift_Remaining86.fits.gz",
)

FITS_BLOCK = 2880
CUBE_FILENAME = "image_cube.f32.npy"
CHANNELS_FILENAME = "channels.json"
STATS_FILENAME = "channel_stats.json"
PREVIEW_SUBDIR = "previews"

# Preview defaults: asinh stretch between the 0.5th and 99.5th percentiles of
# the finite pixels -- the same display convention as the Time Compare
# previews in images.py.
DEFAULT_STRETCH = "asinh"
STRETCHES = ("asinh", "linear")
DEFAULT_PLOW = 0.5
DEFAULT_PHIGH = 99.5
DEFAULT_MAX_SIZE = 1200
ASINH_SOFTENING = 10.0

_BITPIX_DTYPES = {8: ">u1", 16: ">i2", 32: ">i4", 64: ">i8", -32: ">f4", -64: ">f8"}
_CELESTIAL_KEY = re.compile(
    r"^(CTYPE|CRPIX|CRVAL|CDELT|CUNIT|CROTA|CNAME)[12]$|^(PC|CD)[12]_[12]$"
    r"|^(LONPOLE|LATPOLE|RADESYS|EQUINOX)$"
)


# ---------------------------------------------------------------------------
# Errors (mapped to HTTP status codes by spectral_api.py)
# ---------------------------------------------------------------------------

class SpectralError(Exception):
    """Base class; `code` is a stable machine-readable identifier."""

    code = "spectral_error"

    def __init__(self, message: str, **extra: Any) -> None:
        super().__init__(message)
        self.message = message
        self.extra = extra

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, **self.extra}


class SpectralDataMissing(SpectralError):
    code = "spectral_data_missing"


class SpectralDataInvalid(SpectralError):
    code = "spectral_data_invalid"


class ChannelOutOfRange(SpectralError):
    code = "invalid_channel"


class OutsideFootprint(SpectralError):
    code = "outside_footprint"


# ---------------------------------------------------------------------------
# Source layout (fast: headers only)
# ---------------------------------------------------------------------------

@dataclass
class SourceFile:
    path: Path
    first_channel: int          # global, 1-based
    n_channels: int
    data_offset: int            # byte offset of IMAGE data in the decompressed stream
    dtype: np.dtype             # on-disk (big-endian) dtype
    bscale: float
    bzero: float
    wlmin: Optional[float]
    wlmax: Optional[float]

    @property
    def last_channel(self) -> int:
        return self.first_channel + self.n_channels - 1

    def local_index(self, channel: int) -> int:
        return channel - self.first_channel


@dataclass
class Layout:
    sources: list[SourceFile]
    width: int                  # NAXIS1 (x, RA axis)
    height: int                 # NAXIS2 (y, Dec axis)
    total_channels: int
    unit: Optional[str]
    wcs: WCS
    wcs_header: fits.Header
    fingerprint: str
    warnings: list[str] = field(default_factory=list)

    @property
    def plane_pixels(self) -> int:
        return self.width * self.height

    def source_for(self, channel: int) -> SourceFile:
        if not isinstance(channel, (int, np.integer)) or not (1 <= channel <= self.total_channels):
            raise ChannelOutOfRange(
                f"channel must be an integer from 1 to {self.total_channels}; got {channel!r}",
                valid_range=[1, self.total_channels],
            )
        for src in self.sources:
            if src.first_channel <= channel <= src.last_channel:
                return src
        raise ChannelOutOfRange(f"channel {channel} is not mapped to any source file")


def _pad(n: int) -> int:
    return (n + FITS_BLOCK - 1) // FITS_BLOCK * FITS_BLOCK


def _data_size(header: fits.Header) -> int:
    naxis = header.get("NAXIS", 0)
    if naxis == 0:
        return 0
    count = 1
    for i in range(1, naxis + 1):
        count *= header[f"NAXIS{i}"]
    bits = abs(header["BITPIX"]) * header.get("GCOUNT", 1) * (count + header.get("PCOUNT", 0))
    return _pad(bits // 8)


def _read_image_header(path: Path) -> tuple[fits.Header, int]:
    """Return (IMAGE header, byte offset of its data) by walking HDU headers
    on the decompressed stream, seeking over any data units before IMAGE."""
    try:
        with gzip.open(path, "rb") as stream:
            while True:
                header = fits.Header.fromfile(stream)
                if header.get("EXTNAME", "").strip().upper() == "IMAGE":
                    return header, stream.tell()
                stream.seek(_data_size(header), os.SEEK_CUR)
    except (EOFError, OSError, ValueError) as exc:
        raise SpectralDataInvalid(f"{path.name}: could not read IMAGE HDU header ({exc})") from exc


def _celestial_wcs(header: fits.Header, path: Path) -> tuple[WCS, fits.Header]:
    """2-D celestial WCS from the cube header. The spectral axes are WAVE-TAB
    (lookup-table) axes, which astropy can only parse with the full HDUList;
    channel wavelengths come from SPECTRAL_CHANNELS instead."""
    cel = fits.Header()
    cel["NAXIS"] = 2
    cel["NAXIS1"] = header["NAXIS1"]
    cel["NAXIS2"] = header["NAXIS2"]
    for card in header.cards:
        if _CELESTIAL_KEY.match(card.keyword):
            cel[card.keyword] = card.value
    try:
        wcs = WCS(cel)
    except Exception as exc:  # noqa: BLE001 - astropy raises many types here
        raise SpectralDataInvalid(f"{path.name}: invalid celestial WCS ({exc})") from exc
    if not wcs.has_celestial:
        raise SpectralDataInvalid(f"{path.name}: IMAGE header has no celestial WCS")
    return wcs, cel


def _fingerprint(paths: list[Path]) -> str:
    h = hashlib.sha256()
    for p in paths:
        st = p.stat()
        h.update(f"{p.name}:{st.st_size}:{st.st_mtime_ns};".encode())
    return h.hexdigest()[:16]


def load_layout(spherex_dir: Path = SPHEREX_DIR) -> Layout:
    paths = [spherex_dir / name for name in SOURCE_FILENAMES]
    missing = [p.name for p in paths if not p.is_file()]
    if missing:
        raise SpectralDataMissing(
            f"SPHEREx mosaic file(s) not found in {spherex_dir}: {', '.join(missing)}",
            missing_files=missing,
        )

    sources: list[SourceFile] = []
    ref: Optional[tuple[int, int, fits.Header]] = None
    wcs = cel_header = unit = None
    next_channel = 1
    for path in paths:
        header, offset = _read_image_header(path)
        if header.get("NAXIS") != 3:
            raise SpectralDataInvalid(f"{path.name}: IMAGE HDU is not a 3-D cube (NAXIS={header.get('NAXIS')})")
        bitpix = header["BITPIX"]
        if bitpix not in _BITPIX_DTYPES:
            raise SpectralDataInvalid(f"{path.name}: unsupported BITPIX {bitpix}")

        this_wcs, this_cel = _celestial_wcs(header, path)
        shape = (header["NAXIS1"], header["NAXIS2"])
        if ref is None:
            ref = (*shape, this_cel)
            wcs, cel_header, unit = this_wcs, this_cel, header.get("BUNIT")
        else:
            if shape != ref[:2]:
                raise SpectralDataInvalid(
                    f"{path.name}: spatial size {shape} differs from {paths[0].name} {ref[:2]}"
                )
            for key in ("CTYPE1", "CTYPE2", "CRPIX1", "CRPIX2", "CRVAL1", "CRVAL2", "CDELT1", "CDELT2"):
                a, b = ref[2].get(key), this_cel.get(key)
                same = a == b if isinstance(a, str) or isinstance(b, str) else (
                    a is not None and b is not None and math.isclose(a, b, rel_tol=0, abs_tol=1e-10)
                )
                if not same:
                    raise SpectralDataInvalid(
                        f"{path.name}: celestial WCS keyword {key}={b!r} differs from "
                        f"{paths[0].name} ({a!r}); cubes are not on the same pixel grid"
                    )

        n = int(header["NAXIS3"])
        sources.append(SourceFile(
            path=path,
            first_channel=next_channel,
            n_channels=n,
            data_offset=offset,
            dtype=np.dtype(_BITPIX_DTYPES[bitpix]),
            bscale=float(header.get("BSCALE", 1.0)),
            bzero=float(header.get("BZERO", 0.0)),
            wlmin=header.get("WLMIN"),
            wlmax=header.get("WLMAX"),
        ))
        next_channel += n

    layout = Layout(
        sources=sources,
        width=ref[0],
        height=ref[1],
        total_channels=next_channel - 1,
        unit=unit,
        wcs=wcs,
        wcs_header=cel_header,
        fingerprint=_fingerprint(paths),
    )
    for prev, nxt in zip(sources, sources[1:]):
        if prev.wlmax is not None and nxt.wlmin is not None and not prev.wlmax < nxt.wlmin:
            layout.warnings.append(
                f"{nxt.path.name} WLMIN={nxt.wlmin} does not follow {prev.path.name} WLMAX={prev.wlmax}"
            )
    return layout


# ---------------------------------------------------------------------------
# Direct (uncached) reads from the gzip stream
# ---------------------------------------------------------------------------

def _decode(raw: bytes, src: SourceFile) -> np.ndarray:
    arr = np.frombuffer(raw, dtype=src.dtype).astype(np.float32)
    if src.bscale != 1.0 or src.bzero != 0.0:
        arr = arr * np.float32(src.bscale) + np.float32(src.bzero)
    return arr


def _read_exact(stream, nbytes: int, src: SourceFile) -> bytes:
    raw = stream.read(nbytes)
    if len(raw) != nbytes:
        raise SpectralDataInvalid(f"{src.path.name}: unexpected end of IMAGE data (truncated file?)")
    return raw


def iter_planes_from_fits(layout: Layout, src: SourceFile) -> Iterator[tuple[int, np.ndarray]]:
    """Yield (global channel, 2-D float32 plane) for every plane of one
    source file in a single forward pass over the gzip stream."""
    nbytes = layout.plane_pixels * src.dtype.itemsize
    try:
        with gzip.open(src.path, "rb") as stream:
            stream.seek(src.data_offset)
            for local in range(src.n_channels):
                plane = _decode(_read_exact(stream, nbytes, src), src)
                yield src.first_channel + local, plane.reshape(layout.height, layout.width)
    except (EOFError, OSError, gzip.BadGzipFile) as exc:
        raise SpectralDataInvalid(f"{src.path.name}: failed reading IMAGE data ({exc})") from exc


def read_plane_from_fits(layout: Layout, channel: int) -> np.ndarray:
    src = layout.source_for(channel)
    nbytes = layout.plane_pixels * src.dtype.itemsize
    try:
        with gzip.open(src.path, "rb") as stream:
            stream.seek(src.data_offset + src.local_index(channel) * nbytes)
            plane = _decode(_read_exact(stream, nbytes, src), src)
    except (EOFError, OSError, gzip.BadGzipFile) as exc:
        raise SpectralDataInvalid(f"{src.path.name}: failed reading channel {channel} ({exc})") from exc
    return plane.reshape(layout.height, layout.width)


def read_pixel_series_from_fits(layout: Layout, x: int, y: int) -> np.ndarray:
    """All channels at one pixel, one forward pass per source file."""
    out = np.empty(layout.total_channels, dtype=np.float32)
    pixel_offset = (y * layout.width + x)
    for src in layout.sources:
        item = src.dtype.itemsize
        plane_bytes = layout.plane_pixels * item
        try:
            with gzip.open(src.path, "rb") as stream:
                for local in range(src.n_channels):
                    stream.seek(src.data_offset + local * plane_bytes + pixel_offset * item)
                    out[src.first_channel - 1 + local] = _decode(_read_exact(stream, item, src), src)[0]
        except (EOFError, OSError, gzip.BadGzipFile) as exc:
            raise SpectralDataInvalid(f"{src.path.name}: failed reading pixel ({x}, {y}) ({exc})") from exc
    return out


# ---------------------------------------------------------------------------
# Channel metadata (SPECTRAL_CHANNELS / WCS-WAVE tables)
# ---------------------------------------------------------------------------

def _f(value: Any, ndigits: int = 6) -> Optional[float]:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return round(v, ndigits) if math.isfinite(v) else None


def read_channel_tables(layout: Layout) -> tuple[list[dict[str, Any]], list[str]]:
    """Per-channel metadata straight from each file's SPECTRAL_CHANNELS table.
    These tables sit after the three cubes, so this decompresses each file
    once (slow); the result is cached as JSON by SpectralService."""
    channels: list[dict[str, Any]] = []
    warnings: list[str] = []
    for src in layout.sources:
        try:
            with fits.open(src.path, lazy_load_hdus=True, memmap=False) as hdul:
                table = hdul["SPECTRAL_CHANNELS"].data
                wave_table = hdul["WCS-WAVE"].data if "WCS-WAVE" in hdul else None
                rows = [{name: table[name][i] for name in table.names} for i in range(len(table))]
                planes = np.asarray(wave_table["PLANE"][0]).ravel() if wave_table is not None else None
                tab_wl = np.asarray(wave_table["WAVELENGTHS"][0]).ravel() if wave_table is not None else None
        except KeyError as exc:
            raise SpectralDataInvalid(f"{src.path.name}: missing HDU {exc}") from exc
        except (OSError, ValueError, EOFError) as exc:
            raise SpectralDataInvalid(f"{src.path.name}: failed reading channel tables ({exc})") from exc

        if len(rows) != src.n_channels:
            raise SpectralDataInvalid(
                f"{src.path.name}: SPECTRAL_CHANNELS has {len(rows)} rows but IMAGE has {src.n_channels} planes"
            )
        if planes is not None and list(planes) != list(range(1, src.n_channels + 1)):
            raise SpectralDataInvalid(f"{src.path.name}: WCS-WAVE PLANE column is not 1..{src.n_channels}")

        for local, row in enumerate(rows):
            wl = _f(row.get("WAVELENGTH"))
            if tab_wl is not None and wl is not None and not math.isclose(float(tab_wl[local]), wl, abs_tol=1e-4):
                warnings.append(
                    f"{src.path.name} plane {local + 1}: SPECTRAL_CHANNELS wavelength {wl} "
                    f"!= WCS-WAVE {float(tab_wl[local])}"
                )
            channels.append({
                "channel": src.first_channel + local,
                "source_file": src.path.name,
                "source_plane": local + 1,
                "detector": int(row["DETECTOR"]) if "DETECTOR" in row else None,
                "subchannel": int(row["SUBCHAN"]) if "SUBCHAN" in row else None,
                "wavelength_um": wl,
                "wavelength_min_um": _f(row.get("WL_MIN")),
                "wavelength_max_um": _f(row.get("WL_MAX")),
                "bandwidth_um": _f(row.get("BANDWIDTH")),
                "resolving_power": _f(row.get("R"), 3),
                "resolving_power_std": _f(row.get("R_STD"), 3),
            })
    return channels, warnings


# ---------------------------------------------------------------------------
# Preview rendering
# ---------------------------------------------------------------------------

def render_preview(
    plane: np.ndarray,
    stretch: str = DEFAULT_STRETCH,
    plow: float = DEFAULT_PLOW,
    phigh: float = DEFAULT_PHIGH,
    max_size: int = DEFAULT_MAX_SIZE,
) -> tuple[Image.Image, dict[str, Any]]:
    """Grayscale + alpha preview. Display limits are percentiles of the finite
    pixels; pixels with no data (NaN) are fully transparent. The image is
    flipped vertically so north is up and east is left (CDELT1 < 0), the
    same orientation as the Time Compare previews."""
    finite = np.isfinite(plane)
    n_finite = int(finite.sum())
    info: dict[str, Any] = {
        "stretch": stretch, "percentile_low": plow, "percentile_high": phigh,
        "finite_fraction": n_finite / plane.size if plane.size else 0.0,
        "vmin": None, "vmax": None,
    }
    if n_finite == 0:
        lum = np.zeros(plane.shape, dtype=np.uint8)
    else:
        vals = plane[finite]
        vmin, vmax = (float(v) for v in np.percentile(vals, [plow, phigh]))
        if not vmax > vmin:
            vmax = vmin + (abs(vmin) * 1e-6 or 1e-6)
        info["vmin"], info["vmax"] = vmin, vmax
        x = np.clip((np.where(finite, plane, vmin) - vmin) / (vmax - vmin), 0.0, 1.0)
        if stretch == "asinh":
            x = np.arcsinh(x * ASINH_SOFTENING) / np.arcsinh(ASINH_SOFTENING)
        lum = (x * 255.0 + 0.5).astype(np.uint8)
    alpha = np.where(finite, 255, 0).astype(np.uint8)

    img = Image.fromarray(np.flipud(np.dstack([lum, alpha])), mode="LA")
    w, h = img.size
    if max(w, h) > max_size:
        scale = max_size / max(w, h)
        img = img.resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.BOX)
    info["width"], info["height"] = img.size
    return img, info


# ---------------------------------------------------------------------------
# Service (lazy, thread-safe, process-wide singleton)
# ---------------------------------------------------------------------------

class SpectralService:
    def __init__(self, spherex_dir: Path = SPHEREX_DIR, cache_root: Path = CACHE_ROOT) -> None:
        self.spherex_dir = spherex_dir
        self.cache_root = cache_root
        self._lock = threading.RLock()  # re-entrant: cube()/channels() read self.layout while holding it
        self._fits_lock = threading.Lock()   # serializes slow gzip-stream reads
        self._render_lock = threading.Lock()
        self._layout: Optional[Layout] = None
        self._channels: Optional[list[dict[str, Any]]] = None
        self._channel_warnings: list[str] = []
        self._cube: Optional[np.ndarray] = None
        self._cube_checked = False

    # -- lazy state -----------------------------------------------------------

    @property
    def layout(self) -> Layout:
        if self._layout is None:
            with self._lock:
                if self._layout is None:
                    self._layout = load_layout(self.spherex_dir)
        return self._layout

    @property
    def cache_dir(self) -> Path:
        return self.cache_root / self.layout.fingerprint

    def cube(self) -> Optional[np.ndarray]:
        """Memory-mapped channel-major cube (channels, y, x), or None if the
        access cache has not been built."""
        if not self._cube_checked:
            with self._lock:
                if not self._cube_checked:
                    path = self.cache_dir / CUBE_FILENAME
                    if path.is_file():
                        cube = np.load(path, mmap_mode="r")
                        lay = self.layout
                        expected = (lay.total_channels, lay.height, lay.width)
                        if cube.shape == expected and cube.dtype == np.float32:
                            self._cube = cube
                    self._cube_checked = True
        return self._cube

    def reset_cache_handles(self) -> None:
        """Re-check the cache on next access (used after a cache build)."""
        with self._lock:
            self._cube = None
            self._cube_checked = False
            self._channels = None

    def channels(self) -> list[dict[str, Any]]:
        if self._channels is None:
            with self._lock:
                if self._channels is None:
                    path = self.cache_dir / CHANNELS_FILENAME
                    cached: dict[str, Any] = {}
                    if path.is_file():
                        try:
                            cached = json.loads(path.read_text())
                        except (OSError, ValueError):
                            cached = {}
                    if len(cached.get("channels") or []) != self.layout.total_channels:
                        with self._fits_lock:
                            channels, warnings = read_channel_tables(self.layout)
                        cached = {"channels": channels, "warnings": warnings}
                        _write_json_atomic(path, cached)
                    self._channel_warnings = list(cached.get("warnings") or [])
                    self._channels = cached["channels"]
        return self._channels

    def channel_stats(self) -> dict[str, Any]:
        path = self.cache_dir / STATS_FILENAME
        try:
            return json.loads(path.read_text()) if path.is_file() else {}
        except (OSError, ValueError):
            return {}

    def status(self) -> dict[str, Any]:
        files = [
            {"file": name, "found": (self.spherex_dir / name).is_file(),
             "size_bytes": (self.spherex_dir / name).stat().st_size
             if (self.spherex_dir / name).is_file() else None}
            for name in SOURCE_FILENAMES
        ]
        out: dict[str, Any] = {"source_files": files}
        try:
            lay = self.layout
        except SpectralError as exc:
            out.update(available=False, error=exc.as_dict())
            return out
        cube = self.cube()
        out.update(
            available=True,
            total_channels=lay.total_channels,
            access_mode="memmap_cache" if cube is not None else "direct_fits_stream",
            cache_dir=str(self.cache_dir),
            cube_cache_built=cube is not None,
            channel_table_cached=(self.cache_dir / CHANNELS_FILENAME).is_file(),
        )
        if cube is None:
            out["hint"] = (
                "Run `python backend/build_spectral_cache.py` once to build the "
                "memory-mapped access cache; until then reads decompress the "
                "gzip cubes on demand and high channels are slow."
            )
        return out

    # -- data access ----------------------------------------------------------

    def plane(self, channel: int) -> np.ndarray:
        self.layout.source_for(channel)  # validates
        cube = self.cube()
        if cube is not None:
            return np.asarray(cube[channel - 1], dtype=np.float32)
        with self._fits_lock:
            return read_plane_from_fits(self.layout, channel)

    def pixel_series(self, x: int, y: int) -> tuple[np.ndarray, str]:
        cube = self.cube()
        if cube is not None:
            return np.asarray(cube[:, y, x], dtype=np.float32), "memmap_cache"
        with self._fits_lock:
            return read_pixel_series_from_fits(self.layout, x, y), "direct_fits_stream"

    # -- public API -----------------------------------------------------------

    def metadata(self) -> dict[str, Any]:
        lay = self.layout
        channels = self.channels()
        stats = self.channel_stats()
        chan_out = []
        for ch in channels:
            s = stats.get(str(ch["channel"]), {})
            chan_out.append({
                **ch,
                "coverage_fraction": s.get("finite_fraction"),
                "preview_url": f"/api/spectral/channels/{ch['channel']}/preview",
            })

        wl_lo = [c["wavelength_min_um"] for c in channels if c["wavelength_min_um"] is not None]
        wl_hi = [c["wavelength_max_um"] for c in channels if c["wavelength_max_um"] is not None]
        wl_c = [c["wavelength_um"] for c in channels if c["wavelength_um"] is not None]
        monotonic = all(a < b for a, b in zip(wl_c, wl_c[1:])) and len(wl_c) == len(channels)

        wcs = lay.wcs
        corners_pix = [(-0.5, -0.5), (lay.width - 0.5, -0.5),
                       (lay.width - 0.5, lay.height - 0.5), (-0.5, lay.height - 0.5)]
        corners = [
            {"ra_deg": _f(ra, 7), "dec_deg": _f(dec, 7)}
            for ra, dec in (wcs.pixel_to_world_values(x, y) for x, y in corners_pix)
        ]
        cra, cdec = wcs.pixel_to_world_values((lay.width - 1) / 2, (lay.height - 1) / 2)
        scales = np.abs(proj_plane_pixel_scales(wcs))  # deg / pixel

        warnings = list(lay.warnings) + self._channel_warnings
        if not monotonic:
            warnings.append("channel center wavelengths are not strictly increasing with channel number")

        return {
            "dataset": "SPHEREx spectral mosaic (IRSA SPHEREx Mosaic service)",
            "purpose": "spectral exploration of a single sky region; not a time/motion comparison",
            "total_channels": lay.total_channels,
            "image": {
                "width": lay.width,
                "height": lay.height,
                "unit": lay.unit,
                "pixel_scale_arcsec": [_f(float(s) * 3600, 4) for s in scales],
                "center": {"ra_deg": _f(cra, 7), "dec_deg": _f(cdec, 7)},
                "corners": corners,
                "wcs": {k: lay.wcs_header[k] for k in lay.wcs_header if k not in ("NAXIS", "NAXIS1", "NAXIS2")},
                "pixel_convention": (
                    "0-based pixel indices; x along NAXIS1 (RA axis), y along NAXIS2 (Dec axis), "
                    "y=0 is the bottom row of the FITS array. Previews are flipped vertically "
                    "(north up, east left), so preview row 0 is FITS row height-1."
                ),
            },
            "wavelength_range_um": {
                "min": min(wl_lo) if wl_lo else None,
                "max": max(wl_hi) if wl_hi else None,
                "center_min": min(wl_c) if wl_c else None,
                "center_max": max(wl_c) if wl_c else None,
            },
            "sources": [
                {
                    "file": s.path.name,
                    "first_channel": s.first_channel,
                    "last_channel": s.last_channel,
                    "n_channels": s.n_channels,
                    "header_wlmin_um": s.wlmin,
                    "header_wlmax_um": s.wlmax,
                }
                for s in lay.sources
            ],
            "channels": chan_out,
            "checks": {
                "channel_numbers_contiguous": [c["channel"] for c in channels] == list(range(1, lay.total_channels + 1)),
                "wavelengths_strictly_increasing": monotonic,
                "identical_spatial_grid": True,  # enforced in load_layout
            },
            "warnings": warnings,
            "access": {"mode": "memmap_cache" if self.cube() is not None else "direct_fits_stream"},
        }

    def preview(
        self,
        channel: int,
        stretch: str = DEFAULT_STRETCH,
        plow: float = DEFAULT_PLOW,
        phigh: float = DEFAULT_PHIGH,
        max_size: int = DEFAULT_MAX_SIZE,
        fmt: str = "png",
    ) -> tuple[Path, dict[str, Any]]:
        """Return (cached image path, render info), rendering on first use."""
        self.layout.source_for(channel)
        key = f"ch{channel:03d}_{stretch}_p{plow:g}-{phigh:g}_s{max_size}"
        out_dir = self.cache_dir / PREVIEW_SUBDIR
        img_path = out_dir / f"{key}.{fmt}"
        info_path = out_dir / f"{key}.json"
        if img_path.is_file() and info_path.is_file():
            return img_path, json.loads(info_path.read_text())

        with self._render_lock:
            if img_path.is_file() and info_path.is_file():
                return img_path, json.loads(info_path.read_text())
            img, info = render_preview(self.plane(channel), stretch, plow, phigh, max_size)
            info["channel"] = channel
            save_image(img, img_path, fmt)
            _write_json_atomic(info_path, info)
        return img_path, info

    def spectrum(
        self,
        ra: Optional[float] = None,
        dec: Optional[float] = None,
        x: Optional[int] = None,
        y: Optional[int] = None,
    ) -> dict[str, Any]:
        lay = self.layout
        if ra is not None and dec is not None:
            try:
                xf, yf = (float(v) for v in lay.wcs.world_to_pixel_values(ra % 360.0, dec))
            except Exception as exc:  # noqa: BLE001
                raise SpectralDataInvalid(f"WCS transform failed for RA={ra}, Dec={dec} ({exc})") from exc
            pixel_input = False
        else:
            xf, yf = float(x), float(y)
            pixel_input = True

        if not (math.isfinite(xf) and math.isfinite(yf)):
            raise OutsideFootprint(
                f"RA={ra}, Dec={dec} does not project onto the mosaic plane",
                ra_deg=ra, dec_deg=dec,
            )
        xi, yi = int(math.floor(xf + 0.5)), int(math.floor(yf + 0.5))
        if not (0 <= xi < lay.width and 0 <= yi < lay.height):
            where = f"pixel ({xi}, {yi})" if pixel_input else f"RA={ra}, Dec={dec} (pixel {xf:.1f}, {yf:.1f})"
            raise OutsideFootprint(
                f"{where} is outside the {lay.width}x{lay.height} mosaic",
                ra_deg=ra, dec_deg=dec, pixel_x=_f(xf, 3), pixel_y=_f(yf, 3),
                width=lay.width, height=lay.height,
            )

        values, mode = self.pixel_series(xi, yi)
        channels = self.channels()
        samples = []
        for ch, v in zip(channels, values):
            ok = bool(np.isfinite(v))
            samples.append({
                "channel": ch["channel"],
                "detector": ch["detector"],
                "subchannel": ch["subchannel"],
                "wavelength_um": ch["wavelength_um"],
                "bandwidth_um": ch["bandwidth_um"],
                "value": float(v) if ok else None,
                "valid": ok,
            })
        n_valid = sum(s["valid"] for s in samples)
        pra, pdec = lay.wcs.pixel_to_world_values(xi, yi)

        return {
            "query": {"ra_deg": ra, "dec_deg": dec} if not pixel_input else {"x": x, "y": y},
            "pixel": {
                "x": _f(xf, 3), "y": _f(yf, 3),          # exact (sub-pixel) position
                "x_index": xi, "y_index": yi,            # sampled pixel
                "x_frac": _f((xi + 0.5) / lay.width, 6),             # preview overlay,
                "y_frac": _f(1.0 - (yi + 0.5) / lay.height, 6),      # top-left origin
            },
            "pixel_center": {"ra_deg": _f(pra, 7), "dec_deg": _f(pdec, 7)},
            "in_footprint": True,
            "unit": lay.unit,
            "quantity": "surface brightness of the single nearest mosaic pixel (no aperture, no interpolation)",
            "n_channels": len(samples),
            "n_valid": n_valid,
            "has_data": n_valid > 0,
            "samples": samples,
            "access_mode": mode,
            "note": (
                "Values are read directly from the SPHEREx mosaic IMAGE cubes. "
                "null means the pixel is non-finite (no coverage) in that channel, not zero."
            ),
        }


def save_image(img: Image.Image, path: Path, fmt: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    if fmt == "jpeg":
        # JPEG has no alpha: no-data pixels render black.
        img.convert("L").save(tmp, format="JPEG", quality=90)
    else:
        img.save(tmp, format="PNG", optimize=False, compress_level=6)
    os.replace(tmp, path)


def _write_json_atomic(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1))
    os.replace(tmp, path)


service = SpectralService()
