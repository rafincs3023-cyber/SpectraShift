import { Link } from "react-router-dom";
import type { CandidateDetail, CandidateSpectrumResponse, EpochLabel } from "../../api/types";
import { StatusBadge } from "../StatusBadge";
import { LoadingState } from "../LoadingState";
import { ErrorState } from "../ErrorState";
import { SpectrumChart } from "./SpectrumChart";
import { InfoTooltip } from "../ui/InfoTooltip";

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
        <h2>Selected object</h2>
        <p className="section-note">
          Nothing selected. When markers are shown on the image, click one to
          see its sky position, brightness, catalogue check and motion here.
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
        A possible moving object — not a confirmed discovery.
      </p>

      <h2>Position on this date (Epoch {epoch})</h2>
      <dl className="kv-list kv-list-compact">
        <div>
          <dt>
            RA
            <InfoTooltip term="ra" />
          </dt>
          <dd>{fmt(pos.ra_deg, 6)}°</dd>
        </div>
        <div>
          <dt>
            Dec
            <InfoTooltip term="dec" />
          </dt>
          <dd>{fmt(pos.dec_deg, 6)}°</dd>
        </div>
        <div>
          <dt>
            Brightness (flux)
            <InfoTooltip term="brightness" />
          </dt>
          <dd>{fmt(pos.flux, 3)}</dd>
        </div>
      </dl>

      <h2>How it moved</h2>
      <dl className="kv-list kv-list-compact">
        <div>
          <dt>Distance moved (first → last date)</dt>
          <dd>{fmt(detail.motion.total_motion_arcsec, 1)}″</dd>
        </div>
        <div>
          <dt>Speed across the sky</dt>
          <dd>{fmt(detail.motion.motion_arcsec_per_day, 2)}″ per day</dd>
        </div>
        <div>
          <dt>Brightness variation (CV)</dt>
          <dd>{fmt(detail.validation.flux_variation, 3)}</dd>
        </div>
        <div>
          <dt>Validation score</dt>
          <dd>{fmt(detail.validation.validation_score, 1)}</dd>
        </div>
      </dl>

      <h2>Catalogue check</h2>
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
            <dt>Result</dt>
            <dd>
              <StatusBadge status={detail.catalogue.final_catalogue_status} />
            </dd>
          </div>
        </dl>
      ) : (
        <p className="section-note">No catalogue match on record.</p>
      )}

      <h2>
        Brightness at each wavelength sampled
        <InfoTooltip
          label="Why only a few wavelengths?"
          text="On each date SPHEREx measured this spot at one wavelength only, so there is at most one point per date — not a full spectrum."
        />
      </h2>
      {spectrum ? (
        <SpectrumChart points={spectrum.points} />
      ) : (
        <p className="section-note">Not available for this object.</p>
      )}
    </aside>
  );
}
