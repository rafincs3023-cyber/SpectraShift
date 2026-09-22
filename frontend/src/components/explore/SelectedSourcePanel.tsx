import { Link } from "react-router-dom";
import type { CandidateDetail, CandidateSpectrumResponse, EpochLabel } from "../../api/types";
import { StatusBadge } from "../StatusBadge";
import { LoadingState } from "../LoadingState";
import { ErrorState } from "../ErrorState";
import { SpectrumChart } from "./SpectrumChart";

function fmt(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return value.toFixed(digits);
}

export function SelectedSourcePanel({
  epoch,
  loading,
  error,
  detail,
  spectrum,
}: {
  epoch: EpochLabel;
  loading: boolean;
  error: string | null;
  detail: CandidateDetail | null;
  spectrum: CandidateSpectrumResponse | null;
}) {
  if (loading) {
    return (
      <aside className="field-panel">
        <LoadingState label="Loading source…" />
      </aside>
    );
  }

  if (error) {
    return (
      <aside className="field-panel">
        <ErrorState message={error} />
      </aside>
    );
  }

  if (!detail) {
    return (
      <aside className="field-panel">
        <h2>Selected source</h2>
        <p className="section-note">
          Click a marker on the sky viewer to inspect a candidate source:
          its RA/Dec, real per-epoch spectral samples, catalogue
          cross-match status, and motion.
        </p>
      </aside>
    );
  }

  const pos = detail.positions[epoch];

  return (
    <aside className="field-panel selected-source-panel">
      <div className="field-candidate-card-top">
        <Link
          to={`/candidates/${encodeURIComponent(detail.candidate_id)}`}
          className="candidate-link"
        >
          {detail.candidate_id}
        </Link>
        <StatusBadge status={detail.catalogue.final_catalogue_status} />
      </div>
      <p className="section-note">
        Preliminary, unconfirmed candidate — not a confirmed object.
      </p>

      <h2>Position (Epoch {epoch})</h2>
      <dl className="kv-list kv-list-compact">
        <div>
          <dt>RA</dt>
          <dd>{fmt(pos.ra_deg, 6)}°</dd>
        </div>
        <div>
          <dt>Dec</dt>
          <dd>{fmt(pos.dec_deg, 6)}°</dd>
        </div>
        <div>
          <dt>Flux (this epoch)</dt>
          <dd>{fmt(pos.flux, 3)}</dd>
        </div>
      </dl>

      <h2>Motion &amp; brightness</h2>
      <dl className="kv-list kv-list-compact">
        <div>
          <dt>Apparent motion (A→B)</dt>
          <dd>{fmt(detail.motion.total_motion_arcsec, 1)}″</dd>
        </div>
        <div>
          <dt>Motion rate</dt>
          <dd>{fmt(detail.motion.motion_arcsec_per_day, 2)}″/day</dd>
        </div>
        <div>
          <dt>Flux variation (CV)</dt>
          <dd>{fmt(detail.validation.flux_variation, 3)}</dd>
        </div>
        <div>
          <dt>Validation score</dt>
          <dd>{fmt(detail.validation.validation_score, 1)}</dd>
        </div>
      </dl>

      <h2>Catalogue match</h2>
      {detail.catalogue.best_match_catalogue ? (
        <dl className="kv-list kv-list-compact">
          <div>
            <dt>Catalogue</dt>
            <dd>{detail.catalogue.best_match_catalogue}</dd>
          </div>
          <div>
            <dt>Identifier</dt>
            <dd>{detail.catalogue.best_match_object ?? "—"}</dd>
          </div>
          <div>
            <dt>Separation</dt>
            <dd>{fmt(detail.catalogue.best_match_separation_arcsec, 2)}″</dd>
          </div>
          <div>
            <dt>Status</dt>
            <dd>{detail.catalogue.final_catalogue_status ?? "—"}</dd>
          </div>
        </dl>
      ) : (
        <p className="section-note">No catalogue coincidence on record.</p>
      )}

      <h2>Spectrum (flux vs. wavelength)</h2>
      {spectrum ? (
        <SpectrumChart points={spectrum.points} />
      ) : (
        <p className="section-note">No spectral data available.</p>
      )}
    </aside>
  );
}
