import type { CandidateMarker, ComparePairSide } from "../../api/types";
import { imageUrl } from "../../api/client";
import { MarkerOverlay } from "./MarkerOverlay";

function fmt(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return value.toFixed(digits);
}

export function ObservationPanel({
  side,
  markers,
  showMarkers = true,
}: {
  side: ComparePairSide;
  markers: CandidateMarker[];
  showMarkers?: boolean;
}) {
  const obs = side.observation;

  return (
    <div className="obs-panel">
      <div className="obs-panel-header">
        <span className="obs-epoch-chip">Epoch {side.epoch}</span>
        <span className="obs-panel-meta">
          {obs?.date_obs?.slice(0, 10) ?? "—"} · MJD {fmt(obs?.mjd_obs, 3)}
        </span>
      </div>
      <div className="obs-image-frame">
        <img
          src={imageUrl(side.preview_url)}
          alt={`SPHEREx sky image, Epoch ${side.epoch}`}
          className="obs-image"
          draggable={false}
          crossOrigin="anonymous"
        />
        {showMarkers && <MarkerOverlay markers={markers} />}
      </div>
      <div className="obs-panel-footer">
        <span>Detector {obs?.detector ?? "—"}</span>
        <span>
          RA {fmt(obs?.ra_center_deg, 3)}° · Dec {fmt(obs?.dec_center_deg, 3)}°
        </span>
      </div>
    </div>
  );
}
