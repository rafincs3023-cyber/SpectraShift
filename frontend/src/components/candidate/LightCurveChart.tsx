import type { ReactNode } from "react";
import type { SpectrumPoint } from "../../api/types";

const WIDTH = 420;
const HEIGHT = 200;
const MARGIN = { top: 16, right: 16, bottom: 36, left: 48 };

function fmt(value: number | null | undefined, digits = 3): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return value.toFixed(digits);
}

export function LightCurveChart({ points }: { points: SpectrumPoint[] }) {
  const plottable = points.filter(
    (p) => p.mjd !== null && p.flux !== null
  ) as (SpectrumPoint & { mjd: number; flux: number })[];

  const innerW = WIDTH - MARGIN.left - MARGIN.right;
  const innerH = HEIGHT - MARGIN.top - MARGIN.bottom;

  let chart: ReactNode = (
    <p className="section-note">
      No epoch has both a real observation time and flux value for this
      candidate — nothing to plot.
    </p>
  );

  if (plottable.length === 1) {
    chart = (
      <p className="section-note">
        Only one epoch has both a real time and flux value (flux ={" "}
        {fmt(plottable[0].flux)}); at least two are needed to show a
        brightness trend.
      </p>
    );
  } else if (plottable.length > 1) {
    const mjd0 = Math.min(...plottable.map((p) => p.mjd));
    const days = plottable.map((p) => p.mjd - mjd0);
    const fluxes = plottable.map((p) => p.flux);

    const dMin = 0;
    const dMax = Math.max(...days);
    const fMin = Math.min(0, ...fluxes);
    const fMax = Math.max(...fluxes);

    const dPad = (dMax - dMin || 1) * 0.15;
    const fPad = (fMax - fMin || 1) * 0.2;

    const xDomain: [number, number] = [dMin - dPad, dMax + dPad];
    const yDomain: [number, number] = [fMin - fPad, fMax + fPad];

    const xScale = (d: number) =>
      ((d - xDomain[0]) / (xDomain[1] - xDomain[0])) * innerW;
    const yScale = (f: number) =>
      innerH - ((f - yDomain[0]) / (yDomain[1] - yDomain[0])) * innerH;

    const sorted = plottable
      .map((p, i) => ({ ...p, day: days[i] }))
      .sort((a, b) => a.day - b.day);

    chart = (
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        className="spectrum-svg"
        role="img"
        aria-label="Flux versus observation time"
      >
        <g transform={`translate(${MARGIN.left},${MARGIN.top})`}>
          {Array.from({ length: 4 + 1 }, (_, i) => {
            const f = yDomain[0] + (i / 4) * (yDomain[1] - yDomain[0]);
            const y = yScale(f);
            return (
              <g key={`y-${i}`}>
                <line x1={0} x2={innerW} y1={y} y2={y} className="spectrum-grid" />
                <text x={-8} y={y} className="spectrum-tick" textAnchor="end" dy="0.32em">
                  {f.toFixed(1)}
                </text>
              </g>
            );
          })}

          {sorted.map((p) => (
            <text
              key={`x-${p.epoch}`}
              x={xScale(p.day)}
              y={innerH + 16}
              className="spectrum-tick"
              textAnchor="middle"
            >
              {p.day.toFixed(1)}d
            </text>
          ))}

          <line x1={0} x2={innerW} y1={innerH} y2={innerH} className="spectrum-axis" />
          <line x1={0} x2={0} y1={0} y2={innerH} className="spectrum-axis" />

          <polyline
            points={sorted.map((p) => `${xScale(p.day)},${yScale(p.flux)}`).join(" ")}
            className="motion-track-line"
            fill="none"
          />

          {sorted.map((p) => {
            const cx = xScale(p.day);
            const cy = yScale(p.flux);
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
                <circle cx={cx} cy={cy} r={5} className="spectrum-point" />
                <text x={cx} y={cy - 10} className="spectrum-point-label" textAnchor="middle">
                  {p.epoch}
                </text>
              </g>
            );
          })}

          <text x={innerW / 2} y={innerH + 32} className="spectrum-axis-label" textAnchor="middle">
            Days since first available epoch
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
      <p className="section-note">
        Brightness (flux) measured at this candidate's real detected
        position in each epoch. Not a continuous light curve — only 3
        epochs (A, C, B) exist.
      </p>
    </div>
  );
}
