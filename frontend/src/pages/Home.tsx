import { Link } from "react-router-dom";

const FEATURES = [
  {
    to: "/spectral",
    title: "Spectral View",
    tag: "Across wavelength",
    text: "Explore the same sky across 102 infrared wavelengths.",
  },
  {
    to: "/compare",
    title: "Time Compare",
    tag: "Across time",
    text: "Compare the same sky observed about six months apart.",
  },
  {
    to: "/explore",
    title: "Explore",
    tag: "One observation",
    text: "Inspect either real observation in detail.",
  },
  {
    to: "/candidates",
    title: "Candidates",
    tag: "Two-epoch screening",
    text: "Inspect possible two-epoch moving-source candidates.",
  },
];

export function Home() {
  return (
    <div className="page">
      <section className="hero-panel">
        <p className="eyebrow">NASA SPHEREx · Real sky data</p>
        <h1>Explore the same sky across wavelength and time</h1>
        <p className="hero-lead">
          SpectraShift lets you explore real NASA SPHEREx data across 102
          infrared wavelengths, and compare the same sky observed on June 19
          and December 17, 2025.
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
      <section className="feature-grid feature-grid-4">
        {FEATURES.map((f) => (
          <Link key={f.to} to={f.to} className="feature-card">
            <span className="feature-tag">{f.tag}</span>
            <h2>{f.title}</h2>
            <p>{f.text}</p>
            <span className="feature-cta">Open {f.title} →</span>
          </Link>
        ))}
      </section>

      <p className="disclaimer">
        SpectraShift shows real NASA data and preliminary analysis. It does not
        claim any new discovery: candidates are possibilities for follow-up,
        and nothing here is labelled Planet X, a new planet or a confirmed
        moving object.
      </p>
    </div>
  );
}
