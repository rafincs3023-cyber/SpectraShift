"""
Minimal, read-only image-rendering layer for the Compare page.

Renders PNG previews from already-completed FITS products (never
re-detects, re-aligns, or re-validates anything). Every PNG is generated
once and cached to disk under preview_cache/, so repeated requests never
reload the multi-megabyte FITS arrays.

Coordinate convention for candidate markers: FITS/WCS pixel (0-indexed,
row 0 = bottom, matching the convention already used by
three_epoch_compare.py's wcs.pixel_to_world_values calls) is converted to
a top-left-origin fraction (0..1) matching standard image/CSS coordinates,
since the rendered PNG is flipped vertically (np.flipud) to display with
north/sky "up" the same way process_spherex.py's imshow(origin="lower")
did.
"""

from pathlib import Path
from typing import Optional

import numpy as np
from astropy.io import fits
from astropy.wcs import WCS
from PIL import Image

from data_access import BASE_DIR, store

PREVIEW_DIR = Path(__file__).resolve().parent / "preview_cache"
PREVIEW_DIR.mkdir(exist_ok=True)

MAX_PREVIEW_SIZE = 900  # px, longest side; keeps PNGs small on this box

NATIVE_FITS = {
    "A": BASE_DIR / "level2_2025W19_2B_0166_3D3_spx_l2b-v20-2025-247.fits",
    "C": BASE_DIR / "level2_2025W22_1B_0226_1D3_spx_l2b-v20-2025-250.fits",
    "B": BASE_DIR / "level2_2025W24_1A_0099_1D3_spx_l2b-v20-2025-252.fits",
}
ALIGNED_B_FITS = BASE_DIR / "observation_B_aligned.fits"
DIFFERENCE_FITS = BASE_DIR / "difference_A_minus_B.fits"


def _stretch_to_uint8(data: np.ndarray, plo: float = 0.5, phi: float = 99.5) -> np.ndarray:
    """Standard astronomical asinh (Lupton et al. 2004-style) stretch: keeps
    bright stars from saturating the display while making faint,
    real (e.g. threshold-level) detections visible -- a display choice
    only, the underlying pixel values are untouched."""
    finite = np.isfinite(data)
    if not finite.any():
        return np.zeros(data.shape, dtype=np.uint8)
    lo, hi = np.nanpercentile(data[finite], [plo, phi])
    if hi <= lo:
        hi = lo + 1.0
    clipped = np.clip(data, lo, None)
    clipped[~finite] = lo
    x = (clipped - lo) / (hi - lo)
    softening = 10.0
    stretched = np.arcsinh(x * softening) / np.arcsinh(softening)
    stretched = np.clip(stretched, 0, 1)
    return (stretched * 255).astype(np.uint8)


def _resize_longest_side(img: Image.Image, max_size: int) -> Image.Image:
    w, h = img.size
    if max(w, h) <= max_size:
        return img
    scale = max_size / max(w, h)
    return img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.BILINEAR)


def _load_image_data(path: Path, hdu_name: Optional[str] = "IMAGE") -> np.ndarray:
    with fits.open(path) as hdul:
        if hdu_name is not None and hdu_name in hdul:
            return hdul[hdu_name].data.astype(np.float32)
        return hdul[0].data.astype(np.float32)


def _save_grayscale(data: np.ndarray, out_path: Path) -> None:
    stretched = _stretch_to_uint8(data)
    flipped = np.flipud(stretched)  # row 0 -> top of PNG, sky "up"
    img = Image.fromarray(flipped, mode="L")
    img = _resize_longest_side(img, MAX_PREVIEW_SIZE)
    img.save(out_path, format="PNG", optimize=True)


