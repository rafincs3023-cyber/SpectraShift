import { Link } from "react-router-dom";
import { PageIntro } from "../components/ui/PageIntro";
import { TechnicalDetails } from "../components/ui/TechnicalDetails";

export function About() {
  return (
    <div className="page">
      <PageIntro
        eyebrow="NASA Space Apps 2026 · “Planet X and SPHEREx”"
        title="About SpectraShift"
        lead="SpectraShift is a SPHEREx sky explorer: it lets anyone look at real NASA infrared data across wavelength and across time, and screens two observations about six months apart for possible moving sources."
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
              <strong>Time Compare</strong> — the same sky on June 19 and
              December 17, 2025, lined up exactly, to spot changes.
            </li>
            <li>
              <strong>Explore</strong> — inspect either of those two
              observations in detail.
            </li>
            <li>
              <strong>Candidates</strong> — possible position or brightness
              changes found between those two observations.
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
            <li>
              Two single images of one field, taken on June 19 and December
              17, 2025 — 181.77 days (about 5.97 months) apart, at the same
              wavelength (≈1.68 µm) and on the same detector.
            </li>
          </ul>
        </section>

        <section className="card">
          <h2>Wavelength vs time</h2>
          <p>
            <strong>Spectral analysis</strong> compares <em>wavelengths</em>:
            the same sky at the same moment, seen in different “colours” of
            infrared light. Differences there come from what the objects are
            made of and how hot they are — not from motion.
          </p>
          <p>
            <strong>Temporal analysis</strong> compares <em>dates</em>: the
            same sky on June 19 and December 17, 2025. Differences there can
            come from changes over time, including motion.
          </p>
        </section>

        <section className="card">
          <h2>How the candidate screening works</h2>
          <ol className="steps-list">
            <li>Find every star-like source in the earlier and in the later image.</li>
            <li>Set aside sources found at the same place on both dates (stationary).</li>
            <li>
              Reject look-alikes: image edges, pixels SPHEREx flagged, bright-star
              glare, blends, shapes unlike a star, and changes the difference
              image does not confirm.
            </li>
            <li>List what is left as candidates for inspection.</li>
          </ol>
          <p>
            <Link to="/candidates">See the current result →</Link>
          </p>
        </section>

        <section className="card">
          <h2>Limitations</h2>
          <ul className="plain-list">
            <li>
              Two observations alone cannot establish a full trajectory or an
              orbit: a candidate is a possible change, never a measured path.
            </li>
            <li>One sky field and one detector for the time comparison.</li>
            <li>
              The two images differ very slightly in wavelength and sharpness,
              so a difference is an apparent change, not proof of a physical
              one.
            </li>
            <li>
              An empty or short candidate list does not mean nothing moves
              here: faint or blended objects can be missed.
            </li>
          </ul>
        </section>

        <section className="card">
          <h2>What this project is not</h2>
          <p>
            Nothing here is a confirmed discovery. No object is called
            “Planet X”, a new planet or a confirmed moving object. A candidate
            is only a source that passed the current checks and deserves a
            closer look.
          </p>
        </section>
      </div>

      <section className="card">
        <h2>Technical notes</h2>
        <TechnicalDetails summary="How the two images are compared">
          <p>
            The later image (December 17) was reprojected onto the earlier
            image's (June 19) pixel grid, so both share one grid and one
            common footprint. The candidate pipeline measures each image's
            noise and sharpness, blurs the sharper image to match the other,
            detects sources in each with a matched filter (5σ), and pairs
            sources on the shared grid. How far a stationary star's position
            scatters between the two dates is measured from thousands of
            matched stars; a source counts as stationary within 5σ of that
            scatter. Every rejection reason and threshold is listed on the
            Candidates page.
          </p>
        </TechnicalDetails>
      </section>
    </div>
  );
}
