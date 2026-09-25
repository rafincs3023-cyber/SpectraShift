import { Link } from "react-router-dom";
import { PageIntro } from "../components/ui/PageIntro";
import { TechnicalDetails } from "../components/ui/TechnicalDetails";
import { GLOSSARY, type GlossaryKey } from "../components/ui/glossary";

const TERMS: GlossaryKey[] = [
  "wavelength",
  "channel",
  "spectrum",
  "brightness",
  "ra",
  "dec",
  "detector",
  "observationDate",
  "differenceView",
  "candidate",
  "displacement",
  "apparentMotion",
  "stationarySource",
  "blend",
  "unit",
];

export function Help() {
  return (
    <div className="page">
      <PageIntro
        eyebrow="Help"
        title="How to use SpectraShift"
        lead="Short, step-by-step guides for each part of the site, plus a glossary of the terms you will see."
      />

      <div className="card-grid-2">
        <section className="card">
          <h2>How to use Spectral View</h2>
          <p className="lead-note">Same sky, same moment, 102 infrared wavelengths.</p>
          <ol className="steps-list">
            <li>Open <Link to="/spectral">Spectral View</Link>.</li>
            <li>
              Move through wavelengths with the slider, the wavelength bar,
              the Shorter / Longer buttons or the ← / → keys.
            </li>
            <li>Click any point in the image — a bright star is a good start.</li>
            <li>
              Read the chart: it shows how bright that point is at each
              wavelength (its spectrum).
            </li>
          </ol>
          <p className="lead-note">
            Changing wavelength does not change time, so differences between
            wavelengths are not motion.
          </p>
        </section>

        <section className="card">
          <h2>How to use Time Compare</h2>
          <p className="lead-note">Same sky, June 19 and December 17, 2025.</p>
          <ol className="steps-list">
            <li>Open <Link to="/compare">Time Compare</Link>.</li>
            <li>
              Pick a viewing mode: <strong>Side by side</strong>,{" "}
              <strong>Slider</strong> (drag to wipe between dates),{" "}
              <strong>Blink</strong> (changes flicker),{" "}
              <strong>Difference</strong> (only what changed) or{" "}
              <strong>Overlay</strong> (unchanged stars look white).
            </li>
            <li>
              In Difference (Later − Earlier): red = brighter in the later
              image, blue = brighter in the earlier image, dark = little or
              no change.
            </li>
          </ol>
          <p className="lead-note">
            A visible difference does not automatically mean a moving object.
          </p>
        </section>

        <section className="card">
          <h2>How to use Explore</h2>
          <ol className="steps-list">
            <li>
              Open <Link to="/explore">Explore</Link> and choose June 19
              (earlier) or December 17, 2025 (later).
            </li>
            <li>Scroll to zoom in and drag to move around the image.</li>
            <li>
              Click a marker to see that candidate. A solid ring means the
              source is seen in this image; a dashed ring means it is seen
              only in the other one.
            </li>
          </ol>
        </section>

        <section className="card">
          <h2>How to use Candidates</h2>
          <ol className="steps-list">
            <li>Open <Link to="/candidates">Candidates</Link> to see how many passed the checks.</li>
            <li>Open an ID to see its position on each date, the pictures and the numbers.</li>
            <li>Use “Show in Explore” or Time Compare's Blink mode to look for yourself.</li>
          </ol>
        </section>

        <section className="card">
          <h2>What a two-epoch candidate means</h2>
          <p>
            A <strong>two-epoch candidate</strong> is a source whose position
            or appearance changed between June 19 and December 17, 2025
            enough to deserve a closer look, and that passed every current
            quality check.
          </p>
          <p>
            <strong>Why it is not a confirmed discovery:</strong> with only two
            dates there is no third point to test a path, so a change could
            also be a variable star, a blend of two sources, an image
            artifact or noise. Only follow-up observations can tell.
          </p>
          <TechnicalDetails summary="Candidate types">
            <dl className="kv-list">
              <div>
                <dt>Possible position change</dt>
                <dd>A source seen only earlier, paired with a similar source seen only later.</dd>
              </div>
              <div>
                <dt>Small position shift</dt>
                <dd>The same source on both dates, measured slightly further apart than expected.</dd>
              </div>
              <div>
                <dt>Seen only in the earlier / later image</dt>
                <dd>A source on one date with nothing at the same place on the other.</dd>
              </div>
            </dl>
          </TechnicalDetails>
        </section>
      </div>

      <section className="card">
        <h2>Common terms</h2>
        <dl className="glossary-list">
          {TERMS.map((key) => (
            <div key={key}>
              <dt>{GLOSSARY[key].term}</dt>
              <dd>{GLOSSARY[key].text}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section className="card">
        <h2>Where the data comes from</h2>
        <p>
          Everything on this site is real NASA SPHEREx data, served by the
          SpectraShift backend. Nothing is simulated, and no result here is a
          confirmed discovery.
        </p>
      </section>
    </div>
  );
}
