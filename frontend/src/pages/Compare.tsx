import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type {
  CandidateMarker,
  CandidateSummary,
  ComparePairResponse,
  EpochLabel,
  Observation,
} from "../api/types";
import { LoadingState } from "../components/LoadingState";
import { ErrorState } from "../components/ErrorState";
import { ObservationPanel } from "../components/compare/ObservationPanel";
import { SliderCompare } from "../components/compare/SliderCompare";
import { BlinkCompare } from "../components/compare/BlinkCompare";
import { DifferenceView } from "../components/compare/DifferenceView";
import { OverlayCanvas } from "../components/compare/OverlayCanvas";
import { FieldCandidatePanel } from "../components/compare/FieldCandidatePanel";
import { ModeTabs } from "../components/compare/ModeTabs";
import {
  COMPARE_MODES,
  type CompareMode,
} from "../components/compare/compareModes";
import { SixMonthCompare } from "../components/compare/SixMonthCompare";

type Dataset = "6month" | "31day";

// Real SPHEREx header note (DETECTOR keyword comment): "1-3: SWIR, 4-6: MWIR"
function detectorLabel(detector: number | null | undefined): string {
  if (detector === null || detector === undefined) return "Unknown";
  const band = detector <= 3 ? "SWIR" : "MWIR";
  return `Detector ${detector} (${band})`;
}

/** Time Compare: the ~6-month pair is the primary/default dataset; the
 * original A/C/B short-baseline comparison is kept as a secondary one.
 * The selection lives in ?dataset= and ?mode= so any view can be linked. */
export function Compare() {
  const [searchParams, setSearchParams] = useSearchParams();
  const dataset: Dataset =
    searchParams.get("dataset") === "31day" ? "31day" : "6month";
  const modeParam = searchParams.get("mode");
  const mode: CompareMode = COMPARE_MODES.includes(modeParam as CompareMode)
    ? (modeParam as CompareMode)
    : "side-by-side";

  function updateParams(nextDataset: Dataset, nextMode: CompareMode) {
    const params: Record<string, string> = {};
    if (nextDataset !== "6month") params.dataset = nextDataset;
    if (nextMode !== "side-by-side") params.mode = nextMode;
    setSearchParams(params, { replace: true });
  }
  const selectDataset = (next: Dataset) => updateParams(next, mode);
  const setMode = (next: CompareMode) => updateParams(dataset, next);

  return (
    <div className="page compare-page">
      <div className="page-header">
        <h1>Time Compare</h1>
        <p className="page-subtitle">
          Compare real SPHEREx observations of the same sky taken at different
          times and inspect apparent change.
        </p>
      </div>

      <div className="view-scope-note">
        <strong>Time Compare</strong> = changes between observation times
        (same sky, different dates). <strong>Spectral View</strong> = changes
        across wavelength (same sky, 102 wavelength channels) —{" "}
        <Link to="/spectral">open Spectral View</Link>.
      </div>

      <div className="dataset-tabs" role="tablist" aria-label="Comparison dataset">
        <button
          type="button"
          role="tab"
          aria-selected={dataset === "6month"}
          className={dataset === "6month" ? "dataset-tab dataset-tab-active" : "dataset-tab"}
          onClick={() => selectDataset("6month")}
        >
          <span className="dataset-tab-title">
            ~6-Month Compare <span className="dataset-tab-badge">Primary</span>
          </span>
          <span className="dataset-tab-sub">Jun 19, 2025 → Dec 17, 2025 · 181.8-day baseline</span>
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={dataset === "31day"}
          className={dataset === "31day" ? "dataset-tab dataset-tab-active" : "dataset-tab"}
          onClick={() => selectDataset("31day")}
        >
          <span className="dataset-tab-title">
            Short-Baseline / 31-Day Compare{" "}
            <span className="dataset-tab-badge dataset-tab-badge-muted">Secondary</span>
          </span>
          <span className="dataset-tab-sub">Epochs A / C / B · May 9 → Jun 9, 2025</span>
        </button>
      </div>

      {dataset === "6month" ? (
        <SixMonthCompare mode={mode} onModeChange={setMode} />
      ) : (
        <ShortBaselineCompare mode={mode} onModeChange={setMode} />
      )}
    </div>
  );
}

