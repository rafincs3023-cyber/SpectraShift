import type { CatalogueStatus } from "../api/types";

/** Plain-language meaning of each status, for tooltips and legends. */
export const STATUS_HELP: Record<CatalogueStatus, string> = {
  KNOWN_OBJECT:
    "A strong catalogue association explains the detections (epoch-propagated positions, uncertainty-aware match, low chance-coincidence probability).",
  UNMATCHED_AFTER_CHECKS:
    "Every required catalogue check ran successfully at every epoch and none gave a consistent match. This is not evidence of a new or unknown object.",
  UNCERTAIN:
    "The evidence is not strong enough either way: a possible but not secure match, several plausible matches, incomplete catalogue checks, or positions/motion that do not agree across epochs.",
};
