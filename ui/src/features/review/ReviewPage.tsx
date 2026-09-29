import { useMemo, useState } from 'react';
import { Badge, Callout, EmptyState, KpiCard, Panel, WorkflowNextStep } from '@/components';
import { useResultsStore } from '@/state';
import { formatDateTime } from '@/lib/format';
import type { ReviewDecision, ReviewEntry } from '@/types';

const DECISIONS: ReviewDecision[] = ['pending', 'accepted', 'rejected', 'deferred'];

const DECISION_TONE: Record<ReviewDecision, 'ok' | 'danger' | 'warn' | 'pending'> = {
  accepted: 'ok',
  rejected: 'danger',
  deferred: 'warn',
  pending: 'pending',
};

export function ReviewPage({ onExport }: { onExport: () => void }) {
  const { results, saveReview } = useResultsStore();
  const [draft, setDraft] = useState<ReviewEntry[] | null>(null);
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const [showReport, setShowReport] = useState(false);

  const entries = draft ?? results?.review ?? [];
  const progress = useMemo(() => getReviewProgress(entries), [entries]);
  const canSignOff = progress.complete;

  if (!results) {
    return (
      <EmptyState
        title="No assessment run is open"
        detail="Open a run on the Visualize Results step before recording review decisions."
      />
    );
  }

  const update = (index: number, patch: Partial<ReviewEntry>) => {
    const next = entries.map((entry, i) => (i === index ? { ...entry, ...patch } : entry));
    setDraft(next);
    setSavedAt(null);
  };

  const save = async () => {
    setSaving(true);
    try {
      await saveReview(entries);
      setSavedAt(new Date().toISOString());
      setDraft(null);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="stack-lg">
      <Callout tone="warn" title="Every finding needs a named reviewer">
        For each finding, choose a decision and enter the reviewer name. Add the supporting details
        before acting on the finding. Saved reviews are included in{' '}
        <span className="mono">human-validation-sign-off.csv</span>.
      </Callout>

      <div className="grid-3">
        <KpiCard label="Findings to review" value={entries.length} accent="neutral" />
        <KpiCard
          label="Decisions recorded"
          value={`${progress.decisionCount} / ${entries.length}`}
          accent={progress.pendingDecisionCount === 0 && entries.length > 0 ? 'ok' : 'warn'}
        />
        <KpiCard
          label="Sign-off"
          value={canSignOff ? 'Ready' : 'Incomplete'}
          note={
            canSignOff
              ? draft
                ? 'All required fields are complete. Save the review.'
                : 'Every finding has a saved decision and reviewer.'
              : reviewProgressMessage(progress)
          }
          accent={canSignOff ? 'ok' : 'warn'}
        />
      </div>

      {!canSignOff && (
        <Callout tone="info" title="Review is not complete">
          <ul className="validation-issue-list">
            {progress.pendingDecisionCount > 0 && (
              <li>
                <strong>
                  {progress.pendingDecisionCount}{' '}
                  {progress.pendingDecisionCount === 1 ? 'finding needs' : 'findings need'} a decision.
                </strong>
                <span>Choose Accepted, Rejected, or Deferred.</span>
              </li>
            )}
            {progress.missingReviewerCount > 0 && (
              <li>
                <strong>
                  {progress.missingReviewerCount}{' '}
                  {progress.missingReviewerCount === 1 ? 'reviewer name is' : 'reviewer names are'} missing.
                </strong>
                <span>Enter the name of the person who reviewed each finding.</span>
              </li>
            )}
          </ul>
        </Callout>
      )}
      {canSignOff && !draft && (
        <Callout tone="ok" title="Review complete">
          Every finding has a saved decision and reviewer. Step 5 is complete.
        </Callout>
      )}

      {entries.map((entry, index) => (
        <Panel
          key={entry.findingId}
          title={entry.finding}
          subtitle={<span className="mono">{entry.findingId}</span>}
          actions={<Badge tone={DECISION_TONE[entry.decision]}>{entry.decision}</Badge>}
        >
          <div className="stack">
            <div className="grid-3">
              <label className="field">
                <span className="field-label">Decision</span>
                <select
                  className="select"
                  value={entry.decision}
                  onChange={(e) => update(index, { decision: e.target.value as ReviewDecision })}
                >
                  {DECISIONS.map((d) => (
                    <option key={d} value={d}>
                      {d}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span className="field-label">Reviewer</span>
                <input
                  className={`input ${
                    entry.decision !== 'pending' && !entry.reviewer.trim() ? 'input-invalid' : ''
                  }`}
                  value={entry.reviewer}
                  placeholder="Name of the person accountable"
                  aria-invalid={entry.decision !== 'pending' && !entry.reviewer.trim()}
                  onChange={(e) =>
                    update(index, {
                      reviewer: e.target.value,
                      reviewedAtUtc: e.target.value ? new Date().toISOString() : null,
                    })
                  }
                />
                {entry.decision !== 'pending' && !entry.reviewer.trim() && (
                  <span className="field-error">Reviewer name is required.</span>
                )}
              </label>
              <label className="field">
                <span className="field-label">Role</span>
                <input
                  className="input"
                  value={entry.role}
                  placeholder="Platform owner, data engineering lead, FinOps"
                  onChange={(e) => update(index, { role: e.target.value })}
                />
              </label>
            </div>

            <div className="grid-2">
              <ReviewField
                label="Business and SLA context"
                hint="What does this workload promise the business, and when?"
                value={entry.businessSlaContext}
                onChange={(v) => update(index, { businessSlaContext: v })}
              />
              <ReviewField
                label="Performance and reliability risk"
                hint="What could degrade if this change is made?"
                value={entry.performanceReliabilityRisk}
                onChange={(v) => update(index, { performanceReliabilityRisk: v })}
              />
              <ReviewField
                label="Security and governance impact"
                hint="Does this touch access, isolation, retention, or audit?"
                value={entry.securityGovernanceImpact}
                onChange={(v) => update(index, { securityGovernanceImpact: v })}
              />
              <ReviewField
                label="Validation experiment"
                hint="The measurable test that proves the change is safe and beneficial."
                value={entry.validationExperiment}
                onChange={(v) => update(index, { validationExperiment: v })}
              />
              <ReviewField
                label="Owner and approver"
                hint="Who executes, and who signs off."
                value={entry.ownerApprover}
                onChange={(v) => update(index, { ownerApprover: v })}
              />
              <ReviewField
                label="Rationale"
                hint="Why this decision was reached."
                value={entry.rationale}
                onChange={(v) => update(index, { rationale: v })}
              />
            </div>

            {entry.evidenceLinks.length > 0 && (
              <div className="stack-sm">
                <span className="field-label">Evidence</span>
                {entry.evidenceLinks.map((link) => (
                  <span className="mono muted" key={link}>
                    {link}
                  </span>
                ))}
              </div>
            )}

            {entry.reviewedAtUtc && (
              <span className="muted">Last updated {formatDateTime(entry.reviewedAtUtc)}</span>
            )}
          </div>
        </Panel>
      ))}

      <Panel
        title="Consolidated report"
        subtitle="The single Markdown deliverable produced by this run."
        actions={
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => setShowReport(!showReport)}>
            {showReport ? 'Hide preview' : 'Preview report'}
          </button>
        }
        footer={
          <div className="row-between">
            <span className="muted">
              {savedAt ? `Review saved ${formatDateTime(savedAt)}.` : draft ? 'Unsaved changes.' : 'No unsaved changes.'}
            </span>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => void save()}
              disabled={saving || !draft}
            >
              {saving ? 'Saving...' : 'Save review decisions'}
            </button>
          </div>
        }
      >
        {showReport ? (
          <pre className="markdown-preview">{results.reportMarkdown}</pre>
        ) : (
          <span className="muted">
            The report is regenerated by the backend, not by this UI. Saving review decisions updates
            the sign-off register without rewriting the analysis.
          </span>
        )}
      </Panel>

      <WorkflowNextStep
        title="Download the report and evidence"
        detail={
          canSignOff && !draft
            ? 'The review is complete. Download the files needed for the customer handoff.'
            : 'You can inspect exports now, but complete and save the review before using the findings.'
        }
        actionLabel="Continue to export"
        onAction={onExport}
      />
    </div>
  );
}

export function getReviewProgress(entries: ReviewEntry[]) {
  const decisionCount = entries.filter((entry) => entry.decision !== 'pending').length;
  const pendingDecisionCount = entries.length - decisionCount;
  const missingReviewerCount = entries.filter(
    (entry) => entry.decision !== 'pending' && !entry.reviewer.trim(),
  ).length;

  return {
    decisionCount,
    pendingDecisionCount,
    missingReviewerCount,
    complete:
      entries.length > 0 && pendingDecisionCount === 0 && missingReviewerCount === 0,
  };
}

function reviewProgressMessage(progress: ReturnType<typeof getReviewProgress>): string {
  if (progress.pendingDecisionCount > 0 && progress.missingReviewerCount > 0) {
    const decisions =
      progress.pendingDecisionCount === 1
        ? '1 decision is missing'
        : `${progress.pendingDecisionCount} decisions are missing`;
    const reviewers =
      progress.missingReviewerCount === 1
        ? '1 reviewer name is missing'
        : `${progress.missingReviewerCount} reviewer names are missing`;
    return `${decisions}, and ${reviewers}.`;
  }
  if (progress.pendingDecisionCount > 0) {
    return progress.pendingDecisionCount === 1
      ? '1 decision is missing.'
      : `${progress.pendingDecisionCount} decisions are missing.`;
  }
  return progress.missingReviewerCount === 1
    ? '1 reviewer name is missing.'
    : `${progress.missingReviewerCount} reviewer names are missing.`;
}

function ReviewField({
  label,
  hint,
  value,
  onChange,
}: {
  label: string;
  hint: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      <textarea className="textarea" rows={2} value={value} onChange={(e) => onChange(e.target.value)} />
      <span className="field-hint">{hint}</span>
    </label>
  );
}
