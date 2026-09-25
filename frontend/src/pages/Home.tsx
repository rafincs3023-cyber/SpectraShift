import { Link } from "react-router-dom";

const FEATURES = [
  {
    to: "/spectral",
    title: "Spectral View",
    tag: "Across wavelength",
    text: "See one patch of sky in 102 infrared wavelengths. Click any point to see how its brightness changes with wavelength.",
  },
  {
    to: "/compare",
    title: "Time Compare",
    tag: "Across time",
    text: "Compare the same sky on two dates, about 6 months apart. Use side by side, slider, blink or difference views to spot changes.",
  },
  {
    to: "/explore",
    title: "Explore",
    tag: "One observation",
    text: "Browse a single SPHEREx image. Zoom in and pan around the star field.",
  },
];

export function Home() {
  return (
    <div className="page">
      <section className="hero-panel">
        <p className="eyebrow">NASA SPHEREx · Real sky data</p>
        <h1>Explore the same sky across wavelength and time</h1>
        <p className="hero-lead">
          SpectraShift helps you explore real SPHEREx sky data across
          wavelength and time.
        </p>
        <div className="hero-actions">
          <Link to="/spectral" className="btn btn-primary">
            Explore wavelengths
          </Link>
          <Link to="/compare" className="btn btn-primary">
            Compare dates
          </Link>
          <Link to="/help" className="btn btn-secondary">
            How to use it
          </Link>
        </div>
      </section>

      <h2 className="home-section-title">What you can do</h2>
      <section className="feature-grid feature-grid-3">
        {FEATURES.map((f) => (
          <Link key={f.to} to={f.to} className="feature-card">
            <span className="feature-tag">{f.tag}</span>
            <h2>{f.title}</h2>
            <p>{f.text}</p>
            <span className="feature-cta">Open {f.title} →</span>
          </Link>
        ))}
      </section>

      <Link to="/candidates" className="feature-card feature-card-wide">
        <span className="feature-tag">Search result</span>
        <h2>Possible moving objects</h2>
        <p>
          We searched three observation dates for objects that move across
          the sky. See what the search found, and why each possible track was
          kept or rejected.
        </p>
        <span className="feature-cta">See the results →</span>
      </Link>

      <p className="disclaimer">
        SpectraShift shows real NASA data and preliminary analysis. It does not
        claim any new discovery: nothing here is labelled Planet X, a new
        planet or a confirmed moving object.
      </p>
    </div>
  );
}
