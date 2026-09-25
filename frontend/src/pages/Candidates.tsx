import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { CandidateKind, CandidatesResponse } from "../api/types";
import { LoadingState } from "../components/LoadingState";
import { ErrorState } from "../components/ErrorState";
import { PageIntro } from "../components/ui/PageIntro";
import { InfoTooltip } from "../components/ui/InfoTooltip";
import { TechnicalDetails } from "../components/ui/TechnicalDetails";
import { EmptyStateCard } from "../components/ui/EmptyStateCard";
import {
  KIND_EXPLANATION,
  bestSnr,
  displacementText,
  fmt,
  longDate,
  rateText,
} from "../components/candidate/candidateFormat";

const KIND_ORDER: CandidateKind[] = [
  "possible_position_change",
  "shifted_match",
  "seen_only_earlier",
  "seen_only_later",
];

export function Candidates() {
  const [data, setData] = useState<CandidatesResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  function load() {
    setLoading(true);
    setError(null);
    api
      .getCandidates()
      .then(setData)
      .catch((err: unknown) =>
        setError(err instanceof ApiError ? err.message : "Unexpected error")
      )
      .finally(() => setLoading(false));
  }

  useEffect(load, []);

  return (
    <div className="page">
      <PageIntro
        eyebrow="Two-epoch candidates · Jun 19 → Dec 17, 2025"
        title="Possible moving-source candidates"
        lead="SpectraShift compares the June 19 and December 17, 2025 observations and highlights sources whose positions or appearances changed enough to deserve further inspection."
        what="Finds every star-like source in both images, pairs up the ones that stay put, and keeps only changes that pass a series of quality checks."
        how="Read the result below, then open a candidate to see its pictures and numbers."
        result="Each candidate is a possibility for follow-up, not a measured orbit or a discovery."
      />

      <p className="callout-warning candidates-disclaimer">
        These are preliminary two-epoch candidates, not confirmed moving
        objects or discoveries.
      </p>

      {loading && <LoadingState label="Loading the candidate results…" />}

      {!loading && error && <ErrorState message={error} onRetry={load} />}

      {!loading && !error && data && (
        <>
          <section className="count-grid candidates-counts" aria-label="Candidate counts">
            <div className="count-tile">
              <strong>{data.count}</strong>
              <span>candidates passed the current checks</span>
            </div>
            {KIND_ORDER.map((k) => (
              <div className="count-tile" key={k}>
                <strong>{data.counts[k] ?? 0}</strong>
                <span>{data.kind_labels[k].toLowerCase()}</span>
              </div>
            ))}
          </section>
          <p className="section-note">
            Earlier observation {longDate(data.earlier_date)} · later observation{" "}
            {longDate(data.later_date)} · {data.time_baseline_days.toFixed(2)} days apart.
          </p>

          {data.count === 0 ? (
            <EmptyStateCard
              tone="result"
              title="No reliable two-epoch candidate passed the current checks in this field."
              actions={
                <Link to="/compare" className="btn btn-secondary">
                  Compare the two images yourself
                </Link>
              }
            >
              <p>
                This does not prove that no moving source exists. It only
                means none passed the current detection and quality criteria.
              </p>
            </EmptyStateCard>
          ) : (
            <>
              {(data.counts.possible_position_change ?? 0) === 0 && (
                <EmptyStateCard tone="result" title="No source was seen to move to a clearly new place between the two dates.">
                  <p>
                    No source seen only in the earlier image could be paired
                    with a similar source seen only in the later image. The
                    candidates below are smaller or one-sided changes. This
                    does not prove that no moving source exists — only that
                    none passed the current checks.
                  </p>
                </EmptyStateCard>
              )}

              <div className="card candidates-table-card">
                <div className="table-scroll">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>ID</th>
                        <th>Type</th>
                        <th>
                          Position change
                          <InfoTooltip term="displacement" />
                        </th>
                        <th>
                          Apparent motion
                          <InfoTooltip term="apparentMotion" />
                        </th>
                        <th>
                          Signal strength
                          <InfoTooltip
                            label="What is signal strength?"
                            text="Signal-to-noise ratio (SNR): how far the source stands out above the image noise. Higher is more reliable; 5 is the detection limit here."
                          />
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.candidates.map((c) => (
                        <tr key={c.candidate_id}>
                          <td data-label="ID">
                            <Link
                              to={`/candidates/${encodeURIComponent(c.candidate_id)}`}
                              className="candidate-link"
                            >
                              {c.candidate_id}
                            </Link>
                          </td>
                          <td data-label="Type">{c.kind_label}</td>
                          <td data-label="Position change">{displacementText(c)}</td>
                          <td data-label="Apparent motion">{rateText(c)}</td>
                          <td data-label="Signal strength">{fmt(bestSnr(c), 0)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              <section className="card">
                <h2>What the types mean</h2>
                <dl className="kv-list">
                  {KIND_ORDER.map((k) => (
                    <div key={k}>
                      <dt>{data.kind_labels[k]}</dt>
                      <dd>{KIND_EXPLANATION[k]}</dd>
                    </div>
                  ))}
                </dl>
              </section>
            </>
          )}

          <section className="card">
            <h2>How the screening works</h2>
            <ol className="steps-list">
              <li>
                <strong>Find sources.</strong> Detect every star-like point in
                the earlier and in the later image, separately.
              </li>
              <li>
                <strong>Pair them up.</strong> A source found at the same place
                on both dates is a stationary source
                <InfoTooltip term="stationarySource" /> and is set aside.
              </li>
              <li>
                <strong>Check what is left.</strong> Reject anything near the
                image edge, on pixels SPHEREx flagged as unreliable, in the
                glare of a bright star, blended
                <InfoTooltip term="blend" /> with a neighbour, or not shaped
                like a star — and confirm that the change also shows in the
                difference image.
              </li>
              <li>
                <strong>List the survivors</strong> as candidates for
                inspection.
              </li>
            </ol>
            <p className="section-note">
              Two observations cannot establish a trajectory or an orbit, so a
              candidate is only a possibility for follow-up.
            </p>

            <TechnicalDetails summary="Details: detections, rejections and thresholds">
              <div className="count-grid">
                <div className="count-tile">
                  <strong>{data.measured.detections.A.toLocaleString("en-US")}</strong>
                  <span>sources in the earlier image</span>
                </div>
                <div className="count-tile">
                  <strong>{data.measured.detections.B.toLocaleString("en-US")}</strong>
                  <span>sources in the later image</span>
                </div>
                <div className="count-tile">
                  <strong>{data.measured.matched_in_both.toLocaleString("en-US")}</strong>
                  <span>found in both</span>
                </div>
              </div>

              <h3 className="evidence-subheading">Rejected, by first failed check</h3>
              <div className="table-scroll">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Check</th>
                      <th>Rejected</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(data.rejected_by_reason).map(([reason, n]) => (
                      <tr key={reason}>
                        <td data-label="Check">{data.rejection_reasons[reason] ?? reason}</td>
                        <td data-label="Rejected">{n.toLocaleString("en-US")}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <h3 className="evidence-subheading">Measured from the images</h3>
              <dl className="kv-list">
                <div>
                  <dt>Image sharpness (FWHM)</dt>
                  <dd>
                    {fmt(data.measured.fwhm_arcsec.A, 1)}″ earlier, {fmt(data.measured.fwhm_arcsec.B, 1)}″
                    later; the sharper image is blurred to{" "}
                    {fmt(data.measured.psf_matched_fwhm_arcsec, 1)}″ so both are compared alike
                  </dd>
                </div>
                <div>
                  <dt>Alignment</dt>
                  <dd>
                    residual offset ({fmt(data.measured.alignment_residual_shift_arcsec[0], 2)}″,{" "}
                    {fmt(data.measured.alignment_residual_shift_arcsec[1], 2)}″) from{" "}
                    {data.measured.bright_stars_used_for_alignment.toLocaleString("en-US")} bright stars
                  </dd>
                </div>
                <div>
                  <dt>Position error model</dt>
                  <dd>
                    {data.measured.position_error_model.formula}, with floor{" "}
                    {fmt(data.measured.position_error_model.sigma_floor_arcsec, 2)}″ and k ={" "}
                    {fmt(data.measured.position_error_model.k_arcsec, 2)}″ (fitted to the stationary
                    sources)
                  </dd>
                </div>
                <div>
                  <dt>Beyond the stationary tolerance</dt>
                  <dd>
                    {data.measured.matched_beyond_stationary_tolerance} matched sources, where a
                    purely Gaussian error would give{" "}
                    {fmt(data.measured.gaussian_expectation_beyond_tolerance, 2)}. The real errors
                    have longer tails (blends, pixel sampling), which is why small shifts are
                    treated with caution.
                  </dd>
                </div>
                {Object.entries(data.thresholds).map(([k, v]) => (
                  <div key={k}>
                    <dt>{k.replace(/_/g, " ")}</dt>
                    <dd>{String(v)}</dd>
                  </div>
                ))}
              </dl>

              <h3 className="evidence-subheading">Limitations</h3>
              <ul className="plain-list">
                {data.limitations.map((l) => (
                  <li key={l}>{l}</li>
                ))}
                {data.flag_notes.map((l) => (
                  <li key={l}>{l}</li>
                ))}
              </ul>
              <p className="notes-text">
                Inputs: <code>{data.inputs.earlier.file}</code> ({data.inputs.earlier.date}) and{" "}
                <code>{data.inputs.later.file}</code> ({data.inputs.later.date}), compared on the
                shared grid of <code>{data.inputs.earlier.grid_file}</code> /{" "}
                <code>{data.inputs.later.grid_file}</code>. Pipeline {data.pipeline}.
              </p>
            </TechnicalDetails>
          </section>
        </>
      )}
    </div>
  );
}
