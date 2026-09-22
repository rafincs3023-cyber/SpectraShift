export function LoadingState({ label = "Loading data…" }: { label?: string }) {
  return (
    <div className="state-panel state-loading" role="status">
      <div className="spinner" aria-hidden="true" />
      <p>{label}</p>
    </div>
  );
}
