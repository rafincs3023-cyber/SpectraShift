import type { CompareMode } from "./compareModes";

const MODES: { key: CompareMode; label: string }[] = [
  { key: "side-by-side", label: "Side by Side" },
  { key: "slider", label: "Slider" },
  { key: "blink", label: "Blink" },
  { key: "difference", label: "Difference" },
  { key: "overlay", label: "Overlay" },
];

export function ModeTabs({
  mode,
  onChange,
}: {
  mode: CompareMode;
  onChange: (mode: CompareMode) => void;
}) {
  return (
    <div className="mode-tabs" role="tablist" aria-label="Comparison mode">
      {MODES.map((m) => (
        <button
          key={m.key}
          type="button"
          role="tab"
          aria-selected={mode === m.key}
          className={mode === m.key ? "mode-tab mode-tab-active" : "mode-tab"}
          onClick={() => onChange(m.key)}
        >
          {m.label}
        </button>
      ))}
    </div>
  );
}
