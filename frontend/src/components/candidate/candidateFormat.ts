import type { CandidateKind, TwoEpochCandidate } from "../../api/types";

export function fmt(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return value.toFixed(digits);
}

/** Backend dates are UTC without a zone suffix. */
export function parseUtc(iso: string): Date {
  return new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : `${iso}Z`);
}

/** "Jun 19, 2025" */
export function shortDate(iso: string | null | undefined): string {
  if (!iso) return "unknown date";
  return parseUtc(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  });
}

/** "June 19, 2025" */
export function longDate(iso: string | null | undefined): string {
  if (!iso) return "unknown date";
  return parseUtc(iso).toLocaleDateString("en-US", {
    month: "long",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  });
}

/** One plain sentence per candidate type. */
export const KIND_EXPLANATION: Record<CandidateKind, string> = {
  possible_position_change:
    "A source seen only in the earlier image, paired with a similar source seen only in the later image — possibly one object that changed position.",
  shifted_match:
    "The same source appears in both images, but its measured position shifted a little more than the measurement scatter allows.",
  seen_only_earlier:
    "A source visible in the earlier image that was not found at the same place in the later image.",
  seen_only_later:
    "A source visible in the later image that was not found at the same place in the earlier image.",
};

/** Displacement text, or why there is none. */
export function displacementText(c: TwoEpochCandidate): string {
  if (c.angular_displacement_arcsec === null) return "— (seen in one image only)";
  return `${fmt(c.angular_displacement_arcsec, 1)}″`;
}

export function rateText(c: TwoEpochCandidate): string {
  if (c.apparent_motion_arcsec_per_day === null) return "—";
  return `${fmt(c.apparent_motion_arcsec_per_day, 3)}″ per day`;
}

/** Highest signal-to-noise of the candidate's detections. */
export function bestSnr(c: TwoEpochCandidate): number | null {
  const values = [c.earlier?.snr, c.later?.snr].filter((v): v is number => typeof v === "number");
  return values.length ? Math.max(...values) : null;
}
