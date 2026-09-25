import { useEffect, useRef, useState } from "react";
import type { CandidateMarker, CompareImageSide } from "../../api/types";
import { imageUrl } from "../../api/client";
import { MarkerOverlay } from "./MarkerOverlay";

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error(`Failed to load image: ${src}`));
    img.src = src;
  });
}

/** Re-tints a source image's grayscale channel into a single RGB channel pair. */
function tint(
  img: HTMLImageElement,
  w: number,
  h: number,
  channels: [boolean, boolean, boolean] // [R, G, B] on/off
): HTMLCanvasElement {
  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext("2d")!;
  ctx.drawImage(img, 0, 0, w, h);
  const imageData = ctx.getImageData(0, 0, w, h);
  const d = imageData.data;
  for (let i = 0; i < d.length; i += 4) {
    const gray = d[i];
    d[i] = channels[0] ? gray : 0;
    d[i + 1] = channels[1] ? gray : 0;
    d[i + 2] = channels[2] ? gray : 0;
  }
  ctx.putImageData(imageData, 0, 0);
  return canvas;
}

export function OverlayCanvas({
  epochA,
  epochB,
  markers,
}: {
  epochA: CompareImageSide;
  epochB: CompareImageSide;
  markers: CandidateMarker[];
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setReady(false);
    setError(null);

    async function run() {
      try {
        const [imgA, imgB] = await Promise.all([
          loadImage(imageUrl(epochA.preview_url)),
          loadImage(imageUrl(epochB.preview_url)),
        ]);
        if (cancelled) return;

        const w = Math.max(imgA.naturalWidth, imgB.naturalWidth);
        const h = Math.max(imgA.naturalHeight, imgB.naturalHeight);

        const canvas = canvasRef.current;
        if (!canvas) return;
        canvas.width = w;
        canvas.height = h;
        const ctx = canvas.getContext("2d")!;
        ctx.clearRect(0, 0, w, h);

        const redA = tint(imgA, w, h, [true, false, false]);
        const cyanB = tint(imgB, w, h, [false, true, true]);

        ctx.drawImage(redA, 0, 0);
        ctx.globalCompositeOperation = "lighter";
        ctx.drawImage(cyanB, 0, 0);
        ctx.globalCompositeOperation = "source-over";

        if (!cancelled) setReady(true);
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error ? err.message : "Could not render overlay"
          );
        }
      }
    }

    run();
    return () => {
      cancelled = true;
    };
  }, [epochA.preview_url, epochB.preview_url]);

  return (
    <div className="overlay-compare">
      <div className="obs-image-frame">
        <canvas ref={canvasRef} className="obs-image overlay-canvas" />
        {ready && <MarkerOverlay markers={markers} />}
        {!ready && !error && (
          <div className="overlay-loading">Rendering overlay…</div>
        )}
        {error && <div className="overlay-loading overlay-error">{error}</div>}
      </div>
      <p className="section-note">
        {epochA.label ?? `Epoch ${epochA.epoch}`} is shown in red and{" "}
        {epochB.label ?? `Epoch ${epochB.epoch}`} in cyan. Unchanged stars look
        white; a red-only or cyan-only spot shows an apparent change in
        brightness or position between the two dates. This is a viewing aid,
        not a new measurement.
      </p>
    </div>
  );
}
