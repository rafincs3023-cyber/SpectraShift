import { Link, useSearchParams } from "react-router-dom";
import {
  COMPARE_MODES,
  type CompareMode,
} from "../components/compare/compareModes";
import { SixMonthCompare } from "../components/compare/SixMonthCompare";
import { PageIntro } from "../components/ui/PageIntro";

/** Time Compare: the two real SPHEREx observations of the same sky taken
 * about six months apart (Jun 19 and Dec 17, 2025). The viewing mode lives
 * in ?mode= so any view can be linked. */
export function Compare() {
  const [searchParams, setSearchParams] = useSearchParams();
  const modeParam = searchParams.get("mode");
  const mode: CompareMode = COMPARE_MODES.includes(modeParam as CompareMode)
    ? (modeParam as CompareMode)
    : "side-by-side";

  const setMode = (next: CompareMode) =>
    setSearchParams(next === "side-by-side" ? {} : { mode: next }, { replace: true });

  return (
    <div className="page compare-page">
      <PageIntro
        eyebrow="SPHEREx · Same sky, about six months apart"
        title="Time Compare"
        lead="Compare the same sky observed on June 19 and December 17, 2025."
        what="Shows the two real SPHEREx images of this sky, taken about six months apart and lined up exactly."
        how="Switch between the viewing modes: side by side, slider, blink, difference and overlay."
        result="Anything that looks different may have changed or moved — but a visible difference does not automatically mean that an object moved."
      />

      <div className="view-scope-note">
        <strong>Time Compare</strong> = same sky, <em>different dates</em>.{" "}
        <strong>Spectral View</strong> = same sky, <em>different wavelengths</em> —{" "}
        <Link to="/spectral">open Spectral View</Link>.
      </div>

      <SixMonthCompare mode={mode} onModeChange={setMode} />
    </div>
  );
}
