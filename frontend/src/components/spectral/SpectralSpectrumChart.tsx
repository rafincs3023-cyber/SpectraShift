import { useMemo, useState, type MouseEvent } from "react";
import type { SpectralSample } from "../../api/spectral";
import type { DetectorRange } from "./spectralUtils";

const WIDTH = 760;
const HEIGHT = 300;
const M = { top: 24, right: 18, bottom: 44, left: 64 };
const IW = WIDTH - M.left - M.right;
const IH = HEIGHT - M.top - M.bottom;

function niceStep(span: number, count: number): number {
  const raw = span / Math.max(1, count);
  const mag = 10 ** Math.floor(Math.log10(raw));
  const norm = raw / mag;
  return (norm >= 5 ? 10 : norm >= 2 ? 5 : norm >= 1 ? 2 : 1) * mag;
}

function niceDomain(lo: number, hi: number): { domain: [number, number]; ticks: number[] } {
  if (lo === hi) {
    const pad = Math.abs(lo) * 0.1 || 1;
    lo -= pad;
    hi += pad;
  }
  const step = niceStep(hi - lo, 5);
  const d0 = Math.floor(lo / step) * step;
  const d1 = Math.ceil(hi / step) * step;
  const ticks: number[] = [];
  for (let t = d0; t <= d1 + step / 2; t += step) ticks.push(Number(t.toPrecision(12)));
  return { domain: [d0, d1], ticks };
}

function fmtValue(v: number): string {
  const a = Math.abs(v);
  if (a !== 0 && (a < 0.01 || a >= 1e4)) return v.toExponential(2);
  return v.toPrecision(3);
}

type Plotted = SpectralSample & { wavelength_um: number };

/** Surface brightness vs wavelength for all channels at one pixel. Null
 * samples break the line (a gap) and are marked on the baseline; they are
 * never drawn as zero or interpolated across. */
