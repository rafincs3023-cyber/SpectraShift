import type { ReactNode } from "react";

/** Collapsible home for secondary scientific detail: closed by default so
 * the main view stays simple, one click away for anyone who wants it. */
export function TechnicalDetails({
  summary = "Technical details",
  children,
  className,
}: {
  summary?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <details className={className ? `tech-details ${className}` : "tech-details"}>
      <summary>{summary}</summary>
      <div className="tech-details-body">{children}</div>
    </details>
  );
}