def _save_diverging(data: np.ndarray, out_path: Path) -> None:
    """Diverging red/blue render for a difference image, symmetric about 0."""
    finite = np.isfinite(data)
    if finite.any():
        limit = float(np.nanpercentile(np.abs(data[finite]), 99))
    else:
        limit = 1.0
    limit = limit if limit > 0 else 1.0

    norm = np.clip(data, -limit, limit) / limit  # [-1, 1]
    norm[~finite] = 0.0

    rgb = np.zeros((*data.shape, 3), dtype=np.uint8)
    pos = norm > 0
    neg = norm < 0
    # positive (A brighter than B) -> red; negative (B brighter than A) -> blue
    rgb[pos, 0] = (norm[pos] * 255).astype(np.uint8)
    rgb[neg, 2] = (-norm[neg] * 255).astype(np.uint8)
    base = 40  # faint neutral gray so zero-regions aren't pure black
    rgb[..., :] = np.maximum(rgb, base * (~pos & ~neg)[..., None])

    flipped = np.flipud(rgb)
    img = Image.fromarray(flipped, mode="RGB")
    img = _resize_longest_side(img, MAX_PREVIEW_SIZE)
    img.save(out_path, format="PNG", optimize=True)


def get_native_preview_path(epoch: str) -> Path:
    if epoch not in NATIVE_FITS:
        raise ValueError(f"unknown epoch: {epoch}")
    out_path = PREVIEW_DIR / f"{epoch}_native.png"
    if not out_path.exists():
        data = _load_image_data(NATIVE_FITS[epoch])
        _save_grayscale(data, out_path)
    return out_path


def get_aligned_b_preview_path() -> Optional[Path]:
    if not ALIGNED_B_FITS.exists():
        return None
    out_path = PREVIEW_DIR / "B_aligned.png"
    if not out_path.exists():
        data = _load_image_data(ALIGNED_B_FITS, hdu_name=None)
        _save_grayscale(data, out_path)
    return out_path


def get_difference_preview_path() -> Optional[Path]:
    if not DIFFERENCE_FITS.exists():
        return None
    out_path = PREVIEW_DIR / "diff_A_minus_B.png"
    if not out_path.exists():
        data = _load_image_data(DIFFERENCE_FITS, hdu_name=None)
        _save_diverging(data, out_path)
    return out_path


def _header_for(epoch_key: str):
    """epoch_key: 'A' | 'B' | 'C' | 'B_aligned' (shares A's WCS/header)."""
    if epoch_key == "B_aligned":
        path = NATIVE_FITS["A"]
    elif epoch_key in NATIVE_FITS:
        path = NATIVE_FITS[epoch_key]
    else:
        raise ValueError(f"unknown epoch key: {epoch_key}")
    with fits.open(path) as hdul:
        return hdul["IMAGE"].header.copy()


def compute_candidate_markers(epoch_key: str) -> list[dict]:
    """Project each candidate's RA/Dec for the given epoch onto that epoch's
    pixel grid, returning top-left-origin fractional coordinates for
    absolute-positioned overlay markers. epoch_key: 'A' | 'B' | 'C' |
    'B_aligned' (B's real sky position placed on Epoch A's pixel grid,
    matching the already-computed WCS-aligned product)."""

    df = store.get("validated_with_catalogue")
    if df is None:
        df = store.get("validated_candidates")
    if df is None or len(df) == 0:
        return []

    ra_col = f"{epoch_key[0]}_ra" if epoch_key != "B_aligned" else "B_ra"
    dec_col = f"{epoch_key[0]}_dec" if epoch_key != "B_aligned" else "B_dec"
    if ra_col not in df.columns or dec_col not in df.columns:
        return []

    header = _header_for(epoch_key)
    wcs = WCS(header)
    naxis1 = header.get("NAXIS1")
    naxis2 = header.get("NAXIS2")

    markers = []
    for _, row in df.iterrows():
        ra = row[ra_col]
        dec = row[dec_col]
        if ra is None or dec is None:
            continue
        try:
            x, y = wcs.world_to_pixel_values(float(ra), float(dec))
        except Exception:
            continue
        x = float(x)
        y = float(y)
        if not (0 <= x <= naxis1 and 0 <= y <= naxis2):
            continue

        markers.append({
            "candidate_id": row["candidate_id"],
            "x_frac": x / naxis1,
            "y_frac": 1 - (y / naxis2),  # flip: FITS y-up -> CSS top-down
        })

    return markers


