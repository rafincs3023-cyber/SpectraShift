import type { CandidateMarker } from "../../api/types";
import { markerClass, markerLabel } from "../compare/markerUtils";

export function ExploreMarkerOverlay({
  markers,
  selectedId,
  onSelect,
}: {
  markers: CandidateMarker[];
  selectedId: string | null;
  onSelect: (candidateId: string) => void;
}) {
  return (
    <div className="marker-layer">
      {markers.map((m) => (
        <button
          key={m.candidate_id}
          type="button"
          className={
            m.candidate_id === selectedId
              ? `${markerClass(m)} marker-dot-selected`
              : markerClass(m)
          }
          style={{ left: `${m.x_frac * 100}%`, top: `${m.y_frac * 100}%` }}
          title={`${m.candidate_id}${m.detected_here === false ? " (not seen in this image)" : ""} — select`}
          onClick={(e) => {
            e.stopPropagation();
            onSelect(m.candidate_id);
          }}
        >
          <span className="marker-label">{markerLabel(m.candidate_id)}</span>
        </button>
      ))}
    </div>
  );
}
