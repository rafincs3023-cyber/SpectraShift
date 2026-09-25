import { useState } from "react";
import { imageUrl } from "../../api/client";
import type { CandidateCutoutSet } from "../../api/types";

const PANELS = [
  { key: "earlier", label: "Earlier image" },
  { key: "later", label: "Later image" },
  { key: "difference", label: "Later − Earlier" },
] as const;

/** Earlier, later and difference cutouts around one position. */
export function CandidateCutouts({
  set,
  candidateId,
  dates,
}: {
  set: CandidateCutoutSet;
  candidateId: string;
  dates: { earlier: string; later: string };
}) {
  const [failed, setFailed] = useState<Record<string, boolean>>({});

  return (
    <div className="cutout-grid">
      {PANELS.map((p) => (
        <div key={p.key} className="cutout-card">
          <div className="obs-epoch-chip cutout-chip">
            {p.label}
            {p.key !== "difference" && ` · ${dates[p.key]}`}
          </div>
          {failed[p.key] ? (
            <div className="cutout-unavailable">Image unavailable</div>
          ) : (
            <img
              src={imageUrl(set[p.key])}
              alt={`${p.label} around ${candidateId}'s ${set.at} position`}
              className="cutout-image"
              onError={() => setFailed((f) => ({ ...f, [p.key]: true }))}
            />
          )}
        </div>
      ))}
    </div>
  );
}
