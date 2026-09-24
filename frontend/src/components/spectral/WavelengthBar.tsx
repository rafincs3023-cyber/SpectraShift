import { useMemo, type MouseEvent } from "react";
import type { SpectralChannel } from "../../api/spectral";
import { detectorRanges } from "./spectralUtils";

// Keep the marker's label inside the bar near either end.
function edgeClass(fraction: number): string {
  if (fraction < 0.06) return "wl-bar-marker-label-start";
  if (fraction > 0.94) return "wl-bar-marker-label-end";
  return "";
}

/** Horizontal 0.75-5 µm scale showing where the selected channel sits in
 * SPHEREx's full wavelength coverage. Clicking picks the nearest channel. */
export function WavelengthBar({
  channels,
  selected,
  rangeMin,
  rangeMax,
  onSelect,
}: {
  channels: SpectralChannel[];
  selected: SpectralChannel;
  rangeMin: number;
  rangeMax: number;
  onSelect: (channel: number) => void;
}) {
  const detectors = useMemo(() => detectorRanges(channels), [channels]);
  const span = rangeMax - rangeMin;
  const pct = (um: number) => `${((um - rangeMin) / span) * 100}%`;
  const ticks = [1, 2, 3, 4, 5].filter((t) => t >= rangeMin && t <= rangeMax);

  function handleClick(e: MouseEvent<HTMLDivElement>) {
    const rect = e.currentTarget.getBoundingClientRect();
    const um = rangeMin + ((e.clientX - rect.left) / rect.width) * span;
    let best = selected;
    for (const c of channels) {
      if (c.wavelength_um === null) continue;
      if (Math.abs(c.wavelength_um - um) < Math.abs((best.wavelength_um ?? Infinity) - um)) best = c;
    }
    onSelect(best.channel);
  }

  const lo = selected.wavelength_min_um ?? selected.wavelength_um;
  const hi = selected.wavelength_max_um ?? selected.wavelength_um;

  return (
    <div className="wl-bar">
      <div
        className="wl-bar-track"
        onClick={handleClick}
        title="Click to jump to the nearest channel"
        role="presentation"
      >
        {detectors.map((d, i) => (
          <div
            key={d.detector}
            className={i % 2 === 0 ? "wl-bar-det" : "wl-bar-det wl-bar-det-alt"}
            style={{ left: pct(d.minUm), width: `calc(${pct(d.maxUm)} - ${pct(d.minUm)})` }}
          >
            <span>D{d.detector}</span>
          </div>
        ))}
        {lo !== null && hi !== null && (
          <div
            className="wl-bar-band"
            style={{ left: pct(lo), width: `max(3px, calc(${pct(hi)} - ${pct(lo)}))` }}
          />
        )}
        {selected.wavelength_um !== null && (
          <div className="wl-bar-marker" style={{ left: pct(selected.wavelength_um) }}>
            <span className={`wl-bar-marker-label ${edgeClass((selected.wavelength_um - rangeMin) / span)}`}>{selected.wavelength_um.toFixed(3)} µm</span>
          </div>
        )}
      </div>
      <div className="wl-bar-ticks" aria-hidden="true">
        {ticks.map((t) => (
          <span key={t} style={{ left: pct(t) }}>
            {t} µm
          </span>
        ))}
      </div>
      <div className="wl-bar-labels">
        <span>← shorter wavelength ({rangeMin.toFixed(2)} µm)</span>
        <span>longer wavelength ({rangeMax.toFixed(2)} µm) →</span>
      </div>
    </div>
  );
}
