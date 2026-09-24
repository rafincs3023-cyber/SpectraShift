import type { CatalogueStatus } from "../api/types";
import { STATUS_HELP } from "./statusHelp";

const LABELS: Record<CatalogueStatus, string> = {
  KNOWN_OBJECT: "Known Object",
  UNMATCHED_AFTER_CHECKS: "Unmatched After Checks",
  UNCERTAIN: "Uncertain",
};

const CLASS_NAMES: Record<CatalogueStatus, string> = {
  KNOWN_OBJECT: "status-badge status-known",
  UNMATCHED_AFTER_CHECKS: "status-badge status-unmatched",
  UNCERTAIN: "status-badge status-uncertain",
};

export function StatusBadge({
  status,
  reason,
}: {
  status: CatalogueStatus | null | undefined;
  /** Candidate-specific reason, appended to the status meaning in the tooltip. */
  reason?: string | null;
}) {
  if (!status) {
    return <span className="status-badge status-unknown">No status</span>;
  }

  const title = reason
    ? `${STATUS_HELP[status]}\n\nWhy: ${reason}`
    : STATUS_HELP[status];
  return (
    <span className={CLASS_NAMES[status]} title={title}>
      {LABELS[status]}
    </span>
  );
}
