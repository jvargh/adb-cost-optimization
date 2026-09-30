import { useEffect, useRef, useState } from 'react';
import { Badge, Callout, KeyValue, Panel, StatusBadge, WorkflowNextStep } from '@/components';
import { useConfigStore, useRunStore, PHASE_ORDER, phaseIndex } from '@/state';
import { STATUS_MEANING, formatDateTime, elapsedBetween, formatNumber } from '@/lib/format';
import type { CollectionSource, RunPhase } from '@/types';
import { getCollectionOutcome } from '@/features/results/CollectionOutcome';

const PHASE_LABELS: Record<string, string> = {
  preflight: 'Pre-flight',
  collecting: 'Collect',
  normalizing: 'Normalize',
  analyzing: 'Analyze',
  findings: 'Findings',
  reporting: 'Report',
  completed: 'Complete',
};

export function RunPage({ onViewResults, onValidate }: { onViewResults: (runId: string) => void; onValidate?: () => void }) {
  const { config, approvals, validation, validating, validationError } = useConfigStore();
  const { phase, sources, console: lines, start, cancel, reset, runId, handle, startedAtUtc, finishedAtUtc, error } =
    useRunStore();
  const consoleRef = useRef<HTMLDivElement>(null);
  const [now, setNow] = useState(new Date().toISOString());
  useEffect(() => {
    if (['idle', 'completed', 'failed', 'canceled'].includes(phase)) return;
    const timer = window.setInterval(() => setNow(new Date().toISOString()), 1000);
    return () => window.clearInterval(timer);
  }, [phase]);

  useEffect(() => {
    const node = consoleRef.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, [lines.length]);

  if (!config) {
    return <Callout tone="warn" title="Nothing configured">Configure a scope before running.</Callout>;
  }

  const running = phase !== 'idle' && phase !== 'completed' && phase !== 'failed' && phase !== 'canceled';
  const included = config.databricks.workspaces.filter((w) => w.include);
  const outcome = getCollectionOutcome({ manifest: { status: 'passed' }, collection: sources });

  return (
    <div className="stack-lg">
      {!validation?.canRun && phase === 'idle' && (
        <Callout tone={validating ? 'info' : 'warn'} title={validating ? 'Analysis has not started - validation is still running' : validationError ? 'Validation stopped - analysis has not started' : 'Validate before starting a new run'}>
          {validating ? 'Wait for step 2 to finish. You do not need to start it again.' : 'Open step 2 to check the status and resolve any blocking items.'}
          {onValidate && <button type="button" className="btn btn-ghost btn-sm" onClick={onValidate}>Go to validation</button>}
        </Callout>
      )}

      {phase === 'idle' && (
        <Panel
          title="Pre-flight summary"
          subtitle="Exactly what this run will read. Nothing outside this scope is touched."
          footer={
            <div className="row-between">
              <span className="muted">
                Equivalent command:{' '}
                <span className="mono">
                  ./assessment/Invoke-Assessment.ps1 -Action Run
                  {approvals.approveSqlWarehouseAutoStart ? ' -ApproveSqlWarehouseAutoStart' : ''}
                  {approvals.continueOnCollectorError ? ' -ContinueOnCollectorError' : ' -FailOnCollectorError'}
                </span>
              </span>
              <button
                type="button"
                className="btn btn-primary"
                disabled={validating || !validation?.canRun}
                onClick={() => void start()}
              >
                Start read-only assessment
              </button>
            </div>
          }
        >
          <KeyValue
            items={[
              { label: 'Customer', value: `${config.customerId} / ${config.assessmentId}` },
              { label: 'Subscriptions', value: config.azure.subscriptions.join(', ') || 'None' },
              { label: 'Resource groups', value: config.azure.resourceGroups.join(', ') || 'None' },
              { label: 'Workspaces', value: included.map((w) => w.name).join(', ') || 'None' },
              {
                label: 'Window',
                value: `${config.analysis.startUtc} to ${config.analysis.endUtc} (${config.analysis.timeZone})`,
              },
              { label: 'Cost basis', value: config.azure.costBasis.join(' + ') },
              { label: 'Analysis modules', value: config.capabilities?.modules.join(', ') ?? 'Standard capability analysis' },
              { label: 'Collection profile / concurrency', value: `${config.capabilities?.profile ?? 'standard'} / ${config.capabilities?.concurrency ?? 1}` },
              { label: 'Optional asset types', value: config.capabilities?.assets.join(', ') || 'Not selected' },
              { label: 'Output root', value: <span className="mono">{config.outputs.root}</span> },
              {
                label: 'SQL Warehouse auto-start',
                value: approvals.approveSqlWarehouseAutoStart ? 'Approved' : 'Not approved',
              },
            ]}
          />
        </Panel>
      )}

      {phase !== 'idle' && (
        <>
          <Panel
            title="Progress"
            subtitle={
              startedAtUtc
                ? `Started ${formatDateTime(startedAtUtc)} \u00b7 elapsed ${elapsedBetween(startedAtUtc, finishedAtUtc ?? now)}`
                : undefined
            }
            actions={
              running ? (
                <button
                  type="button"
                  className="btn btn-danger btn-sm"
                  disabled={!handle}
                  onClick={() => void cancel()}
                >
                  Cancel run
                </button>
              ) : (
                <button type="button" className="btn btn-ghost btn-sm" onClick={reset}>
                  Start over
                </button>
              )
            }
          >
            <PhaseTrack phase={phase} />
            {phase === 'failed' && (
              <Callout tone="danger" title="Run failed">
                {error ?? 'The assessment stopped before producing a complete result set.'}
              </Callout>
            )}
            {phase === 'canceled' && (
              <Callout tone="warn" title="Run canceled">
                The backend has no whole-run cancellation checkpoint. The child process was
                terminated and the run is marked partial; artifacts written before cancellation
                remain on disk.
              </Callout>
            )}
            {phase === 'completed' && runId && (
              <Callout tone={outcome.needsAttention ? 'danger' : 'ok'} title="Assessment finished - snapshot saved">
                Run <span className="mono">{runId}</span> finished with{' '}
                {sources.filter((s) => s.status === 'passed').length} of {sources.length} sources
                fully passed. Scope, evidence, findings, and report are saved automatically. Use Saved snapshots to reopen this run without collecting again.
              </Callout>
            )}
          </Panel>

          <Panel
            title="Collection sources"
            subtitle="Every source is reported explicitly. Pending telemetry is not zero, and skipped is not failure."
          >
            <SourceGrid sources={sources} />
          </Panel>

          <Panel title="Console">
            <div className="console" ref={consoleRef}>
              {lines.map((line, index) => (
                <div key={index} className={`console-line console-${line.level}`}>
                  <span className="console-time">{formatDateTime(line.atUtc).slice(11)}</span>
                  <span>{line.message}</span>
                </div>
              ))}
            </div>
          </Panel>

          {phase === 'completed' && runId && (
            <WorkflowNextStep
              title="Review the assessment results"
              detail="Open the dashboards, findings, evidence quality, and roadmap for this run."
              actionLabel="Visualize results"
              onAction={() => onViewResults(runId)}
            />
          )}
        </>
      )}
    </div>
  );
}

function PhaseTrack({ phase }: { phase: RunPhase }) {
  const current = phaseIndex(phase);
  const terminated = phase === 'failed' || phase === 'canceled';
  return (
    <div className="phase-track">
      {PHASE_ORDER.map((step, index) => {
        const done = index < current;
        const active = index === current && !terminated;
        const classes = ['phase-pill'];
        if (done) classes.push('done');
        if (active) classes.push('active');
        if (terminated && index === current - 1) classes.push('failed');
        return (
          <span key={step} className={classes.join(' ')}>
            {PHASE_LABELS[step]}
          </span>
        );
      })}
    </div>
  );
}

function SourceGrid({ sources }: { sources: CollectionSource[] }) {
  if (sources.length === 0) {
    return <span className="muted">Waiting for the first collector to report...</span>;
  }
  const domains: CollectionSource['domain'][] = ['azure', 'databricks'];
  return (
    <div className="stack-lg">
      {domains.map((domain) => {
        const rows = sources.filter((s) => s.domain === domain);
        if (rows.length === 0) return null;
        return (
          <div className="stack-sm" key={domain}>
            <span className="field-label">
              {domain === 'azure' ? 'Azure control plane and billing' : 'Azure Databricks workspaces'}
            </span>
            <div className="grid-2">
              {rows.map((source) => (
                <div className="panel" key={source.name}>
                  <div className="panel-body stack-sm">
                    <div className="row-between">
                      <strong>{source.name}</strong>
                      <StatusBadge status={source.status} title={STATUS_MEANING[source.status]} />
                    </div>
                    <span className="muted">
                      {formatNumber(source.itemCount)} item(s)
                      {source.completedAtUtc && source.startedAtUtc
                        ? ` \u00b7 ${elapsedBetween(source.startedAtUtc, source.completedAtUtc)}`
                        : ''}
                    </span>
                    {source.error && <span className="muted">{source.error}</span>}
                    {source.limitations.map((limitation, index) => (
                      <span className="muted" key={index}>
                        &bull; {limitation}
                      </span>
                    ))}
                    {source.workspaceKey && (
                      <Badge tone="neutral">workspace {source.workspaceKey}</Badge>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
