"""
Image-rendering helpers shared by the ~6-month Time Compare previews and the
two-epoch candidate cutouts: an asinh display stretch and a diverging
red/blue render for difference images. Display choices only -- the
underlying pixel values are never changed. Rendered PNGs are cached under
preview_cache/.
"""

from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image

PREVIEW_DIR = Path(__file__).resolve().parent / "preview_cache"
PREVIEW_DIR.mkdir(exist_ok=True)

MAX_PREVIEW_SIZE = 900  # px, longest side; keeps PNGs small on this box


def _stretch_to_uint8(
    data: np.ndarray,
    plo: float = 0.5,
    phi: float = 99.5,
    lo: Optional[float] = None,
    hi: Optional[float] = None,
) -> np.ndarray:
    """Standard astronomical asinh (Lupton et al. 2004-style) stretch: keeps
    bright stars from saturating the display while making faint,
    real (e.g. threshold-level) detections visible -- a display choice
    only, the underlying pixel values are untouched. Pass lo/hi to share
    one fixed display range across several images instead of per-image
    percentiles."""
    finite = np.isfinite(data)
    if not finite.any():
        return np.zeros(data.shape, dtype=np.uint8)
    if lo is None or hi is None:
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


def _save_diverging(
    data: np.ndarray, out_path: Path, max_size: Optional[int] = MAX_PREVIEW_SIZE
) -> None:
    """Diverging red/blue render for a difference image, symmetric about 0.
    max_size=None keeps native resolution."""
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
    # positive -> red, negative -> blue
    rgb[pos, 0] = (norm[pos] * 255).astype(np.uint8)
    rgb[neg, 2] = (-norm[neg] * 255).astype(np.uint8)
    base = 40  # faint neutral gray so zero-regions aren't pure black
    rgb[..., :] = np.maximum(rgb, base * (~pos & ~neg)[..., None])

    flipped = np.flipud(rgb)
    img = Image.fromarray(flipped, mode="RGB")
    if max_size is not None:
        img = _resize_longest_side(img, max_size)
    img.save(out_path, format="PNG", optimize=True)
