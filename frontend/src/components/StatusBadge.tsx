import type { CatalogueStatus } from "../api/types";

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
}: {
  status: CatalogueStatus | null | undefined;
}) {
  if (!status) {
    return <span className="status-badge status-unknown">No status</span>;
  }

  return <span className={CLASS_NAMES[status]}>{LABELS[status]}</span>;
}
