import { useState } from "react";
import { imageUrl } from "../../api/client";

const EPOCHS = ["A", "C", "B"] as const;

export function CandidateCutouts({ candidateId }: { candidateId: string }) {
  const [failed, setFailed] = useState<Record<string, boolean>>({});

  return (
    <div className="cutout-grid">
      {EPOCHS.map((epoch) => (
        <div key={epoch} className="cutout-card">
          <div className="obs-epoch-chip cutout-chip">Epoch {epoch}</div>
          {failed[epoch] ? (
            <div className="cutout-unavailable">Data unavailable</div>
          ) : (
            <img
              src={imageUrl(`/api/candidates/${encodeURIComponent(candidateId)}/cutout/${epoch}`)}
              alt={`Cutout of candidate ${candidateId} at Epoch ${epoch}`}
              className="cutout-image"
              onError={() => setFailed((f) => ({ ...f, [epoch]: true }))}
            />
          )}
        </div>
      ))}
    </div>
  );
}
