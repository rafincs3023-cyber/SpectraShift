import { useRef, useState } from "react";
import type { CandidateMarker, ComparePairSide } from "../../api/types";
import { imageUrl } from "../../api/client";
import { MarkerOverlay } from "./MarkerOverlay";

export function SliderCompare({
  epochA,
  epochB,
  markersA,
  markersB,
}: {
  epochA: ComparePairSide;
  epochB: ComparePairSide;
  markersA: CandidateMarker[];
  markersB: CandidateMarker[];
}) {
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
          alt={`Epoch ${epochA.epoch}`}
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
            alt={`Epoch ${epochB.epoch}`}
            className="obs-image slider-base"
            draggable={false}
            crossOrigin="anonymous"
          />
        </div>

        <div className="slider-handle" style={{ left: `${position}%` }}>
          <div className="slider-handle-grip" />
        </div>

        <span className="slider-side-label slider-side-left">
          Epoch {epochA.epoch}
        </span>
        <span className="slider-side-label slider-side-right">
          Epoch {epochB.epoch}
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
        aria-label="Slide between Epoch A and Epoch B"
      />
    </div>
  );
}
