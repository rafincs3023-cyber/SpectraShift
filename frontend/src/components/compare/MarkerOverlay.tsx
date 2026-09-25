import { useNavigate } from "react-router-dom";
import type { CandidateMarker } from "../../api/types";
import { markerClass, markerLabel } from "./markerUtils";

export function MarkerOverlay({ markers }: { markers: CandidateMarker[] }) {
  const navigate = useNavigate();

  return (
    <div className="marker-layer" aria-hidden={markers.length === 0}>
      {markers.map((m) => (
        <button
          key={m.candidate_id}
          type="button"
          className={markerClass(m)}
          style={{
            left: `${m.x_frac * 100}%`,
            top: `${m.y_frac * 100}%`,
          }}
          title={`${m.candidate_id}${m.detected_here === false ? " (not seen in this image)" : ""} — open details`}
          onClick={(e) => {
            e.stopPropagation();
            navigate(`/candidates/${encodeURIComponent(m.candidate_id)}`);
          }}
        >
          <span className="marker-label">{markerLabel(m.candidate_id)}</span>
        </button>
      ))}
    </div>
  );
}
