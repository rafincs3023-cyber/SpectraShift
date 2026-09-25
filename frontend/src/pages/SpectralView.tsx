import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  getSpectralMetadata,
  getSpectrum,
  isPreviewLoaded,
  loadPreview,
  spectralPreviewUrl,
  SpectralApiError,
  type SpectralMetadata,
  type SpectrumQuery,
  type SpectrumResponse,
} from "../api/spectral";
import { LoadingState } from "../components/LoadingState";
import { ErrorState } from "../components/ErrorState";
import { ChannelControls, ChannelInfo } from "../components/spectral/ChannelControls";
import { SpectralImageViewer } from "../components/spectral/SpectralImageViewer";
import { SpectralSpectrumChart } from "../components/spectral/SpectralSpectrumChart";
import { SelectedPositionPanel } from "../components/spectral/SelectedPositionPanel";
import { WavelengthBar } from "../components/spectral/WavelengthBar";
import { detectorRanges, type PixelPick } from "../components/spectral/spectralUtils";
import { PageIntro } from "../components/ui/PageIntro";
import { InfoTooltip } from "../components/ui/InfoTooltip";
import { TechnicalDetails } from "../components/ui/TechnicalDetails";
import { EmptyStateCard } from "../components/ui/EmptyStateCard";

// Wait this long after the last channel change before requesting a preview
// that isn't already loaded, so dragging the slider across many channels
// doesn't fire a request for every channel passed over.
const PREVIEW_DEBOUNCE_MS = 140;
const URL_SYNC_MS = 300;

function errorMessage(err: unknown): string {
  if (err instanceof SpectralApiError) {
    if (err.code === "spectral_data_missing") {
      return `The SPHEREx mosaic files are not available on the server: ${err.message}`;
    }
    return err.message;
  }
  return err instanceof Error ? err.message : "Unexpected error";
}

function parseChannelParam(raw: string | null): { channel: number; invalid: string | null } {
  if (raw === null) return { channel: 1, invalid: null };
  const n = Number(raw);
  if (Number.isInteger(n) && n >= 1) return { channel: n, invalid: null };
  return { channel: 1, invalid: raw };
}

