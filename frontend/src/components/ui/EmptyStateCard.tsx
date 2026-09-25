import type { ReactNode } from "react";

/** An informative "nothing to show" state: what happened, and what the user
 * can do next. `tone="result"` is for a finished analysis with no findings. */
export function EmptyStateCard({
  title,
  children,
  actions,
  tone = "neutral",
}: {
  title: ReactNode;
  children?: ReactNode;
  actions?: ReactNode;
  tone?: "neutral" | "result";
}) {
  return (
    <div className={`empty-card empty-card-${tone}`} role="status">
      <p className="empty-card-title">{title}</p>
      {children && <div className="empty-card-body">{children}</div>}
      {actions && <div className="empty-card-actions">{actions}</div>}
    </div>
  );
}