# ---------------------------------------------------------------------------
# Per-candidate source cutouts (Candidate Detail page)
# ---------------------------------------------------------------------------

CUTOUT_DIR = Path(__file__).resolve().parent / "cutout_cache"
CUTOUT_DIR.mkdir(exist_ok=True)

CUTOUT_HALF_SIZE = 40   # px, in the native 2040x2040 grid -> an 80x80 crop
CUTOUT_UPSCALE = 4      # nearest-neighbor upscale factor for visibility


def _candidate_row(candidate_id: str):
    df = store.get("validated_with_catalogue")
    if df is None:
        df = store.get("validated_candidates")
    if df is None:
        return None
    mask = df["candidate_id"].astype(str).str.upper() == candidate_id.strip().upper()
    matches = df[mask]
    if len(matches) == 0:
        return None
    return matches.iloc[0]


def get_candidate_cutout_path(candidate_id: str, epoch: str) -> Optional[Path]:
    """A small, real-pixel cutout centered on one candidate's detected
    position in one epoch, cropped directly from that epoch's native FITS
    IMAGE data (not from the downscaled full-frame preview, for sharper
    detail), with a crosshair marking the candidate's exact WCS-derived
    position. Nearest-neighbor upscaled only for on-screen visibility --
    no new pixel values are invented or smoothed in. Returns None if the
    candidate's position falls outside this epoch's detector."""

    if epoch not in NATIVE_FITS:
        raise ValueError(f"unknown epoch: {epoch}")

    row = _candidate_row(candidate_id)
    if row is None:
        return None

    ra = row.get(f"{epoch}_ra")
    dec = row.get(f"{epoch}_dec")
    if ra is None or dec is None:
        return None

    cache_key = f"{candidate_id.upper()}_{epoch}"
    out_path = CUTOUT_DIR / f"{cache_key}.png"
    if out_path.exists():
        return out_path

    header = _header_for(epoch)
    wcs = WCS(header)
    naxis1 = header.get("NAXIS1")
    naxis2 = header.get("NAXIS2")

    x, y = wcs.world_to_pixel_values(float(ra), float(dec))
    x, y = float(x), float(y)
    if not (0 <= x <= naxis1 and 0 <= y <= naxis2):
        return None

    data = _load_image_data(NATIVE_FITS[epoch])

    xi, yi = int(round(x)), int(round(y))
    x0 = max(0, xi - CUTOUT_HALF_SIZE)
    x1 = min(data.shape[1], xi + CUTOUT_HALF_SIZE)
    y0 = max(0, yi - CUTOUT_HALF_SIZE)
    y1 = min(data.shape[0], yi + CUTOUT_HALF_SIZE)

    crop = data[y0:y1, x0:x1]
    stretched = _stretch_to_uint8(crop)
    flipped = np.flipud(stretched)

    img = Image.fromarray(flipped, mode="L").convert("RGB")
    img = img.resize(
        (img.width * CUTOUT_UPSCALE, img.height * CUTOUT_UPSCALE),
        Image.NEAREST,
    )

    # crosshair at the candidate's exact (sub-pixel) real WCS position
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)
    px = (x - x0) * CUTOUT_UPSCALE
    py = (crop.shape[0] - (y - y0)) * CUTOUT_UPSCALE  # flip to match np.flipud
    r = 10
    color = (94, 184, 255)
    draw.line([(px - r, py), (px - 4, py)], fill=color, width=2)
    draw.line([(px + 4, py), (px + r, py)], fill=color, width=2)
    draw.line([(px, py - r), (px, py - 4)], fill=color, width=2)
    draw.line([(px, py + 4), (px, py + r)], fill=color, width=2)

    img.save(out_path, format="PNG", optimize=True)
    return out_path
