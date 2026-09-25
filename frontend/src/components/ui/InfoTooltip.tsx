import { useEffect, useId, useRef, useState } from "react";
import { GLOSSARY, type GlossaryKey } from "./glossary";

const MARGIN = 8; // px kept clear of the viewport edges

/** Small "i" help icon. The explanation opens on hover, keyboard focus or
 * tap, is linked to the icon for screen readers, and is positioned against
 * the viewport: above the icon when there is room, otherwise below, and
 * shifted sideways so it is never clipped at a screen edge. */
export function InfoTooltip({
  term,
  text,
  label,
}: {
  /** a glossary entry, or pass `text` directly */
  term?: GlossaryKey;
  text?: string;
  /** accessible name, defaults to "What is <term>?" */
  label?: string;
}) {
  const id = useId();
  const entry = term ? GLOSSARY[term] : null;
  const body = text ?? entry?.text ?? "";
  const name = label ?? (entry ? `What is ${entry.term}?` : "More information");

  const iconRef = useRef<HTMLButtonElement>(null);
  const bubbleRef = useRef<HTMLSpanElement>(null);
  const [pos, setPos] = useState<{ left: number; top: number; below: boolean } | null>(null);

  function show() {
    const icon = iconRef.current?.getBoundingClientRect();
    const bubble = bubbleRef.current?.getBoundingClientRect();
    if (!icon || !bubble) return;
    let top = icon.top - bubble.height - MARGIN;
    let below = false;
    if (top < MARGIN) {
      top = icon.bottom + MARGIN;
      below = true;
    }
    const maxLeft = window.innerWidth - bubble.width - MARGIN;
    const left = Math.max(MARGIN, Math.min(icon.left + icon.width / 2 - bubble.width / 2, maxLeft));
    setPos({ left, top, below });
  }
  const hide = () => setPos(null);

  // The bubble is fixed-position, so it is re-placed whenever the page
  // scrolls or resizes (including the scroll a browser makes to bring a
  // focused icon into view); Escape closes it.
  const isOpen = pos !== null;
  useEffect(() => {
    if (!isOpen) return;
    let frame = 0;
    const reposition = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(show);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setPos(null);
    };
    window.addEventListener("scroll", reposition, true);
    window.addEventListener("resize", reposition);
    window.addEventListener("keydown", onKey);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("scroll", reposition, true);
      window.removeEventListener("resize", reposition);
      window.removeEventListener("keydown", onKey);
    };
    // show() only reads refs, so re-subscribing on open/close is enough
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen]);

  return (
    <span className="info-tip" onMouseEnter={show} onMouseLeave={hide}>
      <button
        ref={iconRef}
        type="button"
        className="info-tip-icon"
        aria-label={name}
        aria-describedby={id}
        aria-expanded={pos !== null}
        onFocus={show}
        onBlur={hide}
        onClick={() => (pos ? hide() : show())}
      >
        i
      </button>
      <span
        ref={bubbleRef}
        role="tooltip"
        id={id}
        className={pos ? `info-tip-bubble is-open${pos.below ? " is-below" : ""}` : "info-tip-bubble"}
        style={pos ? { left: pos.left, top: pos.top } : undefined}
      >
        {body}
      </span>
    </span>
  );
}
