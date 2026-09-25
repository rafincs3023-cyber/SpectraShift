import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { CandidateDetailResponse, CandidateSighting } from "../api/types";
import { LoadingState } from "../components/LoadingState";
import { ErrorState } from "../components/ErrorState";
import { CandidateCutouts } from "../components/candidate/CandidateCutouts";
import { PageIntro } from "../components/ui/PageIntro";
import { InfoTooltip } from "../components/ui/InfoTooltip";
import { TechnicalDetails } from "../components/ui/TechnicalDetails";
import { EmptyStateCard } from "../components/ui/EmptyStateCard";
import {
  KIND_EXPLANATION,
  displacementText,
  fmt,
  longDate,
  rateText,
} from "../components/candidate/candidateFormat";

function SightingCard({
  title,
  date,
  s,
}: {
  title: string;
  date: string;
  s: CandidateSighting | null;
}) {
  return (
    <div className="card">
      <h2>{title}</h2>
      <p className="section-note">{date}</p>
      {s ? (
        <dl className="kv-list">
          <div>
            <dt>
              RA
              <InfoTooltip term="ra" />
            </dt>
            <dd>{fmt(s.ra, 5)}°</dd>
          </div>
          <div>
            <dt>
              Dec
              <InfoTooltip term="dec" />
            </dt>
            <dd>{fmt(s.dec, 5)}°</dd>
          </div>
          <div>
            <dt>
              Brightness
              <InfoTooltip term="brightness" />
            </dt>
            <dd>{fmt(s.brightness, 3)}</dd>
          </div>
          <div>
            <dt>Signal strength (SNR)</dt>
            <dd>{fmt(s.snr, 1)}</dd>
          </div>
        </dl>
      ) : (
        <p>Not found at this position in this image.</p>
      )}
    </div>
  );
}

