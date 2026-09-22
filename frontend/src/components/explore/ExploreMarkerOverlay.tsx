import type { CandidateMarker } from "../../api/types";

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
              ? "marker-dot marker-dot-selected"
              : "marker-dot"
          }
          style={{ left: `${m.x_frac * 100}%`, top: `${m.y_frac * 100}%` }}
          title={`${m.candidate_id} — select`}
          onClick={(e) => {
            e.stopPropagation();
            onSelect(m.candidate_id);
          }}
        >
          <span className="marker-label">
            {m.candidate_id.replace("3EPOCH-", "#")}
          </span>
        </button>
      ))}
    </div>
  );
}
