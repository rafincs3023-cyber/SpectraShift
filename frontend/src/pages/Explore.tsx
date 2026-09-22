import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api, ApiError, imageUrl } from "../api/client";
import type {
  CandidateDetail,
  CandidateMarker,
  CandidateSpectrumResponse,
  EpochLabel,
  Observation,
} from "../api/types";
import { LoadingState } from "../components/LoadingState";
import { ErrorState } from "../components/ErrorState";
import { ZoomPanViewer } from "../components/explore/ZoomPanViewer";
import { ExploreMarkerOverlay } from "../components/explore/ExploreMarkerOverlay";
import { SelectedSourcePanel } from "../components/explore/SelectedSourcePanel";

function detectorLabel(detector: number | null | undefined): string {
  if (detector === null || detector === undefined) return "Unknown";
  const band = detector <= 3 ? "SWIR" : "MWIR";
  return `Detector ${detector} (${band})`;
}

function fmt(value: number | null | undefined, digits = 3): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return value.toFixed(digits);
}

export function Explore() {
  const [searchParams] = useSearchParams();

  const [observations, setObservations] = useState<Observation[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const [epoch, setEpoch] = useState<EpochLabel>("A");

  const [markers, setMarkers] = useState<CandidateMarker[]>([]);
  const [markersError, setMarkersError] = useState<string | null>(null);
  const [markersLoading, setMarkersLoading] = useState(true);

  // Pre-selects a candidate when arriving from a "Inspect in Explore" link
  // (e.g. /explore?candidate=3EPOCH-001) such as the one on the Candidate
  // Detail page. Read once on mount; the URL isn't kept in sync after that.
  const [selectedId, setSelectedId] = useState<string | null>(() =>
    searchParams.get("candidate")
  );
  const [selectedDetail, setSelectedDetail] = useState<CandidateDetail | null>(null);
  const [selectedSpectrum, setSelectedSpectrum] = useState<CandidateSpectrumResponse | null>(null);
  const [selectedLoading, setSelectedLoading] = useState(false);
  const [selectedError, setSelectedError] = useState<string | null>(null);

  // Initial load: observation list
  useEffect(() => {
    setLoading(true);
    setLoadError(null);
    api
      .getObservations()
      .then((res) => setObservations(res.observations))
      .catch((err: unknown) =>
        setLoadError(err instanceof ApiError ? err.message : "Unexpected error")
      )
      .finally(() => setLoading(false));
  }, []);

  // Markers for the currently selected epoch
  useEffect(() => {
    let cancelled = false;
    setMarkersLoading(true);
    setMarkersError(null);

    api
      .getCandidateMarkers(epoch)
      .then((res) => {
        if (!cancelled) setMarkers(res.markers);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setMarkersError(
            err instanceof ApiError ? err.message : "Unexpected error"
          );
        }
      })
      .finally(() => {
        if (!cancelled) setMarkersLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [epoch]);

  // Selected candidate detail + spectrum
  useEffect(() => {
    if (!selectedId) {
      setSelectedDetail(null);
      setSelectedSpectrum(null);
      setSelectedError(null);
      return;
    }

    let cancelled = false;
    setSelectedLoading(true);
    setSelectedError(null);

    Promise.all([
      api.getCandidate(selectedId),
      api.getCandidateSpectrum(selectedId),
    ])
      .then(([detail, spectrumRes]) => {
        if (cancelled) return;
        setSelectedDetail(detail);
        setSelectedSpectrum(spectrumRes);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setSelectedError(
            err instanceof ApiError ? err.message : "Unexpected error"
          );
        }
      })
      .finally(() => {
        if (!cancelled) setSelectedLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [selectedId]);

  const activeObservation = useMemo(
    () => observations?.find((o) => o.epoch === epoch) ?? null,
    [observations, epoch]
  );

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

  if (loading) {
    return (
      <div className="page">
        <LoadingState label="Loading observations…" />
      </div>
    );
  }

  if (loadError || !observations || observations.length === 0) {
    return (
      <div className="page">
        <ErrorState message={loadError ?? "No observations available."} />
      </div>
    );
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1>Sky Explorer</h1>
        <p className="page-subtitle">
          Browse a single SPHEREx epoch and inspect validated candidate
          sources directly on the sky. Live data from{" "}
          <code>GET /api/observations</code>,{" "}
          <code>GET /api/compare/candidate-markers</code>, and{" "}
          <code>GET /api/candidates/&#123;id&#125;/spectrum</code>.
        </p>
      </div>

      <div className="compare-controls">
        <label className="control-field">
          <span>Observation / Epoch</span>
          <select
            value={epoch}
            onChange={(e) => {
              setEpoch(e.target.value as EpochLabel);
              setSelectedId(null);
            }}
          >
            {observations.map((o) => (
              <option key={o.epoch} value={o.epoch}>
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

      <div className="compare-layout">
        <div className="compare-viewer">
          <div className="obs-panel">
            <div className="obs-panel-header">
              <span className="obs-epoch-chip">Epoch {epoch}</span>
              <span className="obs-panel-meta">
                {activeObservation?.date_obs?.slice(0, 10) ?? "—"} · MJD{" "}
                {fmt(activeObservation?.mjd_obs, 3)}
              </span>
            </div>

            <ZoomPanViewer>
              <div className="obs-image-frame explore-frame">
                <img
                  src={imageUrl(`/api/observations/${epoch}/preview`)}
                  alt={`SPHEREx sky image, Epoch ${epoch}`}
                  className="obs-image"
                  draggable={false}
                  crossOrigin="anonymous"
                />
                {!markersLoading && !markersError && (
                  <ExploreMarkerOverlay
                    markers={markers}
                    selectedId={selectedId}
                    onSelect={setSelectedId}
                  />
                )}
              </div>
            </ZoomPanViewer>

            <div className="obs-panel-footer">
              <span>Detector {activeObservation?.detector ?? "—"}</span>
              <span>
                RA {fmt(activeObservation?.ra_center_deg, 3)}° · Dec{" "}
                {fmt(activeObservation?.dec_center_deg, 3)}°
              </span>
            </div>
          </div>

          {markersLoading && <LoadingState label="Loading candidate markers…" />}
          {!markersLoading && markersError && <ErrorState message={markersError} />}
          {!markersLoading && !markersError && (
            <p className="section-note">
              {markers.length === 0
                ? "No validated candidates fall within this epoch's frame."
                : `${markers.length} candidate marker${
                    markers.length === 1 ? "" : "s"
                  } shown. Click one to inspect it.`}
            </p>
          )}
        </div>

        <SelectedSourcePanel
          epoch={epoch}
          loading={selectedLoading}
          error={selectedError}
          detail={selectedDetail}
          spectrum={selectedSpectrum}
        />
      </div>

      <p className="disclaimer">
        Markers show preliminary, unconfirmed three-epoch motion candidates.
        Apparent change shown here is not a confirmed discovery.
      </p>
    </div>
  );
}
