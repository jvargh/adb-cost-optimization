import { Badge, Callout, EmptyState, Panel } from '@/components';
import { useConfigStore } from '@/state';
import type { ValidationCheck } from '@/types';
import { ValidationProgressPanel } from './ValidationProgressPanel';
import { SourceDetails, ValidationIssueList } from './ValidationIssues';
import { usePermissionStore } from '@/state/permissionStore';
import { ValidationActions } from './ValidationActions';

const GROUP_LABELS: Record<ValidationCheck['group'], string> = {
  environment: 'Environment',
  scope: 'Scope',
  permissions: 'Permissions and access',
  safety: 'Safety and approvals',
};

const GROUP_ORDER: ValidationCheck['group'][] = ['scope', 'permissions', 'environment', 'safety'];

export function ValidatePage({ onRun, onConfigure }: { onRun: () => void; onConfigure?: () => void }) {
  const { config, validation, validating, validationError, validationProgress } =
    useConfigStore();
  const permissionBusy = usePermissionStore((state) => state.busy);

  if (!config) {
    return <EmptyState title="Configure the assessment first" detail="Scope selection is required before pre-flight validation can run." />;
  }

  if (validating) {
    return <ValidationProgressPanel />;
  }
  if (permissionBusy) {
    return <Callout tone="info" title="Permission setup is separate from validation">Resolve the setup status below before starting more live work. A connection error does not mean setup is still running.</Callout>;
  }

  if (!validation) {
    return (
      <div className="stack-lg">
      <ApprovalsPanel />
      <Panel title="Pre-flight validation">
        {validationError ? (
          <div className="stack">
            <Callout tone="danger" title="Validation did not finish">{validationError}</Callout>
            <ValidationActions />
          </div>
        ) : (
          <div className="stack">
            <p>Validation has not started. Run it explicitly to check the current configuration and source access. Read-only checks can query Azure and Databricks.</p>
            <ValidationActions />
          </div>
        )}
      </Panel>
      </div>
    );
  }

  const blockers = validation.checks.filter((c) => c.status === 'fail' && c.severity === 'blocker');
  const warnings = validation.checks.filter(
    (c) => c.status === 'warn' || (c.status === 'fail' && c.severity !== 'blocker'),
  );

  return (
    <div className="stack-lg">
      <ValidationSummary blockers={blockers} warnings={warnings} />
      {blockers.length > 0 && onConfigure && (
        <div>
          <button type="button" className="btn" onClick={onConfigure}>Back to Configure</button>
        </div>
      )}
      {validationProgress && <ValidationProgressPanel />}

      <div className="grid-3">
        <SummaryTile label="Blockers" value={validation.blockerCount} tone={validation.blockerCount ? 'danger' : 'ok'} />
        <SummaryTile label="Warnings" value={validation.warningCount} tone={validation.warningCount ? 'warn' : 'ok'} />
        <SummaryTile
          label="Requirements and reported issues"
          value={validation.checks.length}
          tone="neutral"
        />
      </div>

      <ApprovalsPanel />

      {GROUP_ORDER.map((group) => {
        const checks = validation.checks.filter((c) => c.group === group);
        if (checks.length === 0) return null;
        return (
          <Panel key={group} title={GROUP_LABELS[group]}>
            <div className="stack-sm">
              {checks.map((check) => (
                <CheckRow key={check.id} check={check} />
              ))}
            </div>
          </Panel>
        );
      })}

      <Panel footer={<ValidationActions onRun={onRun} />}>
        <span className="muted">
          Validation is itself read-only. Configuration blockers are reported before any source checks start.
          Re-run it after changing scope or approvals.
        </span>
      </Panel>
    </div>
  );
}

function ApprovalsPanel() {
  const { approvals, setApproval } = useConfigStore();
  return (
    <Panel title="Approvals" subtitle="Warehouse selection never implies approval. Permission changes need a separate exact-grant confirmation.">
      <div className="stack-sm">
        <label className="radio">
          <input type="checkbox" checked={approvals.approveSqlWarehouseAutoStart}
            onChange={(event) => setApproval('approveSqlWarehouseAutoStart', event.target.checked)} />
          <span className="checkbox-body">
            <span className="checkbox-title">Approve SQL Warehouse auto-start (<span className="mono">-ApproveSqlWarehouseAutoStart</span>)</span>
            <span className="checkbox-note">Read-only queries and permission-setup queries can start stopped warehouses and incur DBU charges. This does not approve GRANT statements.</span>
          </span>
        </label>
        <label className="radio">
          <input type="checkbox" checked={approvals.continueOnCollectorError}
            onChange={(event) => setApproval('continueOnCollectorError', event.target.checked)} />
          <span className="checkbox-body">
            <span className="checkbox-title">Continue on collector error (<span className="mono">-ContinueOnCollectorError</span>)</span>
            <span className="checkbox-note">Recommended for assessment collection. Permission setup always stops at the first failure and reports any partial grants.</span>
          </span>
        </label>
      </div>
    </Panel>
  );
}

export function ValidationSummary({
  blockers,
  warnings,
}: {
  blockers: ValidationCheck[];
  warnings: ValidationCheck[];
}) {
  if (blockers.length > 0) {
    return (
      <Callout
        tone="danger"
        title={`${blockers.length} ${blockers.length === 1 ? 'item must' : 'items must'} be fixed before the run`}
      >
        <p>Fix the following {blockers.length === 1 ? 'item' : 'items'}, then run validation again.</p>
        <ValidationIssueList checks={blockers} />
      </Callout>
    );
  }

  if (warnings.length > 0) {
    return (
      <Callout
        tone="warn"
        title={`Ready to run — ${warnings.length} ${warnings.length === 1 ? 'warning' : 'warnings'}`}
      >
        <p>You can start the run. Review these warnings first:</p>
        <ValidationIssueList checks={warnings} />
      </Callout>
    );
  }

  return (
    <Callout tone="ok" title="Ready to run">
      All required checks passed. The assessment only reads data and does not change resources.
    </Callout>
  );
}

function SummaryTile({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: 'ok' | 'warn' | 'danger' | 'neutral';
}) {
  return (
    <div className={`kpi kpi-accent-${tone}`}>
      <span className="kpi-label">{label}</span>
      <span className="kpi-value">{value}</span>
    </div>
  );
}

const STATUS_TONE = {
  pass: 'ok',
  warn: 'warn',
  fail: 'danger',
  skipped: 'neutral',
  running: 'pending',
} as const;

function CheckRow({ check }: { check: ValidationCheck }) {
  return (
    <div className="row" style={{ alignItems: 'flex-start', gap: 'var(--space-3)' }}>
      <Badge tone={STATUS_TONE[check.status]}>{check.status}</Badge>
      <div className="stack-sm" style={{ minWidth: 0, flex: 1 }}>
        <span>
          {check.title}{' '}
          {check.severity === 'blocker' && check.status === 'fail' && (
            <span className="muted">(blocking)</span>
          )}
        </span>
        <span className="muted">{check.detail}</span>
        {check.remediation && (
          <span className="muted">
            <strong>Fix:</strong> {check.remediation}
          </span>
        )}
        <SourceDetails check={check} />
      </div>
    </div>
  );
}
