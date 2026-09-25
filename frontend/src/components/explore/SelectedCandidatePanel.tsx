import { Link } from "react-router-dom";
import type { TwoEpochCandidate } from "../../api/types";
import { InfoTooltip } from "../ui/InfoTooltip";
import {
  KIND_EXPLANATION,
  displacementText,
  fmt,
  rateText,
  shortDate,
} from "../candidate/candidateFormat";

/** Summary of the marker selected in Explore. */
export function SelectedCandidatePanel({
  candidate,
}: {
  candidate: TwoEpochCandidate | null;
}) {
  if (!candidate) {
    return (
      <aside className="card selected-source-panel">
        <h2>Selected candidate</h2>
        <p className="section-note">Click a marker on the image to see its details here.</p>
      </aside>
    );
  }
  const c = candidate;
  return (
    <aside className="card selected-source-panel">
      <h2>{c.candidate_id}</h2>
      <p className="section-note">
        <strong>{c.kind_label}.</strong> {KIND_EXPLANATION[c.kind]}
      </p>
      <p className="callout-warning">A preliminary candidate — not a confirmed moving object or discovery.</p>

      <dl className="kv-list kv-list-compact">
        <div>
          <dt>Earlier image ({shortDate(c.earlier_date)})</dt>
          <dd>
            {c.earlier
              ? `RA ${fmt(c.earlier.ra, 4)}° · Dec ${fmt(c.earlier.dec, 4)}°`
              : "not found"}
          </dd>
        </div>
        <div>
          <dt>Later image ({shortDate(c.later_date)})</dt>
          <dd>
            {c.later ? `RA ${fmt(c.later.ra, 4)}° · Dec ${fmt(c.later.dec, 4)}°` : "not found"}
          </dd>
        </div>
        <div>
          <dt>
            Position change
            <InfoTooltip term="displacement" />
          </dt>
          <dd>{displacementText(c)}</dd>
        </div>
        <div>
          <dt>
            Apparent motion
            <InfoTooltip term="apparentMotion" />
          </dt>
          <dd>{rateText(c)}</dd>
        </div>
      </dl>

      <Link to={`/candidates/${encodeURIComponent(c.candidate_id)}`} className="btn btn-secondary">
        Open full details
      </Link>
    </aside>
  );
}
