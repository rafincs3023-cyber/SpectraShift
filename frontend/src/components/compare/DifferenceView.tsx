import type { ReactNode } from "react";
import { imageUrl } from "../../api/client";

export function DifferenceView({
  available,
  previewUrl,
  epochA,
  epochB,
  alt = "Epoch A minus Epoch B difference",
  caption,
}: {
  available: boolean;
  previewUrl: string | null;
  epochA: string;
  epochB: string;
  alt?: string;
  /** Replaces the default A − B explanation (e.g. for a B − A product). */
  caption?: ReactNode;
}) {
  if (!available || !previewUrl) {
    return (
      <div className="state-panel state-placeholder">
        <p>
          No precomputed difference product exists for Epoch {epochA} vs
          Epoch {epochB}.
        </p>
        <p className="section-note">
          Only Epoch A − Epoch B was computed in the scientific pipeline.
          Select Epoch A and Epoch B to view the difference, or use
          Side by Side / Blink mode for this pair.
        </p>
      </div>
    );
  }

  return (
    <div className="difference-compare">
      <div className="obs-image-frame">
        <img
          src={imageUrl(previewUrl)}
          alt={alt}
          className="obs-image"
          draggable={false}
          crossOrigin="anonymous"
        />
      </div>
      {caption ?? (
        <p className="section-note">
          Precomputed difference: Epoch A − Epoch B. Red = brighter in Epoch A,
          blue = brighter in Epoch B. This reflects apparent change between
          the two observations, not a confirmed physical object.
        </p>
      )}
    </div>
  );
}
