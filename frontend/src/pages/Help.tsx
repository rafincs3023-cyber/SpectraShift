export function Help() {
  return (
    <div className="page">
      <div className="page-header">
        <h1>Help</h1>
        <p className="page-subtitle">How to read this site.</p>
      </div>

      <div className="card">
        <h2>Spectral View vs Time Compare</h2>
        <dl className="kv-list">
          <div>
            <dt>Spectral View</dt>
            <dd>Same sky, same time, across 102 wavelength channels.</dd>
          </div>
          <div>
            <dt>Time Compare</dt>
            <dd>Same sky, observed at different times.</dd>
          </div>
        </dl>
      </div>

      <div className="card">
        <h2>Spectral View</h2>
        <p>
          Step through all 102 SPHEREx channels (0.74–5.01 µm, detectors
          D1–D6) with the slider, the wavelength bar, Prev / Next, a channel
          number, or the ← / → keys. The side panel shows the selected
          channel&apos;s detector, wavelength range, bandwidth and sky
          coverage. Click anywhere on the image, or enter RA/Dec, to plot
          that position&apos;s brightness in every channel.
        </p>
      </div>

      <div className="card">
        <h2>Candidates page</h2>
        <p>
          Lists the three-epoch motion candidates that pass the current
          pipeline — linking across Epochs A → C → B, the stationary-source
          and blend vetoes, trajectory validation — ranked by final priority
          score. The list can be empty: the summary line shows how many
          linked tracks were rejected and why. An empty list does not mean
          that no moving sources exist in the field. When candidates exist,
          click an ID to see its full evidence: per-epoch positions, motion
          rate, validation scores and the catalogue cross-match audit trail.
        </p>
      </div>

      <div className="card">
        <h2>Candidate Detail visuals</h2>
        <p>
          Below the numeric tables, the "Visual Evidence" section shows:
          real source cutouts for Epoch A/C/B, a sky-plane motion track
          (A → C → B), the flux-vs-wavelength spectrum, and a
          brightness-vs-time plot. Every chart is built from real,
          already-computed data; a missing value is shown as "—", never
          invented.
        </p>
      </div>

      <div className="card">
        <h2>Explore page</h2>
        <p>
          Pick an epoch and band (only the bands actually present in the
          data are offered), then scroll to zoom and drag to pan the sky
          view. Candidate markers are overlaid at their real catalogue
          positions.
        </p>
      </div>

      <div className="card">
        <h2>Clicking a source</h2>
        <p>
          Clicking a marker selects that candidate and opens its RA/Dec,
          its real per-epoch spectrum (flux vs. wavelength, with
          uncertainties where available), its catalogue cross-match
          context (matched catalogue, identifier, separation, status), and
          its motion/brightness summary — all in the side panel.
        </p>
      </div>

      <div className="card">
        <h2>Compare page: datasets</h2>
        <dl className="kv-list">
          <div>
            <dt>~6-Month Compare (primary)</dt>
            <dd>
              Jun 19, 2025 → Dec 17, 2025 (181.77 days, ~5.97 months), Epoch
              B registered onto Epoch A&apos;s pixel grid and cut to one fully
              valid common frame. Difference is B − A: positive values mean
              higher surface brightness in the later epoch.
            </dd>
          </div>
          <div>
            <dt>31-Day Compare (secondary)</dt>
            <dd>
              Epochs A / C / B (May 9 → Jun 9, 2025); only the A–B pair is
              pixel-registered and has a precomputed A − B difference.
            </dd>
          </div>
        </dl>
      </div>

      <div className="card">
        <h2>Compare page: modes</h2>
        <dl className="kv-list">
          <div>
            <dt>Side by Side</dt>
            <dd>Both selected epochs shown next to each other.</dd>
          </div>
          <div>
            <dt>Slider</dt>
            <dd>Drag a divider to reveal one epoch under the other.</dd>
          </div>
          <div>
            <dt>Blink</dt>
            <dd>Alternates between the two epochs on a timer.</dd>
          </div>
          <div>
            <dt>Difference</dt>
            <dd>
              The precomputed difference image: B − A for the ~6-month pair;
              A − B for the 31-day A/B pair (not available for pairs that
              were never registered onto a common grid).
            </dd>
          </div>
          <div>
            <dt>Overlay</dt>
            <dd>
              Red/cyan composite of both epochs so unchanged sources look
              pale and changed ones show colour.
            </dd>
          </div>
        </dl>
      </div>

      <div className="card">
        <h2>Ranking &amp; score glossary</h2>
        <dl className="kv-list">
          <div>
            <dt>Rank / priority rank</dt>
            <dd>
              A candidate's position in the final, combined priority
              ordering (lower is higher priority).
            </dd>
          </div>
          <div>
            <dt>Priority score</dt>
            <dd>
              Combines the validation score with catalogue-match and
              Solar System-check signal into one overall ranking score.
            </dd>
          </div>
          <div>
            <dt>Validation score</dt>
            <dd>
              How consistent a candidate's trajectory, motion rate, and
              flux are across the three epochs.
            </dd>
          </div>
          <div>
            <dt>Motion rate</dt>
            <dd>Apparent sky motion in arcseconds per day.</dd>
          </div>
        </dl>
      </div>

      <div className="card">
        <h2>Inspect in Explore / Open in Compare</h2>
        <p>
          On a Candidate Detail page, "Inspect in Explore" jumps to the
          Explore page with that candidate already selected and its
          evidence panel open. "Open in Compare" jumps to the Compare page
          to view epoch imagery directly.
        </p>
      </div>

      <div className="card">
        <h2>Catalogue status meanings</h2>
        <dl className="kv-list">
          <div>
            <dt>KNOWN_OBJECT</dt>
            <dd>
              A strong catalogue association explains the detections: the
              catalogue position, propagated to each observation epoch,
              agrees within the combined uncertainties, the match is unique,
              and a chance coincidence is very unlikely. This includes the
              case where each epoch is a different known star, so the
              apparent motion comes from linking unrelated stars.
            </dd>
          </div>
          <div>
            <dt>UNMATCHED_AFTER_CHECKS</dt>
            <dd>
              Every relevant, important check completed successfully and
              none produced a match.
            </dd>
          </div>
          <div>
            <dt>UNCERTAIN</dt>
            <dd>
              The evidence is not strong enough either way: a possible but
              not secure match, several plausible matches, a required check
              that could not be completed, or positions/motion that do not
              agree across epochs. Hover the status on the Candidates page
              for the specific reason. This never means "unknown" or "a new
              planet."
            </dd>
          </div>
        </dl>
      </div>

      <div className="card">
        <h2>Data source</h2>
        <p>
          All data on this site is read live from the project's FastAPI
          backend, which serves already-completed SPHEREx processing
          results. No data shown here is mocked or fabricated, and no
          candidate is a confirmed discovery.
        </p>
      </div>
    </div>
  );
}
