import type { CompareMode } from "./compareModes";

const MODES: { key: CompareMode; label: string; hint: string }[] = [
  { key: "side-by-side", label: "Side by side", hint: "Both images next to each other." },
  { key: "slider", label: "Slider", hint: "Drag the divider to wipe between the earlier and the later image." },
  { key: "blink", label: "Blink", hint: "The two images swap back and forth, so anything that changed appears to flicker." },
  { key: "difference", label: "Difference", hint: "Shows only what changed between the two images." },
  { key: "overlay", label: "Overlay", hint: "Both images in one picture: unchanged stars look white, changes show as red or cyan." },
];

export function ModeTabs({
  mode,
  onChange,
}: {
  mode: CompareMode;
  onChange: (mode: CompareMode) => void;
}) {
  const active = MODES.find((m) => m.key === mode);
  return (
    <>
      <div className="mode-tabs" role="tablist" aria-label="How to compare the images">
        {MODES.map((m) => (
          <button
            key={m.key}
            type="button"
            role="tab"
            aria-selected={mode === m.key}
            title={m.hint}
            className={mode === m.key ? "mode-tab mode-tab-active" : "mode-tab"}
            onClick={() => onChange(m.key)}
          >
            {m.label}
          </button>
        ))}
      </div>
      {active && (
        <p className="mode-hint">
          <strong>{active.label}:</strong> {active.hint}
        </p>
      )}
    </>
  );
}
