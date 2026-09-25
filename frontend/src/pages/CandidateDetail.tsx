import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type {
  CandidateDetail as CandidateDetailType,
  CandidateSpectrumResponse,
  CatalogueExplanation,
  CrossmatchResponse,
} from "../api/types";
import { LoadingState } from "../components/LoadingState";
import { ErrorState } from "../components/ErrorState";
import { StatusBadge } from "../components/StatusBadge";
import { SpectrumChart } from "../components/explore/SpectrumChart";
import { CandidateCutouts } from "../components/candidate/CandidateCutouts";
import { MotionTrackChart } from "../components/candidate/MotionTrackChart";
import { LightCurveChart } from "../components/candidate/LightCurveChart";
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

/** Catalogue proper motions are ~1e-5 ″/day, so switch to exponent form. */
function fmtRate(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return value !== 0 && Math.abs(value) < 0.01
    ? value.toExponential(1)
    : value.toFixed(2);
}

function shortDate(iso: string): string {
  const d = new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : `${iso}Z`);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" });
}

const EXPLANATION_LABELS: Record<CatalogueExplanation, string> = {
  KNOWN_SOLAR_SYSTEM_OBJECT: "Known Solar System small body (ephemeris from SPHEREx)",
  STATIC_KNOWN_STAR: "Same catalogued star at several epochs (not moving)",
  LINKED_KNOWN_STARS:
    "Each epoch is a different catalogued star (apparent motion from linking unrelated stars)",
  HIGH_PM_STAR_CANDIDATE: "Possible high-proper-motion star (manual review)",
  NO_ASSOCIATION: "No consistent catalogue association",
  INSUFFICIENT_OR_AMBIGUOUS: "Partial, ambiguous or inconsistent catalogue evidence",
};

const MATCH_STATUS_LABELS: Record<string, string> = {
  MATCH: "Match",
  NO_MATCH: "No match",
  SERVICE_UNAVAILABLE: "Service unavailable",
};

