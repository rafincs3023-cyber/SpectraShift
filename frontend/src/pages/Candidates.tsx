import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { CandidateSummary } from "../api/types";
import { LoadingState } from "../components/LoadingState";
import { ErrorState } from "../components/ErrorState";
import { StatusBadge } from "../components/StatusBadge";

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
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  function load() {
    setLoading(true);
    setError(null);
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
          Validated candidates from the SPHEREx three-epoch (A → C → B)
          motion pipeline, ranked by scientific priority score. Live data
          from <code>GET /api/candidates</code>.
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

          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Rank</th>
                  <th>Candidate ID</th>
                  <th>Validation Score</th>
                  <th>Total Motion (″)</th>
                  <th>Motion Rate (″/day)</th>
                  <th>Catalogue Status</th>
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
                      <StatusBadge status={c.final_catalogue_status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
