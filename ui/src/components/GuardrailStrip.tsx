/**
 * Always-visible reminder of the assessment guardrails. These are contractual,
 * not decorative: assessment is read-only, scope-isolated, and every finding
 * requires human validation before any action is taken.
 */
export function GuardrailStrip() {
  return (
    <div className="guardrail-strip">
      <span>Read-only assessment &mdash; permission setup is separate and confirmed</span>
      <span>Scope-isolated to the selected resource groups</span>
      <span>Savings are never estimated without human validation</span>
      <span>Absent evidence is reported, never rendered as zero</span>
    </div>
  );
}

export function MockBanner({
  scenarioLabel,
  onOpenScenarios,
}: {
  scenarioLabel: string;
  onOpenScenarios?: () => void;
}) {
  return (
    <div className="mock-banner">
      <strong>Phase 1 prototype</strong>
      <span>
        Every number on screen comes from deterministic fixtures, not a live tenant. Active
        scenario: <strong>{scenarioLabel}</strong>.
      </span>
      {onOpenScenarios && (
        <button type="button" className="btn btn-ghost btn-sm" onClick={onOpenScenarios}>
          Switch scenario
        </button>
      )}
    </div>
  );
}
