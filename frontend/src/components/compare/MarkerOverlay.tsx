import { useNavigate } from "react-router-dom";
import type { CandidateMarker } from "../../api/types";

export function MarkerOverlay({
  markers,
  colorClass = "marker-dot",
}: {
  markers: CandidateMarker[];
  colorClass?: string;
}) {
  const navigate = useNavigate();

  return (
    <div className="marker-layer" aria-hidden={markers.length === 0}>
      {markers.map((m) => (
        <button
          key={m.candidate_id}
          type="button"
          className={colorClass}
          style={{
            left: `${m.x_frac * 100}%`,
            top: `${m.y_frac * 100}%`,
          }}
          title={`${m.candidate_id} — open detail`}
          onClick={(e) => {
            e.stopPropagation();
            navigate(`/candidates/${encodeURIComponent(m.candidate_id)}`);
          }}
        >
          <span className="marker-label">{m.candidate_id.replace("3EPOCH-", "#")}</span>
        </button>
      ))}
    </div>
  );
}
