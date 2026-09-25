import { useState, type FormEvent } from "react";
import type { SpectrumResponse } from "../../api/spectral";
import { InfoTooltip } from "../ui/InfoTooltip";
import { TechnicalDetails } from "../ui/TechnicalDetails";

function fmt(value: number | null | undefined, digits: number): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return value.toFixed(digits);
}

function fmtValue(v: number): string {
  const a = Math.abs(v);
  if (a !== 0 && (a < 0.01 || a >= 1e4)) return v.toExponential(3);
  return v.toPrecision(4);
}

function availability(nValid: number, n: number): string {
  if (nValid === n) return `Data available in all ${n} wavelengths`;
  if (nValid === 0) return `No data at any of the ${n} wavelengths`;
  return `Data available in ${nValid} of ${n} wavelengths`;
}

/** The selected sky point, plus a manual sky-coordinate lookup form. */
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
      setFormError("Enter RA and Dec as decimal degrees, for example 155.352 and -42.700.");
      return;
    }
    if (r < 0 || r > 360 || d < -90 || d > 90) {
      setFormError("RA must be between 0 and 360, and Dec between −90 and +90.");
      return;
    }
    setFormError(null);
    onLookup(r, d);
  }

  const current = spectrum?.samples.find((s) => s.channel === selectedChannel) ?? null;

  return (
    <div className="card spectral-side-card">
      <div className="spectral-side-head">
        <h2>Selected point in the sky</h2>
        {(spectrum || error) && (
          <button type="button" className="chip-btn" onClick={onClear}>
            Clear
          </button>
        )}
      </div>

      {!spectrum && !loading && !error && (
        <p className="section-note">
          No point selected yet. Click anywhere on the image to see that
          point's spectrum, or type sky coordinates below.
        </p>
      )}
      {loading && (
        <p className="section-note" role="status">
          Reading all 102 wavelengths at this point…
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
              <dt>
                Sky coordinates
                <InfoTooltip term="skyCoordinates" />
              </dt>
              <dd>
                RA {fmt(spectrum.pixel_center.ra_deg, 3)}°, Dec {fmt(spectrum.pixel_center.dec_deg, 3)}°
              </dd>
            </div>
            <div>
              <dt>
                Brightness at this wavelength
                <InfoTooltip term="brightness" />
              </dt>
              <dd>
                {current?.value == null
                  ? "no data"
                  : `${fmtValue(current.value)} ${spectrum.unit ?? ""}`}
              </dd>
            </div>
          </dl>
          <p className={spectrum.has_data ? "availability-note" : "spectral-inline-error"}>
            {availability(spectrum.n_valid, spectrum.n_channels)}
            {!spectrum.has_data && " — this point is outside the imaged area. Try a point inside the image."}
          </p>
          <TechnicalDetails>
            <dl className="kv-list kv-list-compact">
              <div>
                <dt>
                  RA
                  <InfoTooltip term="ra" />
                </dt>
                <dd>{fmt(spectrum.pixel_center.ra_deg, 5)}°</dd>
              </div>
              <div>
                <dt>
                  Dec
                  <InfoTooltip term="dec" />
                </dt>
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
                <dt>Channel shown</dt>
                <dd>{selectedChannel}</dd>
              </div>
              <div>
                <dt>
                  Unit
                  <InfoTooltip term="unit" />
                </dt>
                <dd>{spectrum.unit ?? "—"}</dd>
              </div>
            </dl>
          </TechnicalDetails>
        </>
      )}

      <form className="radec-form" onSubmit={submit} noValidate>
        <p className="radec-form-title">Or enter sky coordinates</p>
        <label>
          <span>
            RA (°)
            <InfoTooltip term="ra" />
          </span>
          <input value={ra} onChange={(e) => setRa(e.target.value)} inputMode="decimal" placeholder="155.352" />
        </label>
        <label>
          <span>
            Dec (°)
            <InfoTooltip term="dec" />
          </span>
          <input value={dec} onChange={(e) => setDec(e.target.value)} inputMode="decimal" placeholder="-42.700" />
        </label>
        <button type="submit" className="btn btn-secondary">
          Show spectrum
        </button>
      </form>
      {formError && <p className="spectral-inline-error">{formError}</p>}
      {footprintHint && <p className="section-note radec-hint">{footprintHint}</p>}
    </div>
  );
}