export function CandidateDetail() {
  const { id = "" } = useParams();
  const [detail, setDetail] = useState<CandidateDetailResponse | null>(null);
  const [error, setError] = useState<{ message: string; status: number } | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .getCandidate(id)
      .then((res) => {
        if (!cancelled) setDetail(res);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(
            err instanceof ApiError
              ? { message: err.message, status: err.status }
              : { message: "Unexpected error", status: 0 }
          );
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  const back = (
    <Link to="/candidates" className="back-link">
      ← All candidates
    </Link>
  );

  if (loading) {
    return (
      <div className="page">
        {back}
        <LoadingState label="Loading the candidate…" />
      </div>
    );
  }

  if (error || !detail) {
    return (
      <div className="page">
        {back}
        {error?.status === 404 ? (
          <EmptyStateCard
            title={`There is no candidate called “${id}”.`}
            actions={
              <Link to="/candidates" className="btn btn-secondary">
                See the current candidates
              </Link>
            }
          >
            <p>The candidate list is rebuilt from the June 19 and December 17, 2025 observations; this ID is not in it.</p>
          </EmptyStateCard>
        ) : (
          <ErrorState message={error?.message ?? "Could not load this candidate."} />
        )}
      </div>
    );
  }

  const c = detail;
  const earlierDate = longDate(c.earlier_date);
  const laterDate = longDate(c.later_date);
  const dates = { earlier: earlierDate, later: laterDate };

  return (
    <div className="page">
      {back}
      <PageIntro
        eyebrow={`Two-epoch candidate · ${c.kind_label}`}
        title={c.candidate_id}
        lead={KIND_EXPLANATION[c.kind]}
      />
      <p className="callout-warning">
        A preliminary two-epoch candidate — not a confirmed moving object or
        discovery. Two observations cannot establish a path or an orbit.
      </p>

      <div className="inspect-links">
        <Link
          to={`/explore?candidate=${encodeURIComponent(c.candidate_id)}${c.earlier ? "" : "&image=later"}`}
          className="btn btn-secondary"
        >
          Show in Explore
        </Link>
        <Link to="/compare?mode=blink" className="btn btn-secondary">
          Blink the two images
        </Link>
      </div>

      <section className="card-grid">
        <SightingCard title="Earlier observation" date={earlierDate} s={c.earlier} />
        <SightingCard title="Later observation" date={laterDate} s={c.later} />
        <div className="card">
          <h2>What changed</h2>
          <dl className="kv-list">
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
            <div>
              <dt>Brightness later ÷ earlier</dt>
              <dd>{c.brightness_ratio_later_over_earlier === null ? "—" : fmt(c.brightness_ratio_later_over_earlier, 2)}</dd>
            </div>
            <div>
              <dt>Time between</dt>
              <dd>{c.time_baseline_days.toFixed(2)} days</dd>
            </div>
          </dl>
        </div>
      </section>

      <section className="card">
        <h2>Pictures</h2>
        <p className="section-note">
          Real pixels around the candidate, about {Math.round(c.cutout_size_arcsec / 60 * 10) / 10}′
          across. The earlier and later cutouts share one brightness scale. In
          the difference, red = brighter later, blue = brighter earlier.
        </p>
        {c.cutouts.map((set) => (
          <div key={set.at}>
            {c.cutouts.length > 1 && (
              <h3 className="evidence-subheading">
                Around the {set.at} position
              </h3>
            )}
            <CandidateCutouts set={set} candidateId={c.candidate_id} dates={dates} />
          </div>
        ))}
      </section>

      <section className="card">
        <h2>Things to keep in mind</h2>
        <ul className="plain-list">
          {c.caveats.map((t) => (
            <li key={t}>{t}</li>
          ))}
          {c.limitations.map((t) => (
            <li key={t}>{t}</li>
          ))}
        </ul>
      </section>

      <section className="card">
        <TechnicalDetails summary="Technical details">
          <dl className="kv-list">
            <div>
              <dt>Status</dt>
              <dd>Passed the current checks (candidate for inspection)</dd>
            </div>
            <div>
              <dt>Earlier observation time</dt>
              <dd>{c.earlier_date} UTC</dd>
            </div>
            <div>
              <dt>Later observation time</dt>
              <dd>{c.later_date} UTC</dd>
            </div>
            {c.position_angle_deg !== null && (
              <div>
                <dt>Direction of the change (position angle, east of north)</dt>
                <dd>{fmt(c.position_angle_deg, 1)}°</dd>
              </div>
            )}
            {c.shift_significance_sigma != null && (
              <div>
                <dt>Shift significance</dt>
                <dd>
                  {fmt(c.shift_significance_sigma, 1)}σ (stationary tolerance{" "}
                  {fmt(c.stationary_tolerance_arcsec, 2)}″ at this brightness)
                </dd>
              </div>
            )}
            {c.alternative_partners !== undefined && (
              <div>
                <dt>Other possible pairings</dt>
                <dd>{c.alternative_partners}</dd>
              </div>
            )}
          </dl>
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Measurement</th>
                  <th>Earlier</th>
                  <th>Later</th>
                </tr>
              </thead>
              <tbody>
                {(
                  [
                    ["Pixel x, y (shared grid)", (s: CandidateSighting) => `${fmt(s.x, 2)}, ${fmt(s.y, 2)}`],
                    ["SNR (matched filter)", (s: CandidateSighting) => fmt(s.snr, 1)],
                    ["Aperture brightness (Σ MJy/sr, r = 2 px)", (s: CandidateSighting) => fmt(s.brightness, 4)],
                    ["Peak (MJy/sr above sky)", (s: CandidateSighting) => fmt(s.peak, 4)],
                    ["Sharpness (peak ÷ 3×3 core)", (s: CandidateSighting) => fmt(s.sharpness, 3)],
                    ["Roundness", (s: CandidateSighting) => fmt(s.roundness, 3)],
                    ["Centroid error", (s: CandidateSighting) => `${fmt(s.centroid_error_arcsec, 2)}″`],
                    ["SNR at the same place in the other image", (s: CandidateSighting) => fmt(s.forced_snr_in_other_image, 1)],
                    ["Difference-image significance", (s: CandidateSighting) => fmt(s.difference_snr, 1)],
                  ] as const
                ).map(([label, get]) => (
                  <tr key={label}>
                    <td data-label="Measurement">{label}</td>
                    <td data-label="Earlier">{c.earlier ? get(c.earlier) : "—"}</td>
                    <td data-label="Later">{c.later ? get(c.later) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </TechnicalDetails>
      </section>
    </div>
  );
}
