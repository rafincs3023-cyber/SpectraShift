import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type {
  CandidateDetail as CandidateDetailType,
  CandidateSpectrumResponse,
  CrossmatchResponse,
} from "../api/types";
import { LoadingState } from "../components/LoadingState";
import { ErrorState } from "../components/ErrorState";
import { StatusBadge } from "../components/StatusBadge";
import { SpectrumChart } from "../components/explore/SpectrumChart";
import { CandidateCutouts } from "../components/candidate/CandidateCutouts";
import { MotionTrackChart } from "../components/candidate/MotionTrackChart";
import { LightCurveChart } from "../components/candidate/LightCurveChart";

function fmt(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "—";
  }
  return value.toFixed(digits);
}

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

  return (
    <div className="page">
      <div className="page-header">
        <Link to="/candidates" className="back-link">
          ← Back to candidates
        </Link>
        <h1>{id}</h1>
        <p className="page-subtitle">
          Evidence from the SPHEREx three-epoch motion pipeline. Live data
          from <code>GET /api/candidates/{id}</code> and{" "}
          <code>GET /api/catalogue-crossmatch/{id}</code>.
        </p>
        <div className="inspect-links">
          <Link to={`/explore?candidate=${encodeURIComponent(id)}`} className="btn btn-secondary">
            Inspect in Explore
          </Link>
          <Link to="/compare" className="btn btn-secondary">
            Open in Compare
          </Link>
        </div>
      </div>

      {loading && <LoadingState label="Loading candidate evidence…" />}

      {!loading && notFound && (
        <ErrorState message={`No candidate found with ID "${id}".`} />
      )}

      {!loading && error && (
        <ErrorState message={error} onRetry={() => load(id)} />
      )}

      {!loading && !notFound && !error && detail && (
        <>
          <section className="card-grid">
            <div className="card">
              <h2>Ranking</h2>
              <dl className="kv-list">
                <div>
                  <dt>Validation rank</dt>
                  <dd>{detail.rank ?? "—"}</dd>
                </div>
                <div>
                  <dt>Final priority rank</dt>
                  <dd>{detail.final_rank ?? "—"}</dd>
                </div>
                <div>
                  <dt>Final priority score</dt>
                  <dd>{fmt(detail.final_priority_score, 1)}</dd>
                </div>
                <div>
                  <dt>Validation score</dt>
                  <dd>{fmt(detail.validation.validation_score, 1)}</dd>
                </div>
              </dl>
            </div>

            <div className="card">
              <h2>Catalogue Status</h2>
              <div className="catalogue-status-row">
                <StatusBadge status={detail.catalogue.final_catalogue_status} />
              </div>
              <dl className="kv-list">
                <div>
                  <dt>Nearest coincidence</dt>
                  <dd>
                    {detail.catalogue.best_match_catalogue ?? "—"}
                    {detail.catalogue.best_match_separation_arcsec !== null &&
                      ` · ${fmt(
                        detail.catalogue.best_match_separation_arcsec,
                        2
                      )}″`}
                  </dd>
                </div>
                <div>
                  <dt>Services succeeded</dt>
                  <dd>
                    {detail.catalogue.services_succeeded.join(", ") || "—"}
                  </dd>
                </div>
                <div>
                  <dt>Services failed</dt>
                  <dd>{detail.catalogue.services_failed.join(", ") || "—"}</dd>
                </div>
              </dl>
              {detail.catalogue.notes && (
                <p className="notes-text">{detail.catalogue.notes}</p>
              )}
            </div>
          </section>

          <section className="card">
            <h2>Positions by Epoch</h2>
            <div className="table-scroll">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Epoch</th>
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
                        <td data-label="Epoch">{epoch}</td>
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
          </section>

          <section className="card-grid">
            <div className="card">
              <h2>Motion</h2>
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
              </dl>
            </div>

            <div className="card">
              <h2>Validation Scores</h2>
              <dl className="kv-list">
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
                  <dd>
                    {fmt(detail.validation.C_prediction_error_arcsec, 2)}″
                  </dd>
                </div>
                <div>
                  <dt>Flux variation (CV)</dt>
                  <dd>{fmt(detail.validation.flux_variation, 3)}</dd>
                </div>
                <div>
                  <dt>Mean flux</dt>
                  <dd>{fmt(detail.validation.flux_mean, 3)}</dd>
                </div>
              </dl>
            </div>
          </section>

          {detail.ranking_reason && (
            <section className="card">
              <h2>Ranking Notes</h2>
              <p className="notes-text">{detail.ranking_reason}</p>
            </section>
          )}

          <section className="card">
            <h2>Visual Evidence</h2>
            <p className="section-note">
              Rendered directly from the real per-epoch FITS data and
              already-computed positions/flux above — nothing here is
              simulated or interpolated beyond real instrument calibration.
            </p>

            <h3 className="evidence-subheading">Source cutouts by epoch</h3>
            <CandidateCutouts candidateId={detail.candidate_id} />

            <div className="card-grid evidence-grid">
              <div>
                <h3 className="evidence-subheading">Motion track (A → C → B)</h3>
                <MotionTrackChart positions={detail.positions} />
              </div>
              <div>
                <h3 className="evidence-subheading">Spectrum (flux vs. wavelength)</h3>
                {spectrum ? (
                  <SpectrumChart points={spectrum.points} />
                ) : (
                  <p className="section-note">Data unavailable.</p>
                )}
              </div>
            </div>

            <h3 className="evidence-subheading">Brightness vs. time</h3>
            {spectrum ? (
              <LightCurveChart points={spectrum.points} />
            ) : (
              <p className="section-note">Data unavailable.</p>
            )}
          </section>

          <section className="card">
            <h2>Catalogue Cross-Match Detail</h2>
            <p className="section-note">
              Every epoch × catalogue check performed for this candidate
              ({crossmatch?.record_count ?? 0} records).
            </p>
            <div className="table-scroll">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Epoch</th>
                    <th>Catalogue</th>
                    <th>Matched Object</th>
                    <th>Object Type</th>
                    <th>Separation (″)</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {crossmatch?.records.map((r, i) => (
                    <tr key={`${r.catalogue}-${r.epoch}-${i}`}>
                      <td data-label="Epoch">{r.epoch}</td>
                      <td data-label="Catalogue">{r.catalogue}</td>
                      <td data-label="Matched Object">
                        {r.matched_object ?? "—"}
                      </td>
                      <td data-label="Object Type">{r.object_type ?? "—"}</td>
                      <td data-label="Separation (arcsec)">
                        {fmt(r.separation_arcsec, 2)}
                      </td>
                      <td data-label="Status">
                        <span
                          className={`match-status match-status-${r.match_status.toLowerCase()}`}
                        >
                          {MATCH_STATUS_LABELS[r.match_status] ??
                            r.match_status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </div>
  );
}
