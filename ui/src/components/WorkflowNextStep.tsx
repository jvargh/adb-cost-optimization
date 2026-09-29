export function WorkflowNextStep({
  title,
  detail,
  actionLabel,
  onAction,
}: {
  title: string;
  detail: string;
  actionLabel: string;
  onAction: () => void;
}) {
  return (
    <section className="workflow-next" aria-label="Next step">
      <div className="workflow-next-text">
        <span className="field-label">Next step</span>
        <strong>{title}</strong>
        <span className="muted">{detail}</span>
      </div>
      <button type="button" className="btn btn-primary" onClick={onAction}>
        {actionLabel}
      </button>
    </section>
  );
}
