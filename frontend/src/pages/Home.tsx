import { Link } from "react-router-dom";

export function Home() {
  return (
    <div className="page">
      <section className="hero-panel">
        <p className="eyebrow">NASA SPHEREx · Spectral &amp; Multi-Epoch Sky Explorer</p>
        <h1>Explore the same sky across wavelength and time</h1>
        <p className="hero-lead">
          SpectraShift works directly on real SPHEREx data. Spectral View steps
          through 102 near-infrared wavelength channels of one sky region;
          Time Compare lines up observations of the same sky taken months
          apart to reveal apparent change; and a three-epoch pipeline searches
          for moving sources while rejecting stationary-star and blend false
          positives. Every result here is preliminary.
        </p>
        <div className="hero-actions">
          <Link to="/spectral" className="btn btn-primary">
            Open Spectral View
          </Link>
          <Link to="/compare" className="btn btn-secondary">
            Open Time Compare
          </Link>
          <Link to="/about" className="btn btn-secondary">
            About this project
          </Link>
        </div>
      </section>

      <section className="feature-grid">
        <Link to="/spectral" className="feature-card">
          <h2>Spectral View</h2>
          <p>
            Same sky, same time, 102 wavelengths (0.74–5.01 µm). Change
            channels and click any position for its spectrum.
          </p>
        </Link>
        <Link to="/compare" className="feature-card">
          <h2>Time Compare</h2>
          <p>
            Same sky at different times: a registered ~6-month pair (Jun → Dec
            2025) plus a 31-day A/C/B set, in side-by-side, slider, blink,
            difference and overlay modes.
          </p>
        </Link>
        <Link to="/explore" className="feature-card">
          <h2>Explore</h2>
          <p>Browse one SPHEREx epoch at a time with zoom and pan.</p>
        </Link>
        <Link to="/candidates" className="feature-card">
          <h2>Candidates</h2>
          <p>
            Three-epoch motion-candidate pipeline results after the
            stationary-source and blend vetoes, live from the API.
          </p>
        </Link>
      </section>

      <p className="disclaimer">
        No candidate on this site is labelled a discovery, Planet X, or a
        confirmed new object. Catalogue status is always one of{" "}
        <code>KNOWN_OBJECT</code>, <code>UNMATCHED_AFTER_CHECKS</code>, or{" "}
        <code>UNCERTAIN</code>.
      </p>
    </div>
  );
}
