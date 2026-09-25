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
          <p className="lead-note">Same sky, different dates.</p>
          <ol className="steps-list">
            <li>Open <Link to="/compare">Time Compare</Link>.</li>
            <li>
              Choose <strong>~6-Month Compare</strong> (recommended) or{" "}
              <strong>31-Day Compare</strong>.
            </li>
            <li>
              Pick a viewing mode: <strong>Side by side</strong>,{" "}
              <strong>Slider</strong> (drag to wipe between dates),{" "}
              <strong>Blink</strong> (changes flicker),{" "}
              <strong>Difference</strong> (only what changed) or{" "}
              <strong>Overlay</strong> (unchanged stars look white).
            </li>
            <li>
              In Difference: red = brighter in one image, blue = brighter in
              the other (the colour key says which), dark = little or no
              change.
            </li>
          </ol>
          <p className="lead-note">
            A visible difference does not automatically mean a moving object.
          </p>
        </section>

        <section className="card">
          <h2>How to use Explore</h2>
          <ol className="steps-list">
            <li>Open <Link to="/explore">Explore</Link> and choose an observation date.</li>
            <li>Scroll to zoom in and drag to move around the image.</li>
            <li>
              If markers appear, click one to see that possible moving object's
              details. If none appear, nothing in that image passed the checks.
            </li>
          </ol>
        </section>

        <section className="card">
          <h2>What “Candidates” means</h2>
          <p>
            A <strong>candidate</strong> is a <em>possible</em> moving object:
            something that seemed to move between observation dates and
            passed our checks. It is never a confirmed discovery.
          </p>
          <p>
            In the current data no candidate passed. Every possible track was
            traced to stationary stars, blended sources or mismatches.{" "}
            <Link to="/candidates">See the details →</Link>
          </p>
          <TechnicalDetails summary="Catalogue check statuses">
            <dl className="kv-list">
              <div>
                <dt>KNOWN_OBJECT</dt>
                <dd>
                  A strong catalogue match explains the detections, including
                  the case where each date shows a different known star.
                </dd>
              </div>
              <div>
                <dt>UNMATCHED_AFTER_CHECKS</dt>
                <dd>Every required check ran and none matched. This does not mean new or unknown.</dd>
              </div>
              <div>
                <dt>UNCERTAIN</dt>
                <dd>The evidence is not strong enough either way.</dd>
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
