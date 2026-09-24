import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { CandidateSummary, LinkingSummary } from "../api/types";
import { LoadingState } from "../components/LoadingState";
import { ErrorState } from "../components/ErrorState";
import { StatusBadge } from "../components/StatusBadge";
import { STATUS_HELP } from "../components/statusHelp";

function fmt(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "—";
  }
  return value.toFixed(digits);
}

export function Candidates() {
  const [candidates, setCandidates] = useState<CandidateSummary[] | null>(
    null
  );
  const [linking, setLinking] = useState<LinkingSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  function load() {
    setLoading(true);
    setError(null);
    // the linking summary is supporting context only; its absence never
    // blocks the candidate list
    api.getLinkingSummary().then(setLinking).catch(() => setLinking(null));
    api
      .getCandidates()
      .then((res) => setCandidates(res.candidates))
      .catch((err: unknown) =>
        setError(err instanceof ApiError ? err.message : "Unexpected error")
      )
      .finally(() => setLoading(false));
  }

  useEffect(load, []);

  return (
    <div className="page">
      <div className="page-header">
        <h1>Three-Epoch Motion Candidates</h1>
        <p className="page-subtitle">
          Results from the SPHEREx three-epoch (A → C → B) motion-candidate
          pipeline. Only tracks that pass the current motion and
          stationary-source validation filters appear here. Live data from{" "}
          <code>GET /api/candidates</code>.
        </p>
      </div>

      {loading && <LoadingState label="Loading candidates from the API…" />}

      {!loading && error && <ErrorState message={error} onRetry={load} />}

      {!loading && !error && candidates && (
        <>
          <p className="result-count">
            {candidates.length} candidate{candidates.length === 1 ? "" : "s"}{" "}
            loaded
          </p>

          {linking && (
            <p className="section-note linking-summary">
              Latest linker run: {linking.accepted_tracks + linking.rejected_tracks}{" "}
              A → C → B tracks formed, {linking.accepted_tracks} accepted,{" "}
              {linking.rejected_tracks} rejected by the stationary-source veto (
              {linking.rejected_by_reason.STATIONARY_SOURCE} stationary source,{" "}
              {linking.rejected_by_reason.BLEND_MISLINK} blend / mislink,{" "}
              {linking.rejected_by_reason.INCONSISTENT_TRAJECTORY} inconsistent
              trajectory).
            </p>
          )}

          {candidates.length === 0 ? (
            <div className="state-panel state-placeholder">
              <p>
                No three-epoch motion candidate survived the current pipeline.
              </p>
              <p className="section-note">
                Every track linked across Epochs A → C → B was traced to
                sources that stay at the same sky position in the other
                epochs, or to blends and bright-star halos around them — that
                is, apparent motion created by linking unrelated stationary
                sources, not a moving object.
                {linking?.genuine_mover_veto_probability != null &&
                  ` A genuinely moving source would be vetoed with probability ≈${Math.round(
                    linking.genuine_mover_veto_probability * 100
                  )}% (measured on random sky positions), so the veto does not
                  explain the absence of candidates on its own.`}{" "}
                Rejected tracks and their reasons are listed in{" "}
                <code>{linking?.rejected_tracks_file ?? "rejected_three_epoch_tracks.csv"}</code>.
              </p>
            </div>
          ) : (
          <>
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Rank</th>
                  <th>Candidate ID</th>
                  <th>Validation Score</th>
                  <th>Total Motion (″)</th>
                  <th>Motion Rate (″/day)</th>
                  <th>
                    Catalogue Status{" "}
                    <span
                      className="info-hint"
                      title={[
                        `Known Object: ${STATUS_HELP.KNOWN_OBJECT}`,
                        `Unmatched After Checks: ${STATUS_HELP.UNMATCHED_AFTER_CHECKS}`,
                        `Uncertain: ${STATUS_HELP.UNCERTAIN}`,
                      ].join("\n\n")}
                      aria-label="What the catalogue statuses mean"
                    >
                      ⓘ
                    </span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {candidates.map((c) => (
                  <tr key={c.candidate_id}>
                    <td data-label="Rank">{c.final_rank ?? c.rank ?? "—"}</td>
                    <td data-label="Candidate ID">
                      <Link
                        to={`/candidates/${encodeURIComponent(
                          c.candidate_id
                        )}`}
                        className="candidate-link"
                      >
                        {c.candidate_id}
                      </Link>
                    </td>
                    <td data-label="Validation Score">
                      {fmt(c.validation_score, 1)}
                    </td>
                    <td data-label="Total Motion (arcsec)">
                      {fmt(c.total_motion_arcsec, 1)}
                    </td>
                    <td data-label="Motion Rate (arcsec/day)">
                      {fmt(c.motion_arcsec_per_day, 2)}
                    </td>
                    <td data-label="Catalogue Status">
                      <StatusBadge
                        status={c.final_catalogue_status}
                        reason={c.status_reason}
                      />
                      {c.match_confidence && c.match_confidence !== "NONE" && (
                        <span className="confidence-note">
                          {c.match_confidence.toLowerCase()} confidence
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <dl className="status-legend">
            <div>
              <dt>Known Object</dt>
              <dd>{STATUS_HELP.KNOWN_OBJECT}</dd>
            </div>
            <div>
              <dt>Unmatched After Checks</dt>
              <dd>{STATUS_HELP.UNMATCHED_AFTER_CHECKS}</dd>
            </div>
            <div>
              <dt>Uncertain</dt>
              <dd>{STATUS_HELP.UNCERTAIN}</dd>
            </div>
          </dl>
          <p className="section-note">
            Hover a status for the candidate-specific reason; the candidate
            page lists the per-epoch catalogue evidence.
          </p>
          </>
          )}
        </>
      )}
    </div>
  );
}
