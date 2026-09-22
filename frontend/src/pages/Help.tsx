export function Help() {
  return (
    <div className="page">
      <div className="page-header">
        <h1>Help</h1>
        <p className="page-subtitle">How to read this site.</p>
      </div>

      <div className="card">
        <h2>Candidates page</h2>
        <p>
          Lists every validated three-epoch motion candidate, ranked by
          final priority score. Click any candidate ID to see its full
          evidence: per-epoch positions, motion rate, trajectory validation
          scores, and the full catalogue cross-match audit trail.
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
              Shows the precomputed Epoch A − Epoch B difference image
              when that exact pair is selected; not available for other
              pairs, since no difference was computed for them.
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
              A catalogue match was found that plausibly explains this
              candidate (e.g. the same object recurring across epochs).
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
              An important check (such as the full Solar System minor-body
              catalogue search) could not be completed, so absence of a
              match cannot be treated as conclusive. This never means
              "unknown" or "a new planet."
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
