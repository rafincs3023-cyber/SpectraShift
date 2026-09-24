import { useState, type FormEvent } from "react";
import type { SpectrumResponse } from "../../api/spectral";

function fmt(value: number | null | undefined, digits: number): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return value.toFixed(digits);
}

function fmtValue(v: number): string {
  const a = Math.abs(v);
  if (a !== 0 && (a < 0.01 || a >= 1e4)) return v.toExponential(3);
  return v.toPrecision(4);
}

/** Selected sky position summary plus a manual RA/Dec lookup form. */
export function SelectedPositionPanel({
  spectrum,
  loading,
  error,
  selectedChannel,
  footprintHint,
  onLookup,
  onClear,
}: {
  spectrum: SpectrumResponse | null;
  loading: boolean;
  error: string | null;
  selectedChannel: number;
  footprintHint: string | null;
  onLookup: (ra: number, dec: number) => void;
  onClear: () => void;
}) {
  const [ra, setRa] = useState("");
  const [dec, setDec] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  function submit(e: FormEvent) {
    e.preventDefault();
    const r = Number(ra);
    const d = Number(dec);
    if (ra.trim() === "" || dec.trim() === "" || !Number.isFinite(r) || !Number.isFinite(d)) {
      setFormError("Enter RA and Dec in decimal degrees.");
      return;
    }
    if (r < 0 || r > 360 || d < -90 || d > 90) {
      setFormError("RA must be 0–360° and Dec −90–+90°.");
      return;
    }
    setFormError(null);
    onLookup(r, d);
  }

  const current = spectrum?.samples.find((s) => s.channel === selectedChannel) ?? null;

  return (
    <div className="card spectral-side-card">
      <div className="spectral-side-head">
        <h2>Selected position</h2>
        {(spectrum || error) && (
          <button type="button" className="chip-btn" onClick={onClear}>
            Clear
          </button>
        )}
      </div>

      {!spectrum && !loading && !error && (
        <p className="section-note">
          Click anywhere on the image to read that spot's brightness in all
          channels, or enter coordinates below.
        </p>
      )}
      {loading && (
        <p className="section-note" role="status">
          Reading all channels at this position…
        </p>
      )}
      {error && !loading && (
        <p className="spectral-inline-error" role="alert">
          {error}
        </p>
      )}

      {spectrum && !loading && (
        <>
          <dl className="kv-list kv-list-compact">
            <div>
              <dt>RA</dt>
              <dd>{fmt(spectrum.pixel_center.ra_deg, 5)}°</dd>
            </div>
            <div>
              <dt>Dec</dt>
              <dd>{fmt(spectrum.pixel_center.dec_deg, 5)}°</dd>
            </div>
            <div>
              <dt>Pixel (x, y)</dt>
              <dd>
                {spectrum.pixel.x_index}, {spectrum.pixel.y_index}
              </dd>
            </div>
            <div>
              <dt>Valid samples</dt>
              <dd>
                {spectrum.n_valid} / {spectrum.n_channels}
              </dd>
            </div>
            <div>
              <dt>Value in channel {selectedChannel}</dt>
              <dd>
                {current?.value == null
                  ? "no data"
                  : `${fmtValue(current.value)} ${spectrum.unit ?? ""}`}
              </dd>
            </div>
          </dl>
          {!spectrum.has_data && (
            <p className="spectral-inline-error">
              No valid data at this position in any channel — the mosaic has
              no coverage here. Try a spot inside the imaged area.
            </p>
          )}
        </>
      )}

      <form className="radec-form" onSubmit={submit} noValidate>
        <label>
          <span>RA (°)</span>
          <input value={ra} onChange={(e) => setRa(e.target.value)} inputMode="decimal" placeholder="155.352" />
        </label>
        <label>
          <span>Dec (°)</span>
          <input value={dec} onChange={(e) => setDec(e.target.value)} inputMode="decimal" placeholder="-42.700" />
        </label>
        <button type="submit" className="btn btn-secondary">
          Look up
        </button>
      </form>
      {formError && <p className="spectral-inline-error">{formError}</p>}
      {footprintHint && <p className="section-note radec-hint">{footprintHint}</p>}
    </div>
  );
}
