import { useRef, useState } from "react";
import type { CandidateMarker, CompareImageSide } from "../../api/types";
import { imageUrl } from "../../api/client";
import { MarkerOverlay } from "./MarkerOverlay";

export function SliderCompare({
  epochA,
  epochB,
  markersA,
  markersB,
}: {
  epochA: CompareImageSide;
  epochB: CompareImageSide;
  markersA: CandidateMarker[];
  markersB: CandidateMarker[];
}) {
  const labelA = epochA.label ?? (epochA.epoch === "A" ? "Earlier image" : "Later image");
  const labelB = epochB.label ?? (epochB.epoch === "A" ? "Earlier image" : "Later image");
  const [position, setPosition] = useState(50); // percent, 0 = all A, 100 = all B
  const containerRef = useRef<HTMLDivElement>(null);
  const dragging = useRef(false);

  function updateFromClientX(clientX: number) {
    const el = containerRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const pct = ((clientX - rect.left) / rect.width) * 100;
    setPosition(Math.min(100, Math.max(0, pct)));
  }

  return (
    <div className="slider-compare">
      <div
        className="obs-image-frame slider-frame"
        ref={containerRef}
        onMouseDown={(e) => {
          dragging.current = true;
          updateFromClientX(e.clientX);
        }}
        onMouseMove={(e) => {
          if (dragging.current) updateFromClientX(e.clientX);
        }}
        onMouseUp={() => (dragging.current = false)}
        onMouseLeave={() => (dragging.current = false)}
        onTouchStart={(e) => updateFromClientX(e.touches[0].clientX)}
        onTouchMove={(e) => updateFromClientX(e.touches[0].clientX)}
      >
        <img
          src={imageUrl(epochA.preview_url)}
          alt={labelA}
          className="obs-image slider-base"
          draggable={false}
          crossOrigin="anonymous"
        />
        <div
          className="slider-clip"
          style={{ clipPath: `inset(0 0 0 ${position}%)` }}
        >
          <img
            src={imageUrl(epochB.preview_url)}
            alt={labelB}
            className="obs-image slider-base"
            draggable={false}
            crossOrigin="anonymous"
          />
        </div>

        <div className="slider-handle" style={{ left: `${position}%` }}>
          <div className="slider-handle-grip" />
        </div>

        <span className="slider-side-label slider-side-left">
          {labelA}
        </span>
        <span className="slider-side-label slider-side-right">
          {labelB}
        </span>

        <MarkerOverlay markers={position < 50 ? markersB : markersA} />
      </div>

      <input
        type="range"
        min={0}
        max={100}
        value={position}
        onChange={(e) => setPosition(Number(e.target.value))}
        className="slider-range-input"
        aria-label={`Slide between ${labelA} and ${labelB}`}
      />
    </div>
  );
}
