import { useRef, type CSSProperties, type MouseEvent } from "react";
import { ZoomPanViewer } from "../explore/ZoomPanViewer";
import { clickToPixel, type PixelPick } from "./spectralUtils";

const DRAG_TOLERANCE_PX = 4;

export function SpectralImageViewer({
  src,
  channel,
  wavelengthUm,
  mosaicWidth,
  mosaicHeight,
  loading,
  error,
  onRetry,
  marker,
  onPick,
  onPickOutside,
}: {
  src: string | null;
  channel: number;
  wavelengthUm: number | null;
  mosaicWidth: number;
  mosaicHeight: number;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
  marker: { xFrac: number; yFrac: number; pending: boolean } | null;
  onPick: (pick: PixelPick) => void;
  onPickOutside: () => void;
}) {
  const imgRef = useRef<HTMLImageElement>(null);
  const downAt = useRef<{ x: number; y: number } | null>(null);

  function handleClick(e: MouseEvent<HTMLImageElement>) {
    // Ignore the click that ends a pan-drag in the zoom viewer.
    const d = downAt.current;
    downAt.current = null;
    if (d && Math.hypot(e.clientX - d.x, e.clientY - d.y) > DRAG_TOLERANCE_PX) return;
    const img = imgRef.current;
    if (!img) return;
    const pick = clickToPixel(e.clientX, e.clientY, img.getBoundingClientRect(), mosaicWidth, mosaicHeight);
    if (pick) onPick(pick);
    else onPickOutside();
  }

  const style = { "--mosaic-aspect": `${mosaicWidth} / ${mosaicHeight}` } as CSSProperties;
  const wl = wavelengthUm === null ? "" : ` at ${wavelengthUm.toFixed(3)} µm`;

  return (
    <div className="spectral-viewer" style={style}>
      <ZoomPanViewer>
        <div className="spectral-frame">
          {src && (
            <img
              ref={imgRef}
              src={src}
              alt={`SPHEREx mosaic, channel ${channel}${wl}`}
              className="spectral-image"
              draggable={false}
              onMouseDown={(e) => (downAt.current = { x: e.clientX, y: e.clientY })}
              onClick={handleClick}
            />
          )}
          {marker && (
            <div
              className={marker.pending ? "spectral-marker spectral-marker-pending" : "spectral-marker"}
              style={{ left: `${marker.xFrac * 100}%`, top: `${marker.yFrac * 100}%` }}
              aria-hidden="true"
            />
          )}
        </div>
      </ZoomPanViewer>

      {loading && !error && (
        <div className="spectral-viewer-status" role="status">
          <div className="spinner" aria-hidden="true" />
          <span>Loading channel {channel}…</span>
        </div>
      )}
      {error && (
        <div className="spectral-viewer-status spectral-viewer-error" role="alert">
          <span>{error}</span>
          <button type="button" className="btn btn-secondary" onClick={onRetry}>
            Try again
          </button>
        </div>
      )}
    </div>
  );
}
