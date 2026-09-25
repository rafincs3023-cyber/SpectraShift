import { useEffect, useState } from "react";
import type { CSSProperties } from "react";
import { api, ApiError, imageUrl } from "../../api/client";
import type { SixMonthCompareResponse, SixMonthSide } from "../../api/types";
import { LoadingState } from "../LoadingState";
import { ErrorState } from "../ErrorState";
import { ObservationPanel } from "./ObservationPanel";
import { SliderCompare } from "./SliderCompare";
import { BlinkCompare } from "./BlinkCompare";
import { DifferenceView } from "./DifferenceView";
import { OverlayCanvas } from "./OverlayCanvas";
import { ModeTabs } from "./ModeTabs";
import { DifferenceLegend } from "./DifferenceLegend";
import { InfoTooltip } from "../ui/InfoTooltip";
import { TechnicalDetails } from "../ui/TechnicalDetails";
import type { CompareMode } from "./compareModes";

/** metadata.json dates are UTC without a zone suffix. */
function parseUtc(iso: string): Date {
  return new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : `${iso}Z`);
}

function formatObsDate(iso: string): string {
  return parseUtc(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  });
}

function formatObsTime(iso: string): string {
  return `${parseUtc(iso).toISOString().slice(11, 19)} UTC`;
}

function withLabel(side: SixMonthSide, which: "A" | "B"): SixMonthSide {
  const date = side.observation?.date_obs;
  return {
    ...side,
    label: `${which === "A" ? "Earlier" : "Later"} image · ${date ? formatObsDate(date) : "unknown date"}`,
  };
}

// Real SPHEREx header note (DETECTOR keyword comment): "1-3: SWIR, 4-6: MWIR"
function detectorText(detector: number | null | undefined): string {
  if (detector === null || detector === undefined) return "—";
  return `D${detector} (${detector <= 3 ? "SWIR" : "MWIR"})`;
}

