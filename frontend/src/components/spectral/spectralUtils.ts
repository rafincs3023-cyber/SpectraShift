import type { SpectralChannel } from "../../api/spectral";

export interface PixelPick {
  x: number; // 0-based FITS pixel column (NAXIS1)
  y: number; // 0-based FITS pixel row (NAXIS2), row 0 = bottom
}

/** Map a click on the rendered preview to a FITS pixel.
 *
 * The preview covers the full width x height mosaic and is flipped
 * vertically (north up), so preview row 0 is FITS row height-1. The
 * <img> box always has the mosaic's aspect ratio (object-fit: fill), and
 * getBoundingClientRect() already includes any zoom/pan transform, so the
 * click's fraction of that box is its fraction of the mosaic. Pixel i covers
 * fractions [i/W, (i+1)/W), whose centre (i+0.5)/W is exactly the x_frac the
 * backend returns; likewise y_frac = 1 - (j+0.5)/H. */
export function clickToPixel(
  clientX: number,
  clientY: number,
  rect: DOMRect,
  width: number,
  height: number
): PixelPick | null {
  const fx = (clientX - rect.left) / rect.width;
  const fy = (clientY - rect.top) / rect.height;
  if (!(fx >= 0 && fx < 1 && fy >= 0 && fy < 1)) return null;
  const col = Math.min(width - 1, Math.floor(fx * width));
  const rowFromTop = Math.min(height - 1, Math.floor(fy * height));
  return { x: col, y: height - 1 - rowFromTop };
}

export interface DetectorRange {
  detector: number;
  minUm: number;
  maxUm: number;
  firstChannel: number;
  lastChannel: number;
}

/** Wavelength coverage of each detector, derived from the real channel table. */
export function detectorRanges(channels: SpectralChannel[]): DetectorRange[] {
  const byDet = new Map<number, DetectorRange>();
  for (const c of channels) {
    if (c.detector === null || c.wavelength_min_um === null || c.wavelength_max_um === null) continue;
    const r = byDet.get(c.detector);
    if (!r) {
      byDet.set(c.detector, {
        detector: c.detector,
        minUm: c.wavelength_min_um,
        maxUm: c.wavelength_max_um,
        firstChannel: c.channel,
        lastChannel: c.channel,
      });
    } else {
      r.minUm = Math.min(r.minUm, c.wavelength_min_um);
      r.maxUm = Math.max(r.maxUm, c.wavelength_max_um);
      r.firstChannel = Math.min(r.firstChannel, c.channel);
      r.lastChannel = Math.max(r.lastChannel, c.channel);
    }
  }
  return [...byDet.values()].sort((a, b) => a.detector - b.detector);
}
