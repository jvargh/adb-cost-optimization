import { useEffect, useState } from 'react';
import { Badge, Callout, Panel } from '@/components';
import { formatDuration } from '@/lib/format';
import { summarizeValidationProgress } from '@/lib/validationProgress';
import { useConfigStore } from '@/state';
import { ValidationIssueList } from './ValidationIssues';

const STATUS = {
  pending: { label: 'Waiting', tone: 'neutral' },
  running: { label: 'Running', tone: 'pending' },
  pass: { label: 'Passed', tone: 'ok' },
  warn: { label: 'Warning', tone: 'warn' },
  fail: { label: 'Failed', tone: 'danger' },
  skipped: { label: 'Not run / unavailable', tone: 'neutral' },
  'not-applicable': { label: 'Not applicable', tone: 'neutral' },
} as const;

export function ValidationProgressPanel({ compact = false, onOpen }: { compact?: boolean; onOpen?: () => void }) {
  const {
    validationProgress: progress, validationStartedAtUtc: started, validating,
    validationLastResponseAtUtc: lastResponse, validationError,
  } = useConfigStore();
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (!validating) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [validating]);
  const summary = progress ? summarizeValidationProgress(progress, now) : null;
  const finish = progress?.finishedAtUtc ? Date.parse(progress.finishedAtUtc) : now;
  const elapsedStart = progress?.startedAtUtc ?? started;
  const elapsed = elapsedStart ? formatDuration(Math.max(0, finish - Date.parse(elapsedStart)) / 1000) : '0s';
  const serverAge = lastResponse ? Math.max(0, (now - Date.parse(lastResponse)) / 1000) : null;
  const activityAge = progress ? Math.max(0, (now - Date.parse(progress.lastActivityAtUtc)) / 1000) : 0;
  const noSourceChecks = progress && progress.steps.length === 0 && !validating;
  const completedLabel = summary?.total ? `${summary.completed}/${summary.total} checks completed`
    : validating ? 'Preparing the check list' : 'No source checks ran';

  return (
    <Panel
      title={validationError ? 'Validation status unavailable' : validating ? 'Validation is running'
        : noSourceChecks ? 'Source checks did not start' : 'Validation checks finished'}
      subtitle="Step 2 checks access and reads source evidence. It does not run the analysis or create a final report."
      actions={onOpen && <button type="button" className="btn btn-ghost btn-sm" onClick={onOpen}>View validation details</button>}
    >
      <div className="stack">
        <div className="row-between" role="status" aria-live="polite">
          <strong>{completedLabel}</strong>
          <span>Elapsed: {elapsed}</span>
        </div>
        {summary && summary.total > 0 && (
          <progress className="validation-progress-bar" aria-label="Validation checks completed" max={summary.total} value={summary.completed} />
        )}
        {validationError ? (
          <Callout tone="danger" title="Do not assume validation passed">{validationError}</Callout>
        ) : validating ? (
          <>
            <span><strong>Now:</strong> {summary?.active?.title ?? progress?.message ?? 'Waiting for the local server to start validation.'}</span>
            <span><strong>Approximate time remaining:</strong>{' '}
              {summary?.overdue ? 'Unknown - this check is taking longer than estimated.'
                : summary?.eta ? `about ${summary.eta.min}-${summary.eta.max} min`
                : 'Calculating after the check list arrives; allow several minutes.'}
            </span>
            <span className="muted">This is a rough planning estimate, not a deadline. More resources, API retries, and SQL checks can make it longer.</span>
            <span className="muted">
              {serverAge === null ? 'Waiting for the first server response.'
                : serverAge > 5 ? `Waiting for the local server - last response ${formatDuration(serverAge)} ago.`
                : 'Local server is responding.'}
              {progress && ` Last check activity: ${formatDuration(activityAge)} ago.`}
            </span>
            {(summary?.overdue || activityAge >= 60) && (
              <Callout tone="warn" title="Waiting for this check to return">
                {summary?.active?.title ?? 'The current check'} has not finished. The server may be waiting for Azure or Databricks.
                No completed checks are being assumed. You can browse other steps; do not start another validation.
              </Callout>
            )}
            {progress?.message && !compact && <span className="validation-activity">{progress.message}</span>}
          </>
        ) : null}
        <span className="muted">Completed means finished, not necessarily passed. Warnings, failures, and unavailable checks are listed separately.</span>
        {!compact && progress && (
          <ol className="validation-check-list">
            {progress.steps.map((check) => (
              <li key={check.id}>
                <div className="row-between">
                  <strong>{check.title}</strong>
                  <Badge tone={STATUS[check.status].tone}>{STATUS[check.status].label}</Badge>
                </div>
                <span className="muted">{check.detail}</span>
                {check.issues && check.issues.length > 0 && <ValidationIssueList checks={check.issues} />}
                {check.startedAtUtc && (
                  <span className="muted">Time: {formatDuration(Math.max(0, (Date.parse(check.finishedAtUtc ?? new Date(now).toISOString()) - Date.parse(check.startedAtUtc))) / 1000)}</span>
                )}
              </li>
            ))}
          </ol>
        )}
      </div>
    </Panel>
  );
}