export function SixMonthCompare({
  mode,
  onModeChange,
}: {
  mode: CompareMode;
  onModeChange: (mode: CompareMode) => void;
}) {
  const [data, setData] = useState<SixMonthCompareResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .getSixMonthCompare()
      .then((res) => {
        if (!cancelled) setData(res);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Unexpected error");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (error) return <ErrorState message={error} />;
  if (!data) return <LoadingState label="Loading the two images…" />;

  const a = withLabel(data.epoch_a, "A");
  const b = withLabel(data.epoch_b, "B");
  const dateA = formatObsDate(data.epoch_a.observation!.date_obs!);
  const dateB = formatObsDate(data.epoch_b.observation!.date_obs!);
  const unit = data.bunit?.replace(/\s/g, "") ?? "—";
  const psfA = data.epoch_a.psf_fwhm_arcsec;
  const psfB = data.epoch_b.psf_fwhm_arcsec;

  const region = data.display_region;
  const target = data.target;
  const targetText = `RA ${target.ra_deg.toFixed(3)}° · Dec ${target.dec_deg.toFixed(3)}°`;
  const frameCenterText = `RA ${data.frame_center.ra_deg.toFixed(3)}° · Dec ${data.frame_center.dec_deg.toFixed(3)}°`;
  const targetNote = target.in_display_region
    ? "inside the displayed frame"
    : `just outside the displayed frame (${target.offset_from_display_px.toFixed(0)} px ≈ ${target.offset_from_display_arcsec.toFixed(0)}″ beyond its edge, where Epoch B's footprint narrows)`;

  // Frames match the displayed region's shape so nothing is cropped away.
  const frameStyle = {
    "--frame-aspect": `${region.width} / ${region.height}`,
  } as CSSProperties;

  return (
    <>
      <div className="time-compare-summary">
        <strong>
          Earlier image {dateA} → later image {dateB}
        </strong>
        <span>
          {data.time_gap_days.toFixed(2)} days apart (~
          {data.time_gap_months.toFixed(2)} months)
        </span>
        <span>
          Same wavelength (≈{data.epoch_a.wavelength_um.toFixed(2)} µm) and same detector
        </span>
        <span>Lined up pixel by pixel, so unchanged stars stay in place</span>
      </div>

      <ModeTabs mode={mode} onChange={onModeChange} />

      <div className="compare-layout compare-layout-wide">
        <div className="compare-viewer compare-viewer-wide" style={frameStyle}>
          {mode === "side-by-side" && (
            <div className="side-by-side-grid">
              <ObservationPanel
                side={a}
                markers={[]}
                showMarkers={false}
                coordLabel="Frame center"
              />
              <ObservationPanel
                side={b}
                markers={[]}
                showMarkers={false}
                coordLabel="Frame center"
              />
            </div>
          )}

          {mode === "slider" && (
            <SliderCompare epochA={a} epochB={b} markersA={[]} markersB={[]} />
          )}

          {mode === "blink" && (
            <BlinkCompare epochA={a} epochB={b} markersA={[]} markersB={[]} />
          )}

          {mode === "difference" && (
            <DifferenceView
              available={data.difference_available}
              previewUrl={data.difference_preview_url}
              epochA="A"
              epochB="B"
              alt={`Later image (${dateB}) minus earlier image (${dateA})`}
              caption={
                <>
                  <DifferenceLegend
                    formula="Later image − Earlier image (B − A): positive values indicate higher surface brightness in the later epoch."
                    red={`brighter in the later image (${dateB})`}
                    blue={`brighter in the earlier image (${dateA})`}
                  />
                  <TechnicalDetails summary="Technical details about the difference image">
                    <p>
                      Display is symmetric about zero and clipped at the 99th
                      percentile of |B − A|.{" "}
                      <a href={imageUrl(data.difference_figure_url)} target="_blank" rel="noreferrer">
                        Reference figure with {unit} colour bar ↗
                      </a>
                    </p>
                    <p>
                      A residual is an apparent variation between the two
                      observations, not a confirmed physical change. Besides
                      real brightness change or motion it can come from the{" "}
                      {data.wavelength_delta_um.toFixed(4)} µm wavelength
                      offset, PSF/alignment residuals around bright stars, or
                      detector artifacts.
                    </p>
                  </TechnicalDetails>
                </>
              }
            />
          )}

          {mode === "overlay" && (
            <OverlayCanvas epochA={a} epochB={b} markers={[]} />
          )}

          <TechnicalDetails summary="Technical details about the alignment">
            <p>
              {data.alignment_note} Displayed frame: {region.width} ×{" "}
              {region.height} px, {(region.valid_fraction * 100).toFixed(2)}%
              valid in both epochs ({region.invalid_pixels} isolated invalid
              pixels drawn neutral). Frame center {frameCenterText}. Target{" "}
              {targetText} lies {targetNote}.
            </p>
          </TechnicalDetails>
        </div>

        <aside className="card time-compare-info">
          <h2>About these images</h2>
          <dl className="kv-list kv-list-compact">
            <div>
              <dt>Earlier image</dt>
              <dd>{dateA}</dd>
            </div>
            <div>
              <dt>Later image</dt>
              <dd>{dateB}</dd>
            </div>
            <div>
              <dt>Time between</dt>
              <dd>
                {data.time_gap_days.toFixed(2)} days (~
                {data.time_gap_months.toFixed(2)} months)
              </dd>
            </div>
            <div>
              <dt>
                Wavelength
                <InfoTooltip term="wavelength" />
              </dt>
              <dd>≈{data.epoch_a.wavelength_um.toFixed(2)} µm (both)</dd>
            </div>
            <div>
              <dt>
                Detector
                <InfoTooltip term="detector" />
              </dt>
              <dd>{detectorText(data.epoch_a.observation?.detector)}</dd>
            </div>
            <div>
              <dt>
                Brightness unit
                <InfoTooltip term="unit" />
              </dt>
              <dd>{unit}</dd>
            </div>
            <div>
              <dt>
                Target
                <InfoTooltip term="skyCoordinates" />
              </dt>
              <dd>{targetText}</dd>
            </div>
          </dl>
          <TechnicalDetails>
          <dl className="kv-list kv-list-compact">
            <div>
              <dt>Epoch A (earlier)</dt>
              <dd>
                {dateA} · {formatObsTime(data.epoch_a.observation!.date_obs!)}
              </dd>
            </div>
            <div>
              <dt>Epoch B (later)</dt>
              <dd>
                {dateB} · {formatObsTime(data.epoch_b.observation!.date_obs!)}
              </dd>
            </div>
            <div>
              <dt>Wavelength A</dt>
              <dd>{data.epoch_a.wavelength_um.toFixed(6)} µm</dd>
            </div>
            <div>
              <dt>Wavelength B</dt>
              <dd>{data.epoch_b.wavelength_um.toFixed(6)} µm</dd>
            </div>
            <div>
              <dt>Wavelength difference</dt>
              <dd>
                {data.wavelength_delta_um.toFixed(6)} µm
                {data.delta_over_bandwidth !== null &&
                  ` (${data.delta_over_bandwidth.toFixed(3)} × bandwidth)`}
              </dd>
            </div>
            {psfA !== null && psfB !== null && (
              <div>
                <dt>PSF FWHM</dt>
                <dd>
                  {psfA === psfB
                    ? `${psfA.toFixed(2)}″ (both)`
                    : `${psfA.toFixed(2)}″ / ${psfB.toFixed(2)}″`}
                </dd>
              </div>
            )}
            <div>
              <dt>Aligned crop (bounding box)</dt>
              <dd>
                {data.crop.width} × {data.crop.height} px
              </dd>
            </div>
            <div>
              <dt>Common footprint</dt>
              <dd>{data.overlap_pixels.toLocaleString("en-US")} px</dd>
            </div>
            <div>
              <dt>Displayed frame</dt>
              <dd>
                {region.width} × {region.height} px ·{" "}
                {(region.valid_fraction * 100).toFixed(2)}% valid
              </dd>
            </div>
            <div>
              <dt>Frame center</dt>
              <dd>{frameCenterText}</dd>
            </div>
            <div>
              <dt>Difference</dt>
              <dd>B − A (later − earlier)</dd>
            </div>
          </dl>
          <p className="notes-text">
            Epoch B is reprojected onto Epoch A's pixel grid. Source files:{" "}
            <code>{data.epoch_a.source_file}</code>,{" "}
            <code>{data.epoch_b.source_file}</code>. Reference figures:{" "}
            <a href={imageUrl(data.epoch_a.figure_url)} target="_blank" rel="noreferrer">
              A
            </a>
            {" · "}
            <a href={imageUrl(data.epoch_b.figure_url)} target="_blank" rel="noreferrer">
              B aligned
            </a>
            {" · "}
            <a href={imageUrl(data.difference_figure_url)} target="_blank" rel="noreferrer">
              B − A
            </a>
            .
          </p>
          </TechnicalDetails>
        </aside>
      </div>

      <p className="disclaimer">
        These are two real SPHEREx observations. Any difference you see is an
        apparent change, not a confirmed discovery, and a difference on its own
        does not prove that something moved.
      </p>
    </>
  );
}
