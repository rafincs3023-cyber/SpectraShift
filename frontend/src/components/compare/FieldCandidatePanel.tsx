import { Link } from "react-router-dom";
import type { CandidateSummary } from "../../api/types";
import { StatusBadge } from "../StatusBadge";

function fmt(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return value.toFixed(digits);
}

export function FieldCandidatePanel({
  candidates,
}: {
  candidates: CandidateSummary[];
}) {
  return (
    <aside className="field-panel">
      <h2>Candidates in this field</h2>
      <p className="section-note">
        {candidates.length === 0
          ? "No validated candidate positions fall within the currently compared epochs."
          : `${candidates.length} candidate${
              candidates.length === 1 ? "" : "s"
            } visible in the selected epochs.`}
      </p>

      <div className="field-candidate-list">
        {candidates.map((c) => (
          <Link
            key={c.candidate_id}
            to={`/candidates/${encodeURIComponent(c.candidate_id)}`}
            className="field-candidate-card"
          >
            <div className="field-candidate-card-top">
              <span className="candidate-link">{c.candidate_id}</span>
              <StatusBadge status={c.final_catalogue_status} />
            </div>
            <dl className="kv-list kv-list-compact">
              <div>
                <dt>Rank</dt>
                <dd>{c.final_rank ?? c.rank ?? "—"}</dd>
              </div>
              <div>
                <dt>Apparent motion</dt>
                <dd>{fmt(c.total_motion_arcsec, 1)}″</dd>
              </div>
              <div>
                <dt>Validation score</dt>
                <dd>{fmt(c.validation_score, 1)}</dd>
              </div>
            </dl>
          </Link>
        ))}
      </div>
    </aside>
  );
}
