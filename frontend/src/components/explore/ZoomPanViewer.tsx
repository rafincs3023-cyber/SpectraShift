import { useEffect, useRef, useState, type ReactNode, type MouseEvent } from "react";

const MIN_SCALE = 1;
const MAX_SCALE = 6;

export function ZoomPanViewer({ children }: { children: ReactNode }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(1);
  const [tx, setTx] = useState(0);
  const [ty, setTy] = useState(0);
  const dragging = useRef(false);
  const lastPos = useRef({ x: 0, y: 0 });

  function zoomAt(clientX: number, clientY: number, factor: number) {
    const el = containerRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const mouseX = clientX - rect.left;
    const mouseY = clientY - rect.top;

    setScale((prevScale) => {
      const newScale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, prevScale * factor));
      if (newScale === prevScale) return prevScale;

      setTx((prevTx) => {
        const contentX = (mouseX - prevTx) / prevScale;
        return mouseX - contentX * newScale;
      });
      setTy((prevTy) => {
        const contentY = (mouseY - prevTy) / prevScale;
        return mouseY - contentY * newScale;
      });

      if (newScale === MIN_SCALE) {
        setTx(0);
        setTy(0);
      }

      return newScale;
    });
  }

  // React's synthetic onWheel is attached as a passive listener, so
  // e.preventDefault() inside it silently fails (and logs a console
  // error) -- the page would scroll underneath while zooming. A native
  // listener with { passive: false } is required to actually block it.
  const zoomAtRef = useRef(zoomAt);
  zoomAtRef.current = zoomAt;

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    function handleNativeWheel(e: globalThis.WheelEvent) {
      e.preventDefault();
      const factor = e.deltaY < 0 ? 1.2 : 1 / 1.2;
      zoomAtRef.current(e.clientX, e.clientY, factor);
    }

    el.addEventListener("wheel", handleNativeWheel, { passive: false });
    return () => el.removeEventListener("wheel", handleNativeWheel);
  }, []);

  function handleMouseDown(e: MouseEvent<HTMLDivElement>) {
    if (scale <= MIN_SCALE) return;
    dragging.current = true;
    lastPos.current = { x: e.clientX, y: e.clientY };
  }

  function handleMouseMove(e: MouseEvent<HTMLDivElement>) {
    if (!dragging.current) return;
    const dx = e.clientX - lastPos.current.x;
    const dy = e.clientY - lastPos.current.y;
    lastPos.current = { x: e.clientX, y: e.clientY };
    setTx((v) => v + dx);
    setTy((v) => v + dy);
  }

  function stopDragging() {
    dragging.current = false;
  }

  function reset() {
    setScale(1);
    setTx(0);
    setTy(0);
  }

  function zoomButton(factor: number) {
    const el = containerRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    zoomAt(rect.left + rect.width / 2, rect.top + rect.height / 2, factor);
  }

  return (
    <div className="zoom-pan-wrap">
      <div
        ref={containerRef}
        className="zoom-pan-viewport"
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={stopDragging}
        onMouseLeave={stopDragging}
        style={{ cursor: scale > MIN_SCALE ? "grab" : "default" }}
      >
        <div
          className="zoom-pan-content"
          style={{
            transform: `translate(${tx}px, ${ty}px) scale(${scale})`,
            transformOrigin: "0 0",
          }}
        >
          {children}
        </div>
      </div>

      <div className="zoom-pan-controls">
        <button type="button" className="btn btn-secondary" onClick={() => zoomButton(1 / 1.4)}>
          − Zoom out
        </button>
        <span className="zoom-pan-scale">{scale.toFixed(1)}×</span>
        <button type="button" className="btn btn-secondary" onClick={() => zoomButton(1.4)}>
          + Zoom in
        </button>
        <button type="button" className="btn btn-secondary" onClick={reset}>
          Reset view
        </button>
        <span className="section-note zoom-pan-hint">
          Scroll to zoom · drag to pan
        </span>
      </div>
    </div>
  );
}
