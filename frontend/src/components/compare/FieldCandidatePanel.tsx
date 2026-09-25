import { Link } from "react-router-dom";
import type { TwoEpochCandidate } from "../../api/types";
import { displacementText } from "../candidate/candidateFormat";
import { markerLabel } from "./markerUtils";

/** Two-epoch candidates marked on the images, with links to their details. */
export function FieldCandidatePanel({
  candidates,
  error,
}: {
  candidates: TwoEpochCandidate[] | null;
  error?: string | null;
}) {
  return (
    <aside className="card field-panel">
      <h2>Candidates in this view</h2>
      {error && <p className="section-note">Candidate markers are unavailable right now.</p>}
      {!error && candidates && (
        <p className="section-note">
          {candidates.length === 0
            ? "No current two-epoch candidates appear in this view."
            : `${candidates.length} preliminary two-epoch candidate${
                candidates.length === 1 ? "" : "s"
              } marked. None is a confirmed moving object.`}
        </p>
      )}

      {candidates && candidates.length > 0 && (
        <div className="field-candidate-list">
          {candidates.map((c) => (
            <Link
              key={c.candidate_id}
              to={`/candidates/${encodeURIComponent(c.candidate_id)}`}
              className="field-candidate-card"
            >
              <div className="field-candidate-card-top">
                <span className="candidate-link">
                  {markerLabel(c.candidate_id)} · {c.candidate_id}
                </span>
              </div>
              <dl className="kv-list kv-list-compact">
                <div>
                  <dt>Type</dt>
                  <dd>{c.kind_label}</dd>
                </div>
                <div>
                  <dt>Position change</dt>
                  <dd>{displacementText(c)}</dd>
                </div>
              </dl>
            </Link>
          ))}
        </div>
      )}
      <p className="section-note">
        Solid ring: seen in this image. Dashed ring: seen only in the other
        image.
      </p>
    </aside>
  );
}
