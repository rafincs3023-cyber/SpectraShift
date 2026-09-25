import { Link } from "react-router-dom";
import { PageIntro } from "../components/ui/PageIntro";
import { TechnicalDetails } from "../components/ui/TechnicalDetails";

export function About() {
  return (
    <div className="page">
      <PageIntro
        eyebrow="NASA Space Apps 2026 · “Planet X and SPHEREx”"
        title="About SpectraShift"
        lead="SpectraShift is a SPHEREx sky explorer: it lets anyone look at real NASA infrared data across wavelength and across time, and shows the result of a careful search for moving objects."
      />

      <div className="card-grid-2">
        <section className="card">
          <h2>What SpectraShift does</h2>
          <ul className="plain-list">
            <li>
              <strong>Spectral View</strong> — one patch of sky in 102
              infrared wavelengths, with the spectrum of any point you click.
            </li>
            <li>
              <strong>Time Compare</strong> — the same sky on two dates, lined
              up exactly, to spot changes.
            </li>
            <li>
              <strong>Explore</strong> — browse a single observation.
            </li>
            <li>
              <strong>Possible moving objects</strong> — the results of a
              search for objects that move between three observations.
            </li>
          </ul>
        </section>

        <section className="card">
          <h2>The data</h2>
          <p>
            All images are real data from NASA's SPHEREx mission, an infrared
            space telescope that maps the whole sky in 102 wavelengths
            (about 0.75 to 5 µm). The data come from NASA/IPAC's IRSA archive
            (SPHEREx Quick Release, DOI 10.26131/IRSA652).
          </p>
          <ul className="plain-list">
            <li>A 102-wavelength mosaic of one 5° × 4.25° sky region.</li>
            <li>Two images of the same field about 6 months apart (Jun 19 and Dec 17, 2025).</li>
            <li>Three images of one field within a month (May 9 – Jun 9, 2025).</li>
          </ul>
        </section>

        <section className="card">
          <h2>Wavelength vs time</h2>
          <p>
            <strong>Spectral View</strong> compares <em>wavelengths</em>: the
            same sky at the same moment, seen in different “colours” of
            infrared light. Differences there come from what the objects are
            made of and how hot they are — not from motion.
          </p>
          <p>
            <strong>Time Compare</strong> compares <em>dates</em>: the same sky
            and wavelength on different days. Differences there can come from
            changes over time, including motion.
          </p>
        </section>

        <section className="card">
          <h2>How the moving-object search works</h2>
          <ol className="steps-list">
            <li>Find every star-like source in three images taken within a month.</li>
            <li>Link sources that could be one object moving in a straight line.</li>
            <li>Reject tracks made of stationary stars, blended sources or bright-star glare.</li>
            <li>Check anything left against catalogues of stars, galaxies, asteroids and comets.</li>
          </ol>
          <p>
            In the current data every possible track was rejected, so no
            candidate is listed. <Link to="/candidates">See the result →</Link>
          </p>
        </section>

        <section className="card">
          <h2>Limitations</h2>
          <ul className="plain-list">
            <li>One sky region; Time Compare uses a single detector.</li>
            <li>
              An empty result does not mean nothing moves here: in this crowded
              field the search recovers only part of the moving objects it is
              tested on.
            </li>
            <li>The search looks for straight-line motion over one month only.</li>
            <li>
              The two ~6-month images differ very slightly in wavelength, so a
              difference is an apparent change, not proof of a physical one.
            </li>
          </ul>
        </section>

        <section className="card">
          <h2>What this project is not</h2>
          <p>
            Nothing here is a confirmed discovery. No object is called
            “Planet X”, a new planet or a confirmed moving object. A candidate
            that no catalogue matches is “unmatched after checks”, which does
            not mean “unknown” or “new”.
          </p>
        </section>
      </div>

      <section className="card">
        <h2>Technical notes</h2>
        <TechnicalDetails summary="How catalogue checks and statuses work">
          <p>
            Catalogue classification propagates Gaia DR3 and SIMBAD positions
            to each SPHEREx observation date using their catalogued proper
            motions, and tests every association against the combined SPHEREx
            and catalogue positional uncertainty. The known asteroid and comet
            search uses the JPL Small-Body Identification service, with
            positions computed from the SPHEREx spacecraft itself; SkyBoT and
            the MPC Checker were unreachable and are not relied on.
          </p>
          <p>
            Each candidate gets exactly one status:{" "}
            <code>KNOWN_OBJECT</code> (a strong match in the checks
            performed), <code>UNMATCHED_AFTER_CHECKS</code> (every required
            check ran and none matched) or <code>UNCERTAIN</code> (evidence
            incomplete, ambiguous or inconsistent).
          </p>
        </TechnicalDetails>
      </section>
    </div>
  );
}
