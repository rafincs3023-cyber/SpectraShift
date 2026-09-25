import type { CandidateMarker, CompareImageSide } from "../../api/types";
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
  coordLabel,
}: {
  side: CompareImageSide;
  markers: CandidateMarker[];
  showMarkers?: boolean;
  /** Names what the footer RA/Dec is, e.g. "Frame center". */
  coordLabel?: string;
}) {
  const obs = side.observation;
  const label = side.label ?? (side.epoch === "A" ? "Earlier image" : "Later image");

  return (
    <div className="obs-panel">
      <div className="obs-panel-header">
        <span className="obs-epoch-chip">{label}</span>
        <span className="obs-panel-meta">
          {obs?.date_obs?.slice(0, 10) ?? "—"} · MJD {fmt(obs?.mjd_obs, 3)}
        </span>
      </div>
      <div className="obs-image-frame">
        <img
          src={imageUrl(side.preview_url)}
          alt={`SPHEREx sky image, ${label}`}
          className="obs-image"
          draggable={false}
          crossOrigin="anonymous"
        />
        {showMarkers && <MarkerOverlay markers={markers} />}
      </div>
      <div className="obs-panel-footer">
        <span>Detector {obs?.detector ?? "—"}</span>
        <span>
          {coordLabel && `${coordLabel}: `}RA {fmt(obs?.ra_center_deg, 3)}° · Dec {fmt(obs?.dec_center_deg, 3)}°
        </span>
      </div>
    </div>
  );
}
