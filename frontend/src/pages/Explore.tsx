import { useEffect, useMemo, useState } from "react";
import type { CSSProperties } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, ApiError, imageUrl } from "../api/client";
import type {
  CandidateMarker,
  SixMonthCompareResponse,
  TwoEpochCandidate,
} from "../api/types";
import { LoadingState } from "../components/LoadingState";
import { ErrorState } from "../components/ErrorState";
import { ZoomPanViewer } from "../components/explore/ZoomPanViewer";
import { ExploreMarkerOverlay } from "../components/explore/ExploreMarkerOverlay";
import { SelectedCandidatePanel } from "../components/explore/SelectedCandidatePanel";
import { PageIntro } from "../components/ui/PageIntro";
import { InfoTooltip } from "../components/ui/InfoTooltip";
import { EmptyStateCard } from "../components/ui/EmptyStateCard";
import { fmt, longDate } from "../components/candidate/candidateFormat";

type Image = "earlier" | "later";

/** Explore one of the two real observations of the ~6-month pair in
 * detail, with the two-epoch candidate markers. ?image=later and
 * ?candidate=SX6M-001 pre-select a date and a marker. */
export function Explore() {
  const [searchParams, setSearchParams] = useSearchParams();
  const image: Image = searchParams.get("image") === "later" ? "later" : "earlier";

  const [pair, setPair] = useState<SixMonthCompareResponse | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [markers, setMarkers] = useState<Record<Image, CandidateMarker[]> | null>(null);
  const [outside, setOutside] = useState<string[]>([]);
  const [candidates, setCandidates] = useState<TwoEpochCandidate[]>([]);
  const [markersError, setMarkersError] = useState<string | null>(null);

  const [selectedId, setSelectedId] = useState<string | null>(() =>
    searchParams.get("candidate")?.toUpperCase() ?? null
  );

  useEffect(() => {
    let cancelled = false;
    api
      .getSixMonthCompare()
      .then((res) => {
        if (!cancelled) setPair(res);
      })
      .catch((err: unknown) => {
        if (!cancelled) setLoadError(err instanceof ApiError ? err.message : "Unexpected error");
      });
    Promise.all([
      api.getCandidateMarkers("earlier"),
      api.getCandidateMarkers("later"),
      api.getCandidates(),
    ])
      .then(([earlier, later, list]) => {
        if (cancelled) return;
        setMarkers({ earlier: earlier.markers, later: later.markers });
        setOutside(earlier.outside_display);
        setCandidates(list.candidates);
      })
      .catch((err: unknown) => {
        if (!cancelled) setMarkersError(err instanceof ApiError ? err.message : "Unexpected error");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  function selectImage(next: Image) {
    const params: Record<string, string> = {};
    if (next === "later") params.image = "later";
    if (selectedId) params.candidate = selectedId;
    setSearchParams(params, { replace: true });
  }

  const selected = useMemo(
    () => candidates.find((c) => c.candidate_id === selectedId) ?? null,
    [candidates, selectedId]
  );

  if (loadError) {
    return (
      <div className="page explore-page">
        <ErrorState message={loadError} />
      </div>
    );
  }
  if (!pair) {
    return (
      <div className="page explore-page">
        <LoadingState label="Loading the observations…" />
      </div>
    );
  }

  const side = image === "earlier" ? pair.epoch_a : pair.epoch_b;
  const obs = side.observation;
  const dates: Record<Image, string> = {
    earlier: longDate(pair.epoch_a.observation?.date_obs),
    later: longDate(pair.epoch_b.observation?.date_obs),
  };
  const shown = markers?.[image] ?? [];
  const frameStyle = {
    "--frame-aspect": `${pair.display_region.width} / ${pair.display_region.height}`,
  } as CSSProperties;

  return (
    <div className="page explore-page">
      <PageIntro
        eyebrow="SPHEREx · One observation at a time"
        title="Explore"
        lead="Inspect either real observation in detail."
        what="Shows one of the two real SPHEREx images of this sky: June 19, 2025 (earlier) or December 17, 2025 (later)."
        how="Choose a date, then scroll to zoom and drag to pan. Click a marker to inspect a two-epoch candidate."
        result="Markers show preliminary two-epoch candidates that passed the current checks — never confirmed moving objects."
      />

      <div className="dataset-tabs" role="tablist" aria-label="Observation date">
        {(["earlier", "later"] as const).map((key) => (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={image === key}
            className={image === key ? "dataset-tab dataset-tab-active" : "dataset-tab"}
            onClick={() => selectImage(key)}
          >
            <span className="dataset-tab-title">{dates[key]}</span>
            <span className="dataset-tab-sub">
              {key === "earlier" ? "Earlier observation" : "Later observation"}
            </span>
          </button>
        ))}
      </div>

      <div className="compare-layout compare-layout-wide">
        <div className="compare-viewer compare-viewer-wide" style={frameStyle}>
          <div className="obs-panel">
            <div className="obs-panel-header">
              <span className="obs-epoch-chip">
                {image === "earlier" ? "Earlier" : "Later"} observation · {dates[image]}
              </span>
              <span className="obs-panel-meta">
                ≈{side.wavelength_um.toFixed(2)} µm · detector D{obs?.detector ?? "—"}
              </span>
            </div>

            <ZoomPanViewer>
              <div className="obs-image-frame explore-frame">
                <img
                  src={imageUrl(side.preview_url)}
                  alt={`SPHEREx sky image taken ${dates[image]}`}
                  className="obs-image"
                  draggable={false}
                  crossOrigin="anonymous"
                />
                <ExploreMarkerOverlay markers={shown} selectedId={selectedId} onSelect={setSelectedId} />
              </div>
            </ZoomPanViewer>

            <div className="obs-panel-footer">
              <span>Scroll to zoom · drag to pan</span>
              <span>
                Frame center: RA {fmt(obs?.ra_center_deg, 3)}° · Dec {fmt(obs?.dec_center_deg, 3)}°
                <InfoTooltip term="skyCoordinates" />
              </span>
            </div>
          </div>

          {!markers && !markersError && <LoadingState label="Loading candidate markers…" />}
          {markersError && <ErrorState message={`Candidate markers are unavailable: ${markersError}`} />}
          {markers && shown.length > 0 && (
            <p className="section-note">
              {shown.length} two-epoch candidate{shown.length === 1 ? "" : "s"} marked. Solid ring:
              seen in this image; dashed ring: seen only in the other image. Click a marker to
              inspect it.
            </p>
          )}
          {markers && outside.length > 0 && (
            <p className="section-note">
              {outside.length} more candidate{outside.length === 1 ? " lies" : "s lie"} just outside
              this frame, near the edge of the area both images cover (
              {outside.map((id, i) => (
                <span key={id}>
                  {i > 0 && ", "}
                  <Link to={`/candidates/${encodeURIComponent(id)}`}>{id}</Link>
                </span>
              ))}
              ).
            </p>
          )}
        </div>

        <div className="explore-side">
          {markers && shown.length === 0 ? (
            <EmptyStateCard
              title="No current two-epoch candidates appear in this view."
              actions={
                <>
                  <Link to="/candidates" className="btn btn-secondary">
                    See the candidate results
                  </Link>
                  <Link to="/compare" className="btn btn-secondary">
                    Compare both dates
                  </Link>
                </>
              }
            >
              <p>You can still browse the image: scroll to zoom in and drag to move around.</p>
            </EmptyStateCard>
          ) : (
            <SelectedCandidatePanel candidate={selected} />
          )}
        </div>
      </div>

      <p className="disclaimer">
        Real SPHEREx data. Markers show preliminary two-epoch candidates, not
        confirmed moving objects or discoveries.
      </p>
    </div>
  );
}
