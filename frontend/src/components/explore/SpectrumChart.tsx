import type { ReactNode } from "react";
import type { SpectrumPoint } from "../../api/types";

const WIDTH = 420;
const HEIGHT = 220;
const MARGIN = { top: 16, right: 16, bottom: 36, left: 48 };

function fmt(value: number | null | undefined, digits = 3): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return value.toFixed(digits);
}

export function SpectrumChart({ points }: { points: SpectrumPoint[] }) {
  const plottable = points.filter(
    (p) => p.wavelength_um !== null && p.flux !== null
  ) as (SpectrumPoint & { wavelength_um: number; flux: number })[];

  const innerW = WIDTH - MARGIN.left - MARGIN.right;
  const innerH = HEIGHT - MARGIN.top - MARGIN.bottom;

  let chart: ReactNode = (
    <p className="section-note">
      No epoch has both a real wavelength and flux value for this candidate
      — nothing to plot.
    </p>
  );

  if (plottable.length > 0) {
    const wavelengths = plottable.map((p) => p.wavelength_um);
    const fluxes = plottable.map((p) => p.flux);

    const wMin = Math.min(...wavelengths);
    const wMax = Math.max(...wavelengths);
    const fMin = Math.min(0, ...fluxes);
    const fMax = Math.max(...fluxes);

    const wPad = (wMax - wMin || 0.05) * 0.25;
    const fPad = (fMax - fMin || 1) * 0.2;

    const xDomain: [number, number] = [wMin - wPad, wMax + wPad];
    const yDomain: [number, number] = [fMin - fPad, fMax + fPad];

    const xScale = (w: number) =>
      ((w - xDomain[0]) / (xDomain[1] - xDomain[0])) * innerW;
    const yScale = (f: number) =>
      innerH - ((f - yDomain[0]) / (yDomain[1] - yDomain[0])) * innerH;

    const xTicks = 4;
    const yTicks = 4;

    chart = (
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        className="spectrum-svg"
        role="img"
        aria-label="Flux versus wavelength"
      >
        <g transform={`translate(${MARGIN.left},${MARGIN.top})`}>
          {/* gridlines + y ticks */}
          {Array.from({ length: yTicks + 1 }, (_, i) => {
            const f = yDomain[0] + (i / yTicks) * (yDomain[1] - yDomain[0]);
            const y = yScale(f);
            return (
              <g key={`y-${i}`}>
                <line
                  x1={0}
                  x2={innerW}
                  y1={y}
                  y2={y}
                  className="spectrum-grid"
                />
                <text x={-8} y={y} className="spectrum-tick" textAnchor="end" dy="0.32em">
                  {f.toFixed(1)}
                </text>
              </g>
            );
          })}

          {/* x ticks */}
          {Array.from({ length: xTicks + 1 }, (_, i) => {
            const w = xDomain[0] + (i / xTicks) * (xDomain[1] - xDomain[0]);
            const x = xScale(w);
            return (
              <g key={`x-${i}`}>
                <line
                  x1={x}
                  x2={x}
                  y1={0}
                  y2={innerH}
                  className="spectrum-grid"
                />
                <text x={x} y={innerH + 16} className="spectrum-tick" textAnchor="middle">
                  {w.toFixed(2)}
                </text>
              </g>
            );
          })}

          <line x1={0} x2={innerW} y1={innerH} y2={innerH} className="spectrum-axis" />
          <line x1={0} x2={0} y1={0} y2={innerH} className="spectrum-axis" />

          {plottable.map((p) => {
            const cx = xScale(p.wavelength_um);
            const cy = yScale(p.flux);
            const xErr = p.wavelength_bandwidth_um
              ? (p.wavelength_bandwidth_um / 2)
              : 0;
            const yErr = p.flux_uncertainty ?? 0;

            return (
              <g key={p.epoch}>
                {yErr > 0 && (
                  <line
                    x1={cx}
                    x2={cx}
                    y1={yScale(p.flux - yErr)}
                    y2={yScale(p.flux + yErr)}
                    className="spectrum-errorbar"
                  />
                )}
                {xErr > 0 && (
                  <line
                    x1={xScale(p.wavelength_um - xErr)}
                    x2={xScale(p.wavelength_um + xErr)}
                    y1={cy}
                    y2={cy}
                    className="spectrum-errorbar"
                  />
                )}
                <circle cx={cx} cy={cy} r={5} className="spectrum-point" />
                <text x={cx} y={cy - 10} className="spectrum-point-label" textAnchor="middle">
                  {p.epoch}
                </text>
              </g>
            );
          })}

          <text
            x={innerW / 2}
            y={innerH + 32}
            className="spectrum-axis-label"
            textAnchor="middle"
          >
            Wavelength (µm)
          </text>
          <text
            x={-innerH / 2}
            y={-36}
            className="spectrum-axis-label"
            textAnchor="middle"
            transform="rotate(-90)"
          >
            Flux
          </text>
        </g>
      </svg>
    );
  }

  return (
    <div className="spectrum-chart">
      {chart}

      <div className="table-scroll">
        <table className="data-table spectrum-table">
          <thead>
            <tr>
              <th>Epoch</th>
              <th>Wavelength (µm)</th>
              <th>Bandwidth (µm)</th>
              <th>Flux</th>
              <th>Flux uncertainty</th>
            </tr>
          </thead>
          <tbody>
            {points.map((p) => (
              <tr key={p.epoch}>
                <td data-label="Epoch">{p.epoch}</td>
                <td data-label="Wavelength (um)">{fmt(p.wavelength_um)}</td>
                <td data-label="Bandwidth (um)">{fmt(p.wavelength_bandwidth_um)}</td>
                <td data-label="Flux">{fmt(p.flux)}</td>
                <td data-label="Flux uncertainty">{fmt(p.flux_uncertainty)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="section-note">
        Each point is the single wavelength sampled at this candidate's real
        detector pixel in that epoch (SPHEREx's linear-variable-filter
        detector maps position to wavelength) — not a continuous spectrum.
        "—" means that value could not be determined for that epoch; it is
        never invented or interpolated.
      </p>
    </div>
  );
}
