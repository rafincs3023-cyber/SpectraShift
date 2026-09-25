import type { CandidateMarker } from "../../api/types";

/** Short on-image label: "SX6M-003" -> "#3". */
export function markerLabel(candidateId: string): string {
  const m = /-0*(\d+)$/.exec(candidateId);
  return m ? `#${m[1]}` : candidateId;
}

/** Marker class: hollow where the source is seen only in the OTHER image. */
export function markerClass(m: CandidateMarker, base = "marker-dot"): string {
  return m.detected_here === false ? `${base} marker-dot-absent` : base;
}
