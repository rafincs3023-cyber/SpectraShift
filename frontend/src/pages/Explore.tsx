import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
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
import { PageIntro } from "../components/ui/PageIntro";
import { InfoTooltip } from "../components/ui/InfoTooltip";
import { EmptyStateCard } from "../components/ui/EmptyStateCard";

function detectorLabel(detector: number | null | undefined): string {
  if (detector === null || detector === undefined) return "Unknown";
  const band = detector <= 3 ? "short-wave infrared" : "mid-wave infrared";
  return `Detector ${detector} (${band})`;
}

function shortDate(iso: string | null | undefined): string {
  if (!iso) return "unknown date";
  const d = new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : `${iso}Z`);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" });
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
      <div className="page explore-page">
        <LoadingState label="Loading observations…" />
      </div>
    );
  }

  if (loadError || !observations || observations.length === 0) {
    return (
      <div className="page explore-page">
        <ErrorState message={loadError ?? "No observations are available right now."} />
      </div>
    );
  }

  return (
    <div className="page explore-page">
      <PageIntro
        eyebrow="SPHEREx · One observation"
        title="Explore"
        lead="Browse one observation and inspect interesting sky sources."
        what="Shows one real SPHEREx image of the sky, taken on a single date."
        how="Choose a date, then scroll to zoom and drag to pan. If markers appear, click one to inspect it."
        result="Markers show possible moving objects that passed every check. If no markers appear, nothing in this image passed those checks."
      />

      <div className="compare-controls">
        <label className="control-field">
          <span>
            Observation date
            <InfoTooltip term="observationDate" />
          </span>
          <select
            value={epoch}
            onChange={(e) => {
              setEpoch(e.target.value as EpochLabel);
              setSelectedId(null);
            }}
          >
            {observations.map((o) => (
              <option key={o.epoch} value={o.epoch}>
                {shortDate(o.date_obs)} (Epoch {o.epoch})
              </option>
            ))}
          </select>
        </label>

        <label className="control-field">
          <span>
            Wavelength band
            <InfoTooltip term="detector" />
          </span>
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
          Only one wavelength band is available for these images (
          {availableBands[0]?.[1] ?? "none"}). For all 102 wavelengths, use
          the Spectral View.
        </p>
      )}

      <div className="compare-layout">
        <div className="compare-viewer">
          <div className="obs-panel">
            <div className="obs-panel-header">
              <span className="obs-epoch-chip">{shortDate(activeObservation?.date_obs)}</span>
              <span className="obs-panel-meta">
                Epoch {epoch} · MJD {fmt(activeObservation?.mjd_obs, 3)}
              </span>
            </div>

            <ZoomPanViewer>
              <div className="obs-image-frame explore-frame">
                <img
                  src={imageUrl(`/api/observations/${epoch}/preview`)}
                  alt={`SPHEREx sky image taken ${shortDate(activeObservation?.date_obs)}`}
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
              <span>Scroll to zoom · drag to pan</span>
              <span>
                Image reference point: RA {fmt(activeObservation?.ra_center_deg, 3)}° · Dec{" "}
                {fmt(activeObservation?.dec_center_deg, 3)}°
                <InfoTooltip term="skyCoordinates" />
              </span>
            </div>
          </div>

          {markersLoading && <LoadingState label="Checking for moving-object markers…" />}
          {!markersLoading && markersError && <ErrorState message={markersError} />}
          {!markersLoading && !markersError && markers.length > 0 && (
            <p className="section-note">
              {markers.length} possible moving object{markers.length === 1 ? "" : "s"} marked.
              Click a marker to inspect it.
            </p>
          )}
        </div>

        <div className="explore-side">
          <SelectedSourcePanel
            epoch={epoch}
            loading={selectedLoading}
            error={selectedError}
            detail={selectedDetail}
            spectrum={selectedSpectrum}
          />
          {!markersLoading && !markersError && markers.length === 0 && (
            <EmptyStateCard
              title="No validated moving-object markers appear in this view."
              actions={
                <>
                  <Link to="/candidates" className="btn btn-secondary">
                    Why are there no markers?
                  </Link>
                  <Link to="/spectral" className="btn btn-secondary">
                    Explore 102 wavelengths
                  </Link>
                </>
              }
            >
              <p>
                You can still browse the image: scroll to zoom in on the star
                field and drag to move around. Switch the date above to see the
                same field on another day.
              </p>
            </EmptyStateCard>
          )}
        </div>
      </div>

      <p className="disclaimer">
        Real SPHEREx data. Markers, when present, show possible moving objects,
        not confirmed discoveries.
      </p>
    </div>
  );
}