/** The original A/C/B 31-day comparison, unchanged apart from sharing the
 * mode selection with the ~6-month view. */
function ShortBaselineCompare({
  mode,
  onModeChange,
}: {
  mode: CompareMode;
  onModeChange: (mode: CompareMode) => void;
}) {
  const [observations, setObservations] = useState<Observation[] | null>(null);
  const [candidates, setCandidates] = useState<CandidateSummary[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const [epochA, setEpochA] = useState<EpochLabel>("A");
  const [epochB, setEpochB] = useState<EpochLabel>("B");

  const [pair, setPair] = useState<ComparePairResponse | null>(null);
  const [markersA, setMarkersA] = useState<CandidateMarker[]>([]);
  const [markersB, setMarkersB] = useState<CandidateMarker[]>([]);
  const [pairError, setPairError] = useState<string | null>(null);
  const [pairLoading, setPairLoading] = useState(true);

  // Initial load: observations + candidates
  useEffect(() => {
    setLoading(true);
    setLoadError(null);
    Promise.all([api.getObservations(), api.getCandidates()])
      .then(([obsRes, candRes]) => {
        setObservations(obsRes.observations);
        setCandidates(candRes.candidates);
      })
      .catch((err: unknown) =>
        setLoadError(err instanceof ApiError ? err.message : "Unexpected error")
      )
      .finally(() => setLoading(false));
  }, []);

  // Reload the pair + markers whenever the selected epochs change
  useEffect(() => {
    if (epochA === epochB) {
      // Shouldn't happen via the UI (each <select> disables the epoch
      // chosen in the other one), but guard against a stuck spinner if it
      // ever does.
      setPairLoading(false);
      setPairError("Observation A and Observation B must be different epochs.");
      return;
    }

    let cancelled = false;
    setPairLoading(true);
    setPairError(null);

    api
      .getComparePair(epochA, epochB)
      .then(async (pairRes) => {
        if (cancelled) return;
        setPair(pairRes);

        const [mA, mB] = await Promise.all([
          api.getByPath<{ markers: CandidateMarker[] }>(
            pairRes.epoch_a.markers_url
          ),
          api.getByPath<{ markers: CandidateMarker[] }>(
            pairRes.epoch_b.markers_url
          ),
        ]);
        if (cancelled) return;
        setMarkersA(mA.markers);
        setMarkersB(mB.markers);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setPairError(
            err instanceof ApiError ? err.message : "Unexpected error"
          );
        }
      })
      .finally(() => {
        if (!cancelled) setPairLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [epochA, epochB]);

  function swapEpochs() {
    setEpochA(epochB);
    setEpochB(epochA);
  }

  // Bands actually present in the loaded observations (never invented)
  const availableBands = useMemo(() => {
    if (!observations) return [];
    const seen = new Map<number, string>();
    for (const o of observations) {
      if (o.detector !== null && o.detector !== undefined) {
        seen.set(o.detector, detectorLabel(o.detector));
      }
    }
    return [...seen.entries()];
  }, [observations]);

  const fieldCandidateIds = useMemo(() => {
    const ids = new Set<string>();
    markersA.forEach((m) => ids.add(m.candidate_id));
    markersB.forEach((m) => ids.add(m.candidate_id));
    return ids;
  }, [markersA, markersB]);

  const fieldCandidates = useMemo(() => {
    if (!candidates) return [];
    return candidates.filter((c) => fieldCandidateIds.has(c.candidate_id));
  }, [candidates, fieldCandidateIds]);

  if (loading) {
    return (
      <LoadingState label="Loading observations…" />
    );
  }

  if (loadError || !observations || !candidates) {
    return (
      <ErrorState message={loadError ?? "Could not load observations."} />
    );
  }

  return (
    <>
      <p className="section-note">
        Compare real SPHEREx sky observations across epochs and inspect
        apparent change. Live data from <code>GET /api/observations</code>{" "}
        and <code>GET /api/compare/*</code>.
      </p>

      <div className="compare-controls">
        <label className="control-field">
          <span>Observation A</span>
          <select
            value={epochA}
            onChange={(e) => setEpochA(e.target.value as EpochLabel)}
          >
            {observations.map((o) => (
              <option key={o.epoch} value={o.epoch} disabled={o.epoch === epochB}>
                Epoch {o.epoch} — {o.date_obs?.slice(0, 10) ?? "unknown date"}
              </option>
            ))}
          </select>
        </label>

        <button
          type="button"
          className="btn btn-secondary swap-btn"
          onClick={swapEpochs}
          title="Swap Observation A and B"
        >
          ⇄ Swap
        </button>

        <label className="control-field">
          <span>Observation B</span>
          <select
            value={epochB}
            onChange={(e) => setEpochB(e.target.value as EpochLabel)}
          >
            {observations.map((o) => (
              <option key={o.epoch} value={o.epoch} disabled={o.epoch === epochA}>
                Epoch {o.epoch} — {o.date_obs?.slice(0, 10) ?? "unknown date"}
              </option>
            ))}
          </select>
        </label>

        <label className="control-field">
          <span>Band</span>
          <select disabled value={availableBands[0]?.[0] ?? ""}>
            {availableBands.length === 0 && <option>No band data</option>}
            {availableBands.map(([detector, label]) => (
              <option key={detector} value={detector}>
                {label}
              </option>
            ))}
          </select>
        </label>
      </div>
      {availableBands.length <= 1 && (
        <p className="section-note band-note">
          Only one detector/band was downloaded for this project (
          {availableBands[0]?.[1] ?? "none"}); the band selector reflects
          the real available data only.
        </p>
      )}

      <ModeTabs mode={mode} onChange={onModeChange} />

      {pairLoading && <LoadingState label="Loading comparison…" />}
      {!pairLoading && pairError && <ErrorState message={pairError} />}

      {!pairLoading && !pairError && pair && (
        <>
          {!pair.pixel_aligned && (
            <p className="alignment-note">{pair.alignment_note}</p>
          )}

          <div className="compare-layout">
            <div className="compare-viewer">
              {mode === "side-by-side" && (
                <div className="side-by-side-grid">
                  <ObservationPanel side={pair.epoch_a} markers={markersA} />
                  <ObservationPanel side={pair.epoch_b} markers={markersB} />
                </div>
              )}

              {mode === "slider" && (
                <SliderCompare
                  epochA={pair.epoch_a}
                  epochB={pair.epoch_b}
                  markersA={markersA}
                  markersB={markersB}
                />
              )}

              {mode === "blink" && (
                <BlinkCompare
                  epochA={pair.epoch_a}
                  epochB={pair.epoch_b}
                  markersA={markersA}
                  markersB={markersB}
                />
              )}

              {mode === "difference" && (
                <DifferenceView
                  available={pair.difference_available}
                  previewUrl={pair.difference_preview_url}
                  epochA={pair.epoch_a.epoch}
                  epochB={pair.epoch_b.epoch}
                />
              )}

              {mode === "overlay" && (
                <OverlayCanvas
                  epochA={pair.epoch_a}
                  epochB={pair.epoch_b}
                  markers={markersA}
                />
              )}
            </div>

            <FieldCandidatePanel candidates={fieldCandidates} />
          </div>
        </>
      )}

      <p className="disclaimer">
        Markers show preliminary, unconfirmed three-epoch motion candidates.
        Apparent change shown here is not a confirmed discovery.
      </p>
    </>
  );
}
