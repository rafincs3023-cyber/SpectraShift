import type { EpochPosition } from "../../api/types";

const WIDTH = 320;
const HEIGHT = 320;
const MARGIN = 36;

const EPOCH_COLORS: Record<string, string> = {
  A: "#5eb8ff",
  C: "#6fe3a8",
  B: "#ff9b9b",
};

export function MotionTrackChart({
  positions,
}: {
  positions: { A: EpochPosition; C: EpochPosition; B: EpochPosition };
}) {
  const epochs = (["A", "C", "B"] as const).map((epoch) => ({
    epoch,
    ra: positions[epoch].ra_deg,
    dec: positions[epoch].dec_deg,
  }));

  const valid = epochs.filter(
    (e): e is { epoch: "A" | "C" | "B"; ra: number; dec: number } =>
      e.ra !== null && e.dec !== null
  );

  if (valid.length < 2) {
    return (
      <p className="section-note">
        Not enough real positions available to plot a motion track (need at
        least 2 of the 3 epochs).
      </p>
    );
  }

  // Sky-plane offsets in arcsec relative to the first valid epoch,
  // RA scaled by cos(dec) so the plot is angle-true (same method used in
  // validate_candidates.py's top_candidate_tracks.png).
  const ra0 = valid[0].ra;
  const dec0 = valid[0].dec;
  const cosd = Math.cos((dec0 * Math.PI) / 180);

  const points = valid.map((e) => ({
    epoch: e.epoch,
    x: (e.ra - ra0) * cosd * 3600,
    y: (e.dec - dec0) * 3600,
  }));

  const xs = points.map((p) => p.x);
  const ys = points.map((p) => p.y);
  const extent = Math.max(
    1,
    Math.max(...xs) - Math.min(...xs),
    Math.max(...ys) - Math.min(...ys)
  );
  const pad = extent * 0.25;
  const half = extent / 2 + pad;
  const cx = (Math.max(...xs) + Math.min(...xs)) / 2;
  const cy = (Math.max(...ys) + Math.min(...ys)) / 2;

  const plotSize = Math.min(WIDTH, HEIGHT) - MARGIN * 2;
  const scale = plotSize / (half * 2);

  // screen space: x right, y DOWN — dec increases up, so flip y
  const sx = (x: number) => WIDTH / 2 + (x - cx) * scale;
  const sy = (y: number) => HEIGHT / 2 - (y - cy) * scale;

  const missing = epochs.filter((e) => e.ra === null || e.dec === null);

  return (
    <div className="motion-track">
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        className="motion-track-svg"
        role="img"
        aria-label="Sky-plane motion track across epochs"
      >
        <line x1={WIDTH / 2} x2={WIDTH / 2} y1={0} y2={HEIGHT} className="spectrum-grid" />
        <line x1={0} x2={WIDTH} y1={HEIGHT / 2} y2={HEIGHT / 2} className="spectrum-grid" />

        {points.slice(1).map((p, i) => {
          const prev = points[i];
          return (
            <line
              key={`seg-${p.epoch}`}
              x1={sx(prev.x)}
              y1={sy(prev.y)}
              x2={sx(p.x)}
              y2={sy(p.y)}
              className="motion-track-line"
              markerEnd="url(#track-arrow)"
            />
          );
        })}

        <defs>
          <marker
            id="track-arrow"
            markerWidth="8"
            markerHeight="8"
            refX="6"
            refY="3"
            orient="auto"
          >
            <path d="M0,0 L6,3 L0,6 Z" className="motion-track-arrowhead" />
          </marker>
        </defs>

        {points.map((p) => (
          <g key={p.epoch}>
            <circle
              cx={sx(p.x)}
              cy={sy(p.y)}
              r={6}
              fill={EPOCH_COLORS[p.epoch]}
              stroke="#06121c"
              strokeWidth={1.5}
            />
            <text
              x={sx(p.x)}
              y={sy(p.y) - 12}
              textAnchor="middle"
              className="motion-track-label"
              fill={EPOCH_COLORS[p.epoch]}
            >
              {p.epoch}
            </text>
          </g>
        ))}
      </svg>

      <p className="section-note">
        Sky-plane track (arcsec offset, angle-true) through the epochs with
        a real position: A (blue) → C (green) → B (red).
        {missing.length > 0 &&
          ` No real position for epoch ${missing
            .map((m) => m.epoch)
            .join(", ")}; not shown.`}
      </p>
    </div>
  );
}
