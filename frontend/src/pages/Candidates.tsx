import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { CandidateSummary, LinkingSummary } from "../api/types";
import { LoadingState } from "../components/LoadingState";
import { ErrorState } from "../components/ErrorState";
import { StatusBadge } from "../components/StatusBadge";
import { STATUS_HELP } from "../components/statusHelp";
import { PageIntro } from "../components/ui/PageIntro";
import { InfoTooltip } from "../components/ui/InfoTooltip";
import { TechnicalDetails } from "../components/ui/TechnicalDetails";
import { EmptyStateCard } from "../components/ui/EmptyStateCard";

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

  const tracksChecked = linking ? linking.accepted_tracks + linking.rejected_tracks : null;

  return (
    <div className="page">
      <PageIntro
        eyebrow="Search for moving objects"
        title="Possible Moving Objects"
        lead="The result of our search for objects that move across the sky between three SPHEREx observations."
        what="Compares three images of the same sky taken within one month (May 9 – Jun 9, 2025) and looks for anything that shifts position steadily."
        how="Read the result below. Open the details if you want the numbers behind it."
        result="Anything listed here would be a possible moving object that passed every check — never a confirmed discovery."
      />

      {loading && <LoadingState label="Loading the search results…" />}

      {!loading && error && <ErrorState message={error} onRetry={load} />}

      {!loading && !error && candidates && (
        <>
          {candidates.length === 0 ? (
            <EmptyStateCard
              tone="result"
              title="No reliable moving-object candidate was found in this dataset."
              actions={
                <>
                  <Link to="/compare" className="btn btn-secondary">
                    Compare the images yourself
                  </Link>
                  <Link to="/help" className="btn btn-secondary">
                    What does this mean?
                  </Link>
                </>
              }
            >
              <p>
                The system checked{" "}
                {tracksChecked !== null ? `${tracksChecked.toLocaleString("en-US")} possible tracks` : "many possible tracks"}{" "}
                and rejected every one. They turned out to be stationary stars,
                blended sources or mismatched detections — not objects moving
                across the sky.
              </p>
              <p>
                This is an honest result, not an error. It also does not prove
                that nothing moves in this part of the sky: faint objects, or
                objects in crowded parts of the image, can be missed.
              </p>
            </EmptyStateCard>
          ) : (
            <EmptyStateCard
              tone="result"
              title={`${candidates.length} possible moving object${candidates.length === 1 ? "" : "s"} passed every check.`}
            >
              <p>
                Each one is only a candidate. Open an ID to see its positions,
                motion and catalogue check.
              </p>
            </EmptyStateCard>
          )}

          {candidates.length > 0 && (
            <div className="card candidates-table-card">
              <div className="table-scroll">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Rank</th>
                      <th>ID</th>
                      <th>Validation score</th>
                      <th>Total motion (″)</th>
                      <th>Motion per day (″)</th>
                      <th>
                        Catalogue check
                        <InfoTooltip
                          label="What the catalogue check means"
                          text={`Known object: matched to a catalogued star, galaxy or Solar System body. Unmatched after checks: no match, which does not mean new. Uncertain: not enough evidence either way.`}
                        />
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {candidates.map((c) => (
                      <tr key={c.candidate_id}>
                        <td data-label="Rank">{c.final_rank ?? c.rank ?? "—"}</td>
                        <td data-label="ID">
                          <Link
                            to={`/candidates/${encodeURIComponent(c.candidate_id)}`}
                            className="candidate-link"
                          >
                            {c.candidate_id}
                          </Link>
                        </td>
                        <td data-label="Validation score">{fmt(c.validation_score, 1)}</td>
                        <td data-label="Total motion (arcsec)">{fmt(c.total_motion_arcsec, 1)}</td>
                        <td data-label="Motion per day (arcsec)">{fmt(c.motion_arcsec_per_day, 2)}</td>
                        <td data-label="Catalogue check">
                          <StatusBadge status={c.final_catalogue_status} reason={c.status_reason} />
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
              <p className="section-note">
                Hover a status to see the reason for that candidate.
              </p>
            </div>
          )}

          <section className="card">
            <h2>How the search works</h2>
            <ol className="steps-list">
              <li>
                <strong>Find sources.</strong> Detect every star-like point in
                each of the three images.
              </li>
              <li>
                <strong>Link them.</strong> Connect points that could be one
                object moving in a straight line from date to date.
              </li>
              <li>
                <strong>Reject look-alikes.</strong> Remove tracks built from
                stationary sources
                <InfoTooltip term="stationarySource" /> (the same star found at
                the same place on another date), blends
                <InfoTooltip term="blend" /> and bright-star glare.
              </li>
              <li>
                <strong>Check catalogues.</strong> Compare anything left with
                known stars, galaxies, asteroids and comets.
              </li>
            </ol>

            <TechnicalDetails summary="Details: tracks checked and why they were rejected">
              {linking ? (
                <>
                  <div className="count-grid">
                    <div className="count-tile">
                      <strong>{tracksChecked?.toLocaleString("en-US")}</strong>
                      <span>possible tracks formed</span>
                    </div>
                    <div className="count-tile">
                      <strong>{linking.accepted_tracks}</strong>
                      <span>kept as candidates</span>
                    </div>
                    <div className="count-tile">
                      <strong>{linking.rejected_by_reason.STATIONARY_SOURCE}</strong>
                      <span>stationary source</span>
                    </div>
                    <div className="count-tile">
                      <strong>{linking.rejected_by_reason.BLEND_MISLINK}</strong>
                      <span>blend / mislink</span>
                    </div>
                    <div className="count-tile">
                      <strong>{linking.rejected_by_reason.INCONSISTENT_TRAJECTORY}</strong>
                      <span>inconsistent path</span>
                    </div>
                  </div>
                  <p>
                    Rejection reasons: <em>stationary source</em> — the track's
                    detections are the same source at the same sky position on
                    other dates; <em>blend / mislink</em> — the track is built
                    around persistent sources or bright-star halos;{" "}
                    <em>inconsistent path</em> — the middle detection does not
                    lie on a steady straight-line path.
                  </p>
                  {linking.genuine_mover_veto_probability != null && (
                    <p>
                      Measured on random sky positions, these checks would
                      reject a genuinely moving object only about{" "}
                      {Math.round(linking.genuine_mover_veto_probability * 100)}% of the time, so they do
                      not explain the empty result on their own.
                    </p>
                  )}
                  <p>
                    Every rejected track and its reason is listed in{" "}
                    <code>{linking.rejected_tracks_file ?? "rejected_three_epoch_tracks.csv"}</code>.
                  </p>
                </>
              ) : (
                <p>The detailed search statistics are not available right now.</p>
              )}
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
            </TechnicalDetails>
          </section>
        </>
      )}
    </div>
  );
}