export function SpectralSpectrumChart({
  samples,
  selectedChannel,
  unit,
  wlMin,
  wlMax,
  detectors,
  onSelectChannel,
}: {
  samples: SpectralSample[];
  selectedChannel: number;
  unit: string | null;
  wlMin: number;
  wlMax: number;
  detectors: DetectorRange[];
  onSelectChannel: (channel: number) => void;
}) {
  const [hover, setHover] = useState<Plotted | null>(null);

  const plotted = useMemo(
    () => samples.filter((s): s is Plotted => s.wavelength_um !== null),
    [samples]
  );
  const valid = plotted.filter((s) => s.value !== null) as (Plotted & { value: number })[];

  const xDomain: [number, number] = [wlMin - 0.05, wlMax + 0.05];
  const x = (um: number) => ((um - xDomain[0]) / (xDomain[1] - xDomain[0])) * IW;

  const vals = valid.map((s) => s.value);
  const { domain: yDomain, ticks: yTicks } =
    vals.length === 0 ? niceDomain(0, 1) : niceDomain(Math.min(...vals), Math.max(...vals));
  const y = (v: number) => IH - ((v - yDomain[0]) / (yDomain[1] - yDomain[0])) * IH;

  // Consecutive valid samples form one path segment; a null ends it.
  const segments: string[] = [];
  let cur: string[] = [];
  for (const s of plotted) {
    if (s.value === null) {
      if (cur.length) segments.push(cur.join(" "));
      cur = [];
      continue;
    }
    cur.push(`${cur.length ? "L" : "M"}${x(s.wavelength_um).toFixed(2)},${y(s.value).toFixed(2)}`);
  }
  if (cur.length) segments.push(cur.join(" "));

  const selected = plotted.find((s) => s.channel === selectedChannel) ?? null;

  function nearest(e: MouseEvent<SVGRectElement>): Plotted | null {
    const rect = e.currentTarget.getBoundingClientRect();
    const um = xDomain[0] + ((e.clientX - rect.left) / rect.width) * (xDomain[1] - xDomain[0]);
    let best: Plotted | null = null;
    for (const s of plotted) {
      if (!best || Math.abs(s.wavelength_um - um) < Math.abs(best.wavelength_um - um)) best = s;
    }
    return best;
  }

  const tip = hover;
  const tipLeftPct = tip ? ((M.left + x(tip.wavelength_um)) / WIDTH) * 100 : 0;

  return (
    <div className="spectral-chart">
      <div className="spectral-chart-scroll">
        <div className="spectral-chart-plot">
          <svg
            viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
            className="spectrum-svg spectral-chart-svg"
            role="img"
            aria-label={`Spectrum: ${valid.length} valid samples from ${wlMin.toFixed(2)} to ${wlMax.toFixed(2)} µm`}
          >
            <g transform={`translate(${M.left},${M.top})`}>
              {detectors.map((d, i) => (
                <g key={d.detector}>
                  {i % 2 === 1 && (
                    <rect
                      x={x(d.minUm)}
                      y={0}
                      width={Math.max(0, x(d.maxUm) - x(d.minUm))}
                      height={IH}
                      className="spectral-chart-detband"
                    />
                  )}
                  <text x={(x(d.minUm) + x(d.maxUm)) / 2} y={-8} className="spectrum-tick" textAnchor="middle">
                    D{d.detector}
                  </text>
                </g>
              ))}

              {yTicks.map((t) => (
                <g key={`y${t}`}>
                  <line x1={0} x2={IW} y1={y(t)} y2={y(t)} className="spectrum-grid" />
                  <text x={-8} y={y(t)} className="spectrum-tick" textAnchor="end" dy="0.32em">
                    {fmtValue(t)}
                  </text>
                </g>
              ))}
              {[1, 2, 3, 4, 5].filter((t) => t >= xDomain[0] && t <= xDomain[1]).map((t) => (
                <text key={`x${t}`} x={x(t)} y={IH + 18} className="spectrum-tick" textAnchor="middle">
                  {t}
                </text>
              ))}
              <line x1={0} x2={IW} y1={IH} y2={IH} className="spectrum-axis" />
              <line x1={0} x2={0} y1={0} y2={IH} className="spectrum-axis" />

              {selected && (
                <g>
                  <line
                    x1={x(selected.wavelength_um)}
                    x2={x(selected.wavelength_um)}
                    y1={0}
                    y2={IH}
                    className="spectral-chart-selected-line"
                  />
                  <text
                    x={x(selected.wavelength_um)}
                    y={IH - 6}
                    dx={x(selected.wavelength_um) > IW - 80 ? -6 : 6}
                    textAnchor={x(selected.wavelength_um) > IW - 80 ? "end" : "start"}
                    className="spectral-chart-selected-label"
                  >
                    Ch {selected.channel}
                    {selected.value === null ? " · no data" : ""}
                  </text>
                </g>
              )}

              {segments.map((d, i) => (
                <path key={i} d={d} className="spectral-chart-line" />
              ))}
              {valid.map((s) => (
                <circle
                  key={s.channel}
                  cx={x(s.wavelength_um)}
                  cy={y(s.value)}
                  r={s.channel === selectedChannel ? 5 : 2.2}
                  className={
                    s.channel === selectedChannel ? "spectral-chart-point spectral-chart-point-selected" : "spectral-chart-point"
                  }
                />
              ))}
              {plotted
                .filter((s) => s.value === null)
                .map((s) => (
                  <line
                    key={`n${s.channel}`}
                    x1={x(s.wavelength_um)}
                    x2={x(s.wavelength_um)}
                    y1={IH - 5}
                    y2={IH + 5}
                    className="spectral-chart-null"
                  />
                ))}

              {tip && (
                <line x1={x(tip.wavelength_um)} x2={x(tip.wavelength_um)} y1={0} y2={IH} className="spectral-chart-crosshair" />
              )}
              {tip && tip.value !== null && (
                <circle cx={x(tip.wavelength_um)} cy={y(tip.value)} r={4.5} className="spectral-chart-point-hover" />
              )}

              <text x={IW / 2} y={IH + 38} className="spectrum-axis-label" textAnchor="middle">
                Wavelength (µm)
              </text>
              <text x={-IH / 2} y={-50} className="spectrum-axis-label" textAnchor="middle" transform="rotate(-90)">
                Brightness ({unit ?? "unknown unit"})
              </text>

              <rect
                x={0}
                y={0}
                width={IW}
                height={IH}
                fill="transparent"
                className="spectral-chart-hit"
                onMouseMove={(e) => setHover(nearest(e))}
                onMouseLeave={() => setHover(null)}
                onClick={(e) => {
                  const s = nearest(e);
                  if (s) onSelectChannel(s.channel);
                }}
              />
            </g>
          </svg>

          {tip && (
            <div
              className="spectral-chart-tooltip"
              style={{
                left: `${tipLeftPct}%`,
                transform: tipLeftPct > 70 ? "translateX(calc(-100% - 10px))" : "translateX(10px)",
              }}
            >
              <strong>Channel {tip.channel}</strong>
              <span>{tip.wavelength_um.toFixed(3)} µm · detector {tip.detector ?? "—"}</span>
              <span>
                {tip.value === null ? "No valid data (null)" : `${fmtValue(tip.value)} ${unit ?? ""}`}
              </span>
              <em>Click to view this channel</em>
            </div>
          )}
        </div>
      </div>

      <div className="spectral-chart-legend">
        <span>
          <i className="legend-line" /> Brightness measured ({valid.length} wavelengths)
        </span>
        <span>
          <i className="legend-null" /> No data ({plotted.length - valid.length}) — shown as a gap, not as zero
        </span>
        <span>
          <i className="legend-selected" /> Wavelength shown in the image
        </span>
      </div>
    </div>
  );
}
