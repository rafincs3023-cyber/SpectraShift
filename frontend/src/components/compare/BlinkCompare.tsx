import { useEffect, useState } from "react";
import type { CandidateMarker, ComparePairSide } from "../../api/types";
import { imageUrl } from "../../api/client";
import { MarkerOverlay } from "./MarkerOverlay";

const INTERVAL_OPTIONS = [
  { label: "Fast (0.3s)", value: 300 },
  { label: "Normal (0.7s)", value: 700 },
  { label: "Slow (1.5s)", value: 1500 },
];

export function BlinkCompare({
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
  const [showingA, setShowingA] = useState(true);
  const [playing, setPlaying] = useState(true);
  const [intervalMs, setIntervalMs] = useState(700);

  useEffect(() => {
    if (!playing) return;
    const id = window.setInterval(() => setShowingA((v) => !v), intervalMs);
    return () => window.clearInterval(id);
  }, [playing, intervalMs]);

  const active = showingA ? epochA : epochB;
  const activeMarkers = showingA ? markersA : markersB;

  return (
    <div className="blink-compare">
      <div className="obs-image-frame">
        <img
          src={imageUrl(active.preview_url)}
          alt={`Epoch ${active.epoch}`}
          className="obs-image"
          draggable={false}
          crossOrigin="anonymous"
        />
        <MarkerOverlay markers={activeMarkers} />
        <span className="blink-epoch-chip">Epoch {active.epoch}</span>
      </div>

      <div className="blink-controls">
        <button
          type="button"
          className="btn btn-secondary"
          onClick={() => setPlaying((p) => !p)}
        >
          {playing ? "Pause" : "Play"}
        </button>
        <div className="blink-interval-options" role="radiogroup" aria-label="Blink speed">
          {INTERVAL_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              type="button"
              className={
                intervalMs === opt.value
                  ? "chip-btn chip-btn-active"
                  : "chip-btn"
              }
              onClick={() => setIntervalMs(opt.value)}
            >
              {opt.label}
            </button>
          ))}
        </div>
        <button
          type="button"
          className="btn btn-secondary"
          onClick={() => {
            setPlaying(false);
            setShowingA((v) => !v);
          }}
        >
          Step
        </button>
      </div>
    </div>
  );
}
