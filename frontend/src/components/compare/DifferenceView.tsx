import type { ReactNode } from "react";
import { imageUrl } from "../../api/client";

export function DifferenceView({
  available,
  previewUrl,
  alt = "Later image minus earlier image",
  caption,
}: {
  available: boolean;
  previewUrl: string | null;
  alt?: string;
  /** Colour key and notes shown under the image. */
  caption?: ReactNode;
}) {
  if (!available || !previewUrl) {
    return (
      <div className="state-panel state-placeholder">
        <p>The difference image is not available right now.</p>
        <p className="section-note">
          Use Side by side, Slider or Blink to compare the two images instead.
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
      {caption}
    </div>
  );
}