export function CandidateDetail() {
  const { id } = useParams<{ id: string }>();

  const [detail, setDetail] = useState<CandidateDetailType | null>(null);
  const [crossmatch, setCrossmatch] = useState<CrossmatchResponse | null>(
    null
  );
  const [spectrum, setSpectrum] = useState<CandidateSpectrumResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [loading, setLoading] = useState(true);
  const [epochDates, setEpochDates] = useState<Partial<Record<"A" | "C" | "B", string>>>({});

  // Observation dates only make labels friendlier ("May 9, 2025 (A)"); if
  // they fail to load the page falls back to plain epoch letters.
  useEffect(() => {
    api
      .getObservations()
      .then((res) =>
        setEpochDates(
          Object.fromEntries(
            res.observations.filter((o) => o.date_obs).map((o) => [o.epoch, o.date_obs as string])
          )
        )
      )
      .catch(() => {});
  }, []);

  function load(candidateId: string) {
    setLoading(true);
    setError(null);
    setNotFound(false);

    Promise.all([
      api.getCandidate(candidateId),
      api.getCatalogueCrossmatch(candidateId),
      api.getCandidateSpectrum(candidateId),
    ])
      .then(([detailRes, crossmatchRes, spectrumRes]) => {
        setDetail(detailRes);
        setCrossmatch(crossmatchRes);
        setSpectrum(spectrumRes);
      })
      .catch((err: unknown) => {
        if (err instanceof ApiError && err.status === 404) {
          setNotFound(true);
        } else {
          setError(err instanceof ApiError ? err.message : "Unexpected error");
        }
      })
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    if (id) load(id);
  }, [id]);

  if (!id) {
    return <ErrorState message="No candidate ID given in the URL." />;
  }

  const dateLabel = (epoch: "A" | "C" | "B") => {
    const iso = epochDates[epoch];
    return iso ? `${shortDate(iso)} (${epoch})` : `Epoch ${epoch}`;
  };
  const status = detail?.catalogue.final_catalogue_status ?? null;

  return (
    <div className="page">
      <Link to="/candidates" className="back-link">
        ← All search results
      </Link>
      <PageIntro
        eyebrow="Possible moving object"
        title={id}
        lead="Evidence for one track that seemed to move across three observation dates. It is a candidate for checking, not a confirmed discovery."
        what="Summarises how this source appeared to move, what the catalogue check found, and the pictures behind it."
        how="Start with the summary and pictures. Open the technical details for the full measurements."
        result="The catalogue check says whether the source matches something already known. “Unmatched” never means new or unknown."
      />
      <div className="inspect-links">
        <Link to={`/explore?candidate=${encodeURIComponent(id)}`} className="btn btn-secondary">
          Show it in Explore
        </Link>
        <Link to="/compare?dataset=31day" className="btn btn-secondary">
          Compare the three dates
        </Link>
      </div>

      {loading && <LoadingState label="Loading this candidate…" />}

      {!loading && notFound && (
        <EmptyStateCard
          title="This candidate is not in the current results."
          actions={
            <Link to="/candidates" className="btn btn-secondary">
              See the current results
            </Link>
          }
        >
          <p>
            There is no possible moving object with the ID “{id}”. The search
            may have been re-run with stricter checks, so older IDs can
            disappear.
          </p>
        </EmptyStateCard>
      )}

      {!loading && error && (
        <ErrorState message={error} onRetry={() => load(id)} />
      )}

      {!loading && !notFound && !error && detail && (
        <>
          <section className="card-grid">
            <div className="card">
              <h2>Catalogue check</h2>
              <div className="catalogue-status-row">
                <StatusBadge status={status} reason={detail.catalogue.status_reason} />
                {detail.catalogue.match_confidence &&
                  detail.catalogue.match_confidence !== "NONE" && (
                    <span className="confidence-note">
                      {detail.catalogue.match_confidence.toLowerCase()} confidence
                    </span>
                  )}
              </div>
              {status && <p className="section-note">{STATUS_HELP[status]}</p>}
              {detail.catalogue.status_reason && (
                <p className="notes-text status-reason">
                  <strong>Why:</strong> {detail.catalogue.status_reason}
                </p>
              )}
              {detail.catalogue.best_match_object && (
                <dl className="kv-list">
                  <div>
                    <dt>Matched to</dt>
                    <dd>{detail.catalogue.best_match_object}</dd>
                  </div>
                </dl>
              )}
            </div>

            <div className="card">
              <h2>How it moved</h2>
              <dl className="kv-list">
                <div>
                  <dt>Distance moved</dt>
                  <dd>
                    {fmt(detail.motion.total_motion_arcsec, 1)}″ from {dateLabel("A")} to {dateLabel("B")}
                  </dd>
                </div>
                <div>
                  <dt>Speed across the sky</dt>
                  <dd>{fmt(detail.motion.motion_arcsec_per_day, 2)}″ per day</dd>
                </div>
                <div>
                  <dt>Change of direction</dt>
                  <dd>{fmt(detail.motion.direction_diff_deg, 1)}°</dd>
                </div>
                <div>
                  <dt>Search ranking</dt>
                  <dd>#{detail.final_rank ?? detail.rank ?? "—"}</dd>
                </div>
              </dl>
              <p className="section-note">
                ″ = arcseconds; 3,600″ make one degree on the sky. A real moving
                object keeps a steady speed and direction.
              </p>
            </div>
          </section>

          <section className="card">
            <h2>Pictures</h2>
            <p className="section-note">
              Made directly from the real SPHEREx images and measurements —
              nothing here is simulated.
            </p>

            <h3 className="evidence-subheading">What it looks like on each date</h3>
            <CandidateCutouts candidateId={detail.candidate_id} />

            <div className="card-grid evidence-grid">
              <div>
                <h3 className="evidence-subheading">Its path across the sky</h3>
                <MotionTrackChart positions={detail.positions} />
              </div>
              <div>
                <h3 className="evidence-subheading">
                  Brightness at each wavelength sampled
                  <InfoTooltip
                    label="Why only a few wavelengths?"
                    text="On each date SPHEREx measured this spot at one wavelength only, so the chart has at most one point per date — it is not a full spectrum."
                  />
                </h3>
                {spectrum ? (
                  <SpectrumChart points={spectrum.points} />
                ) : (
                  <p className="section-note">Not available for this candidate.</p>
                )}
              </div>
            </div>

            <h3 className="evidence-subheading">Brightness over time</h3>
            {spectrum ? (
              <LightCurveChart points={spectrum.points} />
            ) : (
              <p className="section-note">Not available for this candidate.</p>
            )}
          </section>

          <section className="card">
            <h2>Technical details</h2>
            <p className="section-note">
              The full measurements behind the summary above.
            </p>

            <TechnicalDetails summary="Catalogue check details">
              <dl className="kv-list">
                {detail.catalogue.explanation && (
                  <div>
                    <dt>Classification basis</dt>
                    <dd>{EXPLANATION_LABELS[detail.catalogue.explanation]}</dd>
                  </div>
                )}
                {detail.catalogue.observed_motion && (
                  <div>
                    <dt>Observed motion</dt>
                    <dd>
                      {fmt(detail.catalogue.observed_motion.rate_arcsec_per_day, 2)}
                      ″/day · PA{" "}
                      {fmt(detail.catalogue.observed_motion.position_angle_deg, 0)}°
                    </dd>
                  </div>
                )}
                {detail.catalogue.expected_motion?.source && (
                  <div>
                    <dt>Expected (catalogue) motion</dt>
                    <dd>
                      {fmtRate(detail.catalogue.expected_motion.rate_arcsec_per_day)}
                      ″/day · {detail.catalogue.expected_motion.source}
                    </dd>
                  </div>
                )}
                {detail.catalogue.joint_p_chance !== null &&
                  detail.catalogue.joint_p_chance !== undefined && (
                    <div>
                      <dt>Joint chance-coincidence probability</dt>
                      <dd>{detail.catalogue.joint_p_chance.toExponential(1)}</dd>
                    </div>
                  )}
                <div>
                  <dt>Nearest coincidence</dt>
                  <dd>
                    {detail.catalogue.best_match_catalogue ?? "—"}
                    {detail.catalogue.best_match_separation_arcsec !== null &&
                      ` · ${fmt(detail.catalogue.best_match_separation_arcsec, 2)}″`}
                  </dd>
                </div>
                <div>
                  <dt>Catalogues checked</dt>
                  <dd>
                    {(detail.catalogue.catalogues_checked ??
                      detail.catalogue.services_succeeded
                    ).join(", ") || "—"}
                  </dd>
                </div>
                <div>
                  <dt>Required checks failed</dt>
                  <dd>{detail.catalogue.services_failed.join(", ") || "none"}</dd>
                </div>
                {!!detail.catalogue.optional_services_unavailable?.length && (
                  <div>
                    <dt>Optional services unavailable</dt>
                    <dd>{detail.catalogue.optional_services_unavailable.join(", ")}</dd>
                  </div>
                )}
              </dl>
              {!detail.catalogue.status_reason && detail.catalogue.notes && (
                <p className="notes-text">{detail.catalogue.notes}</p>
              )}
            </TechnicalDetails>

            {!!detail.catalogue.per_epoch?.length && (
              <TechnicalDetails summary="Catalogue evidence on each date">
                <p>
                  Catalogue positions are propagated to each observation epoch
                  with their own proper motion. χ² compares the separation with
                  the combined SPHEREx + catalogue uncertainty (consistent if
                  ≤ 13.8: 2 degrees of freedom, 99.9%). Persistence is the
                  forced-photometry SNR at this epoch&apos;s position in the
                  other two images; a static source stays detectable there.
                </p>
                <div className="table-scroll">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Date (epoch)</th>
                        <th>Nearest catalogue match</th>
                        <th>Expected RA, Dec at epoch (deg)</th>
                        <th>Separation (″)</th>
                        <th>σ total (″)</th>
                        <th>χ²</th>
                        <th>Consistent matches</th>
                        <th>P(chance)</th>
                        <th>Flux vs G (mag)</th>
                        <th>Persistence SNR</th>
                      </tr>
                    </thead>
                    <tbody>
                      {detail.catalogue.per_epoch.map((m) => (
                        <tr key={m.epoch}>
                          <td data-label="Date (epoch)">{dateLabel(m.epoch)}</td>
                          <td data-label="Nearest catalogue match">{m.match_object || "—"}</td>
                          <td data-label="Expected RA, Dec (deg)">
                            {fmt(m.expected_ra_deg, 5)}, {fmt(m.expected_dec_deg, 5)}
                          </td>
                          <td data-label="Separation (arcsec)">{fmt(m.separation_arcsec, 2)}</td>
                          <td data-label="Sigma total (arcsec)">{fmt(m.sigma_total_arcsec, 2)}</td>
                          <td data-label="Chi2">{fmt(m.chi2, 2)}</td>
                          <td data-label="Consistent matches">{m.n_consistent ?? "—"}</td>
                          <td data-label="P(chance)">{fmt(m.p_chance, 4)}</td>
                          <td data-label="Flux vs G residual (mag)">{fmt(m.mag_residual, 2)}</td>
                          <td data-label="Persistence SNR">
                            {m.persistence_snr?.replace(/;/g, " · ") ?? "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </TechnicalDetails>
            )}

            <TechnicalDetails summary="Position on each date">
              <div className="table-scroll">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Date (epoch)</th>
                      <th>RA (deg)</th>
                      <th>Dec (deg)</th>
                      <th>Source ID</th>
                      <th>Flux</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(["A", "C", "B"] as const).map((epoch) => {
                      const pos = detail.positions[epoch];
                      return (
                        <tr key={epoch}>
                          <td data-label="Date (epoch)">{dateLabel(epoch)}</td>
                          <td data-label="RA (deg)">{fmt(pos.ra_deg, 6)}</td>
                          <td data-label="Dec (deg)">{fmt(pos.dec_deg, 6)}</td>
                          <td data-label="Source ID">{pos.source_id ?? "—"}</td>
                          <td data-label="Flux">{fmt(pos.flux, 3)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </TechnicalDetails>

            <TechnicalDetails summary="Motion and validation scores">
              <dl className="kv-list">
                <div>
                  <dt>Total motion (A→B)</dt>
                  <dd>{fmt(detail.motion.total_motion_arcsec, 2)}″</dd>
                </div>
                <div>
                  <dt>Motion rate (A→B)</dt>
                  <dd>{fmt(detail.motion.motion_arcsec_per_day, 3)}″/day</dd>
                </div>
                <div>
                  <dt>A → C motion / rate</dt>
                  <dd>
                    {fmt(detail.motion.motion_AC_arcsec, 2)}″ ·{" "}
                    {fmt(detail.motion.rate_AC_arcsec_per_day, 3)}″/day
                  </dd>
                </div>
                <div>
                  <dt>C → B motion / rate</dt>
                  <dd>
                    {fmt(detail.motion.motion_CB_arcsec, 2)}″ ·{" "}
                    {fmt(detail.motion.rate_CB_arcsec_per_day, 3)}″/day
                  </dd>
                </div>
                <div>
                  <dt>Direction change (A→C vs C→B)</dt>
                  <dd>{fmt(detail.motion.direction_diff_deg, 2)}°</dd>
                </div>
                <div>
                  <dt>Validation score</dt>
                  <dd>{fmt(detail.validation.validation_score, 1)}</dd>
                </div>
                <div>
                  <dt>Trajectory consistency</dt>
                  <dd>{fmt(detail.validation.trajectory_score, 3)}</dd>
                </div>
                <div>
                  <dt>Rate consistency</dt>
                  <dd>{fmt(detail.validation.rate_consistency_score, 3)}</dd>
                </div>
                <div>
                  <dt>C prediction error</dt>
                  <dd>{fmt(detail.validation.C_prediction_error_arcsec, 2)}″</dd>
                </div>
                <div>
                  <dt>Flux variation (CV)</dt>
                  <dd>{fmt(detail.validation.flux_variation, 3)}</dd>
                </div>
                <div>
                  <dt>Mean flux</dt>
                  <dd>{fmt(detail.validation.flux_mean, 3)}</dd>
                </div>
                <div>
                  <dt>Validation rank / final priority rank</dt>
                  <dd>
                    {detail.rank ?? "—"} / {detail.final_rank ?? "—"}
                  </dd>
                </div>
                <div>
                  <dt>Final priority score</dt>
                  <dd>{fmt(detail.final_priority_score, 1)}</dd>
                </div>
              </dl>
              {detail.ranking_reason && <p className="notes-text">{detail.ranking_reason}</p>}
            </TechnicalDetails>

            <TechnicalDetails summary={`Every catalogue check (${crossmatch?.record_count ?? 0} records)`}>
              <div className="table-scroll">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Date (epoch)</th>
                      <th>Catalogue</th>
                      <th>Matched object</th>
                      <th>Object type</th>
                      <th>Separation (″)</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {crossmatch?.records.map((r, i) => (
                      <tr key={`${r.catalogue}-${r.epoch}-${i}`}>
                        <td data-label="Date (epoch)">{dateLabel(r.epoch)}</td>
                        <td data-label="Catalogue">{r.catalogue}</td>
                        <td data-label="Matched object">{r.matched_object ?? "—"}</td>
                        <td data-label="Object type">{r.object_type ?? "—"}</td>
                        <td data-label="Separation (arcsec)">{fmt(r.separation_arcsec, 2)}</td>
                        <td data-label="Status">
                          <span className={`match-status match-status-${r.match_status.toLowerCase()}`}>
                            {MATCH_STATUS_LABELS[r.match_status] ?? r.match_status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </TechnicalDetails>
          </section>
        </>
      )}
    </div>
  );
}
