export function About() {
  return (
    <div className="page">
      <div className="page-header">
        <h1>About SpectraShift</h1>
        <p className="page-subtitle">
          A SPHEREx Spectral &amp; Multi-Epoch Sky Explorer — built for the
          NASA Space Apps 2026 "Planet X and SPHEREx" challenge.
        </p>
      </div>

      <div className="card">
        <h2>Challenge Goal</h2>
        <p>
          SpectraShift is a public-facing SPHEREx sky explorer: a way to
          browse real spectral sky imagery and compare observations of the
          same field across time, to see what appears to change or move
          between epochs.
        </p>
      </div>

      <div className="card">
        <h2>How SpectraShift Works</h2>
        <p>
          Explore the sky → click a source → inspect its spectrum and
          catalogue context → compare two epochs directly → inspect the
          full evidence behind any motion candidate.
        </p>
      </div>

      <div className="card">
        <h2>Data &amp; Provenance</h2>
        <p>
          Imagery is from the SPHEREx mission, Quick Release 2 (QR2),
          DOI 10.26131/IRSA652, accessed via IRSA (hosted on AWS).
        </p>
      </div>

      <div className="card">
        <h2>What this is</h2>
        <p>
          This project processes multi-epoch SPHEREx imagery to detect
          sources that move across three observation epochs (A → C → B),
          validates that motion scientifically (trajectory consistency,
          motion-rate consistency, flux consistency, and epoch-C position
          prediction error), and cross-matches each candidate against Gaia
          DR3, SIMBAD, and available Solar System object catalogues.
        </p>
      </div>

      <div className="card">
        <h2>Scientific Limitations</h2>
        <p>
          A full MPC/SkyBoT minor-planet catalogue verification was not
          completed for these candidates, and the JPL Horizons check that
          was used only covers a limited set of major/bright bodies, not
          the full minor-planet catalogue. Because of this,{" "}
          <code>UNMATCHED_AFTER_CHECKS</code> and <code>UNCERTAIN</code>{" "}
          only describe the checks actually performed — they do not mean
          "unknown" or "a new planet."
        </p>
      </div>

      <div className="card">
        <h2>What this is not</h2>
        <p>
          Nothing produced by this pipeline is a confirmed discovery. A
          candidate is not "Planet X," a new planet, or a confirmed unknown
          object. Catalogue status only ever reflects one of three
          outcomes: a match found in the checks actually performed
          (<code>KNOWN_OBJECT</code>), no match in the checks actually
          performed (<code>UNMATCHED_AFTER_CHECKS</code>), or an important
          check that could not be completed (<code>UNCERTAIN</code>).
        </p>
      </div>
    </div>
  );
}
