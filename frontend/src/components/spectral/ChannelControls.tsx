import { useState } from "react";
import type { SpectralChannel } from "../../api/spectral";

function fmt(value: number | null | undefined, digits = 3): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return value.toFixed(digits);
}

/** Slider + previous/next + direct entry for channels 1..total. */
export function ChannelControls({
  channel,
  total,
  onChange,
}: {
  channel: number;
  total: number;
  onChange: (channel: number) => void;
}) {
  // Draft text for the number box; `null` means "show the current channel".
  const [draft, setDraft] = useState<string | null>(null);
  const [draftError, setDraftError] = useState<string | null>(null);

  function commit() {
    if (draft === null) return;
    const n = Number(draft.trim());
    if (!Number.isInteger(n) || n < 1 || n > total) {
      setDraftError(`Enter a whole number from 1 to ${total}.`);
      return;
    }
    setDraft(null);
    setDraftError(null);
    onChange(n);
  }

  return (
    <div className="channel-controls">
      <button
        type="button"
        className="btn btn-secondary channel-step"
        onClick={() => onChange(channel - 1)}
        disabled={channel <= 1}
        aria-label="Previous channel (shorter wavelength)"
      >
        ‹ Prev
      </button>

      <input
        type="range"
        className="channel-slider"
        min={1}
        max={total}
        step={1}
        value={channel}
        onChange={(e) => onChange(Number(e.target.value))}
        aria-label="Spectral channel"
        aria-valuetext={`Channel ${channel} of ${total}`}
      />

      <button
        type="button"
        className="btn btn-secondary channel-step"
        onClick={() => onChange(channel + 1)}
        disabled={channel >= total}
        aria-label="Next channel (longer wavelength)"
      >
        Next ›
      </button>

      <label className="channel-jump">
        <span>Go to channel</span>
        <input
          type="number"
          inputMode="numeric"
          min={1}
          max={total}
          value={draft ?? String(channel)}
          onChange={(e) => {
            setDraft(e.target.value);
            setDraftError(null);
          }}
          onBlur={commit}
          onKeyDown={(e) => {
            if (e.key === "Enter") commit();
            if (e.key === "Escape") {
              setDraft(null);
              setDraftError(null);
            }
          }}
          aria-invalid={draftError !== null}
        />
      </label>
      {draftError && <p className="channel-jump-error">{draftError}</p>}
    </div>
  );
}

export function ChannelInfo({
  info,
  total,
}: {
  info: SpectralChannel;
  total: number;
}) {
  return (
    <div className="channel-info">
      <div className="channel-info-headline">
        <span className="channel-info-number">
          Channel {info.channel} <span>/ {total}</span>
        </span>
        <span className="channel-info-wl">{fmt(info.wavelength_um)} µm</span>
      </div>
      <dl className="kv-list kv-list-compact">
        <div>
          <dt>Detector</dt>
          <dd>{info.detector ?? "—"}</dd>
        </div>
        <div>
          <dt>Subchannel</dt>
          <dd>{info.subchannel ?? "—"}</dd>
        </div>
        <div>
          <dt>Wavelength range</dt>
          <dd>
            {fmt(info.wavelength_min_um)} – {fmt(info.wavelength_max_um)} µm
          </dd>
        </div>
        <div>
          <dt>Bandwidth</dt>
          <dd>{fmt(info.bandwidth_um)} µm</dd>
        </div>
        <div>
          <dt>Sky coverage</dt>
          <dd>
            {info.coverage_fraction === null
              ? "—"
              : `${(info.coverage_fraction * 100).toFixed(2)}%`}
          </dd>
        </div>
        <div>
          <dt>Source</dt>
          <dd className="channel-info-source" title={info.source_file}>
            plane {info.source_plane} of {info.source_file.replace(/\.fits\.gz$/, "")}
          </dd>
        </div>
      </dl>
    </div>
  );
}