export function SpectralView() {
  const [searchParams, setSearchParams] = useSearchParams();

  const [metadata, setMetadata] = useState<SpectralMetadata | null>(null);
  const [metaError, setMetaError] = useState<string | null>(null);
  const [metaAttempt, setMetaAttempt] = useState(0);

  // Channel lives in local state for responsive slider dragging and is
  // mirrored to ?channel= (debounced) so a view can be shared/bookmarked.
  const [initial] = useState(() => parseChannelParam(searchParams.get("channel")));
  const [channel, setChannel] = useState(initial.channel);
  const [channelNotice, setChannelNotice] = useState<string | null>(
    initial.invalid !== null ? `"${initial.invalid}" is not a valid channel; showing channel 1.` : null
  );

  const [shownChannel, setShownChannel] = useState<number | null>(null);
  const [previewError, setPreviewError] = useState<{ channel: number; message: string } | null>(null);
  const [previewAttempt, setPreviewAttempt] = useState(0);

  const [pendingPick, setPendingPick] = useState<PixelPick | null>(null);
  const [spectrum, setSpectrum] = useState<SpectrumResponse | null>(null);
  const [spectrumLoading, setSpectrumLoading] = useState(false);
  const [spectrumError, setSpectrumError] = useState<string | null>(null);
  const spectrumAbort = useRef<AbortController | null>(null);

  const total = metadata?.total_channels ?? 0;

  // Metadata: fetched once per session (cached in api/spectral.ts).
  useEffect(() => {
    let cancelled = false;
    getSpectralMetadata()
      .then((m) => {
        if (cancelled) return;
        setMetadata(m);
        setMetaError(null);
        // A ?channel= beyond the real channel count is rejected here.
        if (initial.channel > m.total_channels) {
          setChannel(1);
          setChannelNotice(
            `Channel ${initial.channel} does not exist (there are ${m.total_channels}); showing channel 1.`
          );
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) setMetaError(errorMessage(err));
      });
    return () => {
      cancelled = true;
    };
  }, [metaAttempt, initial.channel]);

  // Preview for the selected channel. The previous image stays on screen
  // (with a loading badge) until the new one has fully loaded.
  useEffect(() => {
    if (!metadata) return;
    let cancelled = false;
    const timer = window.setTimeout(
      () => {
        loadPreview(channel)
          .then(() => {
            if (cancelled) return;
            setShownChannel(channel);
            setPreviewError(null);
            // Warm the neighbours so Prev/Next feel instant.
            for (const n of [channel + 1, channel - 1]) {
              if (n >= 1 && n <= metadata.total_channels) loadPreview(n).catch(() => {});
            }
          })
          .catch((err: unknown) => {
            if (!cancelled) setPreviewError({ channel, message: errorMessage(err) });
          });
      },
      isPreviewLoaded(channel) ? 0 : PREVIEW_DEBOUNCE_MS
    );
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [channel, metadata, previewAttempt]);

  // Mirror the channel into the URL without flooding history.
  useEffect(() => {
    const t = window.setTimeout(() => {
      if (searchParams.get("channel") !== String(channel)) {
        setSearchParams({ channel: String(channel) }, { replace: true });
      }
    }, URL_SYNC_MS);
    return () => window.clearTimeout(t);
  }, [channel, searchParams, setSearchParams]);

  const goTo = (n: number) => {
    if (!total) return;
    setChannel(Math.min(total, Math.max(1, Math.round(n))));
    setChannelNotice(null);
  };
  // ← / → step through channels (ignored while typing in a field).
  useEffect(() => {
    if (!total) return;
    function onKey(e: KeyboardEvent) {
      const tag = (e.target as HTMLElement | null)?.tagName;
      if (tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA" || e.altKey || e.ctrlKey || e.metaKey) return;
      const step = e.key === "ArrowLeft" ? -1 : e.key === "ArrowRight" ? 1 : 0;
      if (!step) return;
      e.preventDefault();
      setChannel((c) => Math.min(total, Math.max(1, c + step)));
      setChannelNotice(null);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [total]);

  function requestSpectrum(query: SpectrumQuery, pick: PixelPick | null) {
    spectrumAbort.current?.abort();
    const ctrl = new AbortController();
    spectrumAbort.current = ctrl;
    setPendingPick(pick);
    setSpectrumLoading(true);
    setSpectrumError(null);
    getSpectrum(query, ctrl.signal)
      .then((res) => {
        if (ctrl.signal.aborted) return;
        setSpectrum(res);
        setPendingPick(null);
      })
      .catch((err: unknown) => {
        if (ctrl.signal.aborted) return;
        setPendingPick(null);
        setSpectrumError(
          err instanceof SpectralApiError && err.code === "outside_footprint"
            ? `That position is outside this mosaic. ${footprintHint ?? ""}`.trim()
            : `Could not read the spectrum: ${errorMessage(err)}`
        );
      })
      .finally(() => {
        if (!ctrl.signal.aborted) setSpectrumLoading(false);
      });
  }

  function clearSelection() {
    spectrumAbort.current?.abort();
    setSpectrum(null);
    setSpectrumError(null);
    setSpectrumLoading(false);
    setPendingPick(null);
  }

  const detectors = metadata ? detectorRanges(metadata.channels) : [];
  const footprintHint = metadata ? describeFootprint(metadata) : null;

  if (metaError) {
    return (
      <div className="page">
        <SpectralHeader />
        <ErrorState
          message={metaError}
          onRetry={() => {
            setMetaError(null);
            setMetaAttempt((n) => n + 1);
          }}
        />
      </div>
    );
  }

  if (!metadata) {
    return (
      <div className="page">
        <SpectralHeader />
        <LoadingState label="Loading the 102-wavelength sky image…" />
      </div>
    );
  }

  const info = metadata.channels.find((c) => c.channel === channel) ?? metadata.channels[0];
  const wlMin = metadata.wavelength_range_um.min ?? 0.75;
  const wlMax = metadata.wavelength_range_um.max ?? 5.0;
  const previewFailed = previewError?.channel === channel ? previewError.message : null;
  const marker = pendingPick
    ? {
        xFrac: (pendingPick.x + 0.5) / metadata.image.width,
        yFrac: 1 - (pendingPick.y + 0.5) / metadata.image.height,
        pending: true,
      }
    : spectrum
      ? { xFrac: spectrum.pixel.x_frac, yFrac: spectrum.pixel.y_frac, pending: false }
      : null;

  return (
    <div className="page spectral-page">
      <SpectralHeader />

      <div className="spectral-mode-compare">
        <div className="spectral-mode spectral-mode-active">
          <strong>Spectral View · you are here</strong>
          <span>Same sky, same moment, {metadata.total_channels} different wavelengths.</span>
        </div>
        <Link to="/compare" className="spectral-mode">
          <strong>Time Compare →</strong>
          <span>Same sky about six months apart (Jun 19 → Dec 17, 2025), to look for changes over time.</span>
        </Link>
      </div>

      <section className="card spectral-channel-card" aria-label="Choose a wavelength">
        <div className="spectral-channel-top">
          <div>
            <p className="eyebrow spectral-eyebrow">Choose a wavelength (this changes colour, not time)</p>
            <p className="spectral-channel-title">
              Wavelength <strong>{info.wavelength_um?.toFixed(3) ?? "—"} µm</strong>
              <InfoTooltip term="wavelength" />
              <span className="spectral-channel-sub">
                {" "}· channel {channel} of {metadata.total_channels}
                <InfoTooltip term="channel" />
              </span>
            </p>
          </div>
          <span className="section-note spectral-keys">Tip: use the ← / → keys to step through wavelengths</span>
        </div>
        <WavelengthBar
          channels={metadata.channels}
          selected={info}
          rangeMin={wlMin}
          rangeMax={wlMax}
          onSelect={goTo}
        />
        <ChannelControls channel={channel} total={metadata.total_channels} onChange={goTo} />
        {channelNotice && <p className="spectral-inline-error">{channelNotice}</p>}
      </section>

      <div className="compare-layout spectral-layout">
        <div className="compare-viewer">
          <div className="obs-panel">
            <div className="obs-panel-header">
              <span className="obs-epoch-chip">{info.wavelength_um?.toFixed(3) ?? "—"} µm</span>
              <span className="obs-panel-meta">
                Channel {channel} · detector D{info.detector ?? "—"}
              </span>
            </div>
            <SpectralImageViewer
              src={shownChannel === null ? null : spectralPreviewUrl(shownChannel)}
              channel={channel}
              wavelengthUm={info.wavelength_um}
              mosaicWidth={metadata.image.width}
              mosaicHeight={metadata.image.height}
              loading={shownChannel !== channel}
              error={previewFailed}
              onRetry={() => {
                setPreviewError(null);
                setPreviewAttempt((n) => n + 1);
              }}
              marker={marker}
              onPick={(pick) => requestSpectrum({ x: pick.x, y: pick.y }, pick)}
              onPickOutside={() => setSpectrumError("That click was outside the image. Click on the mosaic itself.")}
            />
            <div className="obs-panel-footer">
              <span>Click any point to see its spectrum</span>
              <span>North up · East left</span>
            </div>
          </div>
          <p className="section-note">
            Brighter means more infrared light at this wavelength. Dark or
            transparent areas have no data at this wavelength.
          </p>
          <TechnicalDetails summary="Technical details about this image">
            <p>
              Mosaic size {metadata.image.width} × {metadata.image.height} pixels,{" "}
              {metadata.image.pixel_scale_arcsec[0]?.toFixed(2) ?? "—"}″ per pixel; brightness
              unit {metadata.image.unit ?? "—"}.
            </p>
            <p>
              Display only: each wavelength is shown with an asinh stretch between
              the 0.5th and 99.5th brightness percentiles of that channel. Spectra
              are read from the full-precision data, not from this picture.
            </p>
          </TechnicalDetails>
        </div>

        <aside className="spectral-side">
          <div className="card spectral-side-card">
            <h2>This wavelength</h2>
            <ChannelInfo info={info} total={metadata.total_channels} />
          </div>
          <SelectedPositionPanel
            spectrum={spectrum}
            loading={spectrumLoading}
            error={spectrumError}
            selectedChannel={channel}
            footprintHint={footprintHint}
            onLookup={(ra, dec) => requestSpectrum({ ra, dec }, null)}
            onClear={clearSelection}
          />
        </aside>
      </div>

      <section className="card spectral-spectrum-card" aria-label="Spectrum of the selected point">
        <div className="spectral-side-head">
          <h2>
            Spectrum of the selected point
            <InfoTooltip term="spectrum" />
          </h2>
          {spectrum && (
            <span className="section-note">
              RA {spectrum.pixel_center.ra_deg?.toFixed(4)}°, Dec {spectrum.pixel_center.dec_deg?.toFixed(4)}°
            </span>
          )}
        </div>
        <p className="section-note spectral-chart-intro">
          This chart shows how bright the selected sky point is at each
          wavelength, from {wlMin.toFixed(2)} µm (left) to {wlMax.toFixed(2)} µm (right).
        </p>

        {!spectrum && !spectrumLoading && (
          <EmptyStateCard title="Click any point in the image to plot its spectrum.">
            <p>
              Try a bright star first: stars and galaxies usually have smooth
              spectra, while dust and gas can show bumps at particular
              wavelengths. You can also enter sky coordinates in the panel on
              the right.
            </p>
          </EmptyStateCard>
        )}
        {!spectrum && spectrumLoading && <LoadingState label="Reading all 102 wavelengths at this point…" />}

        {spectrum && (
          <>
            {!spectrum.has_data && (
              <p className="spectral-inline-error">
                This point has no data at any of the {spectrum.n_channels} wavelengths, so there is nothing to plot. Try a point inside the image.
              </p>
            )}
            <SpectralSpectrumChart
              samples={spectrum.samples}
              selectedChannel={channel}
              unit={spectrum.unit}
              wlMin={wlMin}
              wlMax={wlMax}
              detectors={detectors}
              onSelectChannel={goTo}
            />
            <p className="section-note">
              How to read it: each dot is one wavelength. Higher dots mean a
              brighter point. Hover a dot to read its value; click the chart to
              show that wavelength in the image. The shaded bands are SPHEREx's
              six detectors (D1–D6)<InfoTooltip term="detector" />.
            </p>
            <TechnicalDetails summary="Technical details about this spectrum">
              <p>
                Each value is the single nearest mosaic pixel (x {spectrum.pixel.x_index}, y{" "}
                {spectrum.pixel.y_index}) in one channel, in {spectrum.unit}; nothing is
                interpolated or smoothed. Data present in {spectrum.n_valid} of{" "}
                {spectrum.n_channels} channels; missing values are shown as gaps, never as zero.
              </p>
            </TechnicalDetails>
            <details className="spectral-table-toggle">
              <summary>Show all {spectrum.n_channels} values as a table</summary>
              <div className="table-scroll">
                <table className="data-table spectrum-table">
                  <thead>
                    <tr>
                      <th>Channel</th>
                      <th>
                        Wavelength <span className="unit-case">(µm)</span>
                      </th>
                      <th>Detector</th>
                      <th>
                        Brightness <span className="unit-case">({spectrum.unit})</span>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {spectrum.samples.map((s) => (
                      <tr key={s.channel} className={s.channel === channel ? "spectral-row-selected" : undefined}>
                        <td data-label="Channel">{s.channel}</td>
                        <td data-label="Wavelength (µm)">{s.wavelength_um?.toFixed(3) ?? "—"}</td>
                        <td data-label="Detector">{s.detector ?? "—"}</td>
                        <td data-label="Brightness">{s.value === null ? "no data" : s.value.toPrecision(5)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
          </>
        )}
      </section>

      <p className="disclaimer">
        Real SPHEREx data. Changing the wavelength does not change the time of
        the observation, so differences between wavelengths are not motion.
      </p>
    </div>
  );
}

function describeFootprint(metadata: SpectralMetadata): string | null {
  const corners = metadata.image.corners;
  const ras = corners.map((c) => c.ra_deg).filter((v): v is number => v !== null);
  const decs = corners.map((c) => c.dec_deg).filter((v): v is number => v !== null);
  if (ras.length < 4 || decs.length < 4) return null;
  return (
    `This mosaic covers roughly RA ${Math.min(...ras).toFixed(1)}°–${Math.max(...ras).toFixed(1)}°, ` +
    `Dec ${Math.min(...decs).toFixed(1)}° to ${Math.max(...decs).toFixed(1)}°.`
  );
}

function SpectralHeader() {
  return (
    <PageIntro
      eyebrow="SPHEREx · 102 infrared wavelengths"
      title="Spectral View"
      lead="See the same patch of sky across 102 infrared wavelengths."
      what="Shows one sky region at 102 wavelengths — the same moment, seen in different “colours” of infrared light."
      how="Move through wavelengths with the slider or arrow keys, then click the image to pick a point."
      result="The chart shows how bright that point is at each wavelength (its spectrum). This page changes wavelength, not observation time."
    />
  );
}
