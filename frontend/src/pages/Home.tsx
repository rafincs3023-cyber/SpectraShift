import { Link } from "react-router-dom";

export function Home() {
  return (
    <div className="page">
      <section className="hero-panel">
        <p className="eyebrow">SPHEREx · Three-Epoch Motion Survey</p>
        <h1>
          Mapping slow-moving candidates across the outer solar system
        </h1>
        <p className="hero-lead">
          This tool tracks sources detected across three SPHEREx epochs
          (A → C → B), scientifically validates their motion, and cross-checks
          them against Gaia, SIMBAD, and known Solar System object catalogues.
          Every candidate here is preliminary and unconfirmed.
        </p>
        <div className="hero-actions">
          <Link to="/candidates" className="btn btn-primary">
            View validated candidates
          </Link>
          <Link to="/about" className="btn btn-secondary">
            About this project
          </Link>
        </div>
      </section>

      <section className="feature-grid">
        <Link to="/explore" className="feature-card">
          <h2>Explore</h2>
          <p>Browse the raw SPHEREx sky imagery by epoch. Coming soon.</p>
        </Link>
        <Link to="/compare" className="feature-card">
          <h2>Compare</h2>
          <p>Side-by-side multi-epoch sky comparison. Coming soon.</p>
        </Link>
        <Link to="/candidates" className="feature-card">
          <h2>Candidates</h2>
          <p>
            The full, validated three-epoch motion candidate list, live from
            the API.
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
