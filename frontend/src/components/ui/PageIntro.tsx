import type { ReactNode } from "react";

/** Page header with a one-line lead and three short helper points:
 * what the page does, what to do, and what the result means. */
export function PageIntro({
  eyebrow,
  title,
  lead,
  what,
  how,
  result,
}: {
  eyebrow?: string;
  title: string;
  lead: ReactNode;
  what?: ReactNode;
  how?: ReactNode;
  result?: ReactNode;
}) {
  const steps = [
    { label: "What this page does", body: what },
    { label: "What to do", body: how },
    { label: "What the result means", body: result },
  ].filter((s) => s.body);
  return (
    <header className="page-intro">
      {eyebrow && <p className="eyebrow">{eyebrow}</p>}
      <h1>{title}</h1>
      <p className="page-intro-lead">{lead}</p>
      {steps.length > 0 && (
        <ol className="page-intro-steps">
          {steps.map((s) => (
            <li key={s.label}>
              <span className="page-intro-step-label">{s.label}</span>
              <span className="page-intro-step-body">{s.body}</span>
            </li>
          ))}
        </ol>
      )}
    </header>
  );
}
