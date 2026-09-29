import { useEffect, useState } from 'react';
import { Callout, Panel, Spinner } from '@/components';
import { useConfigStore, useRunStore } from '@/state';
import { usePermissionStore } from '@/state/permissionStore';
import { ManualPermissionGuide } from './ManualPermissionGuide';
import { ValidationActions } from './ValidationActions';

export function PermissionSetupPanel({ onRun }: { onRun?: () => void }) {
  const { config, approvals, validating, loading, signingIn, resetValidation } = useConfigStore();
  const phase = useRunStore((state) => state.phase);
  const { job, busy, requesting, error, preview, apply, refresh, clear } = usePermissionStore();
  const [workspaceId, setWorkspaceId] = useState('');
  const [confirmed, setConfirmed] = useState(false);
  useEffect(() => { void usePermissionStore.getState().refresh(); }, []);
  if (!config) return null;
  const workspaces = config.databricks.workspaces.filter((workspace) => workspace.include && workspace.sqlWarehouseId);
  const workspace = workspaces.find((item) => item.workspaceId === workspaceId) ?? workspaces[0];
  const active = validating || loading || signingIn || !['idle', 'completed', 'failed', 'canceled'].includes(phase);
  const approved = approvals.approveSqlWarehouseAutoStart;
  const matches = job && workspace && job.workspaceId === workspace.workspaceId
    && job.warehouseId === workspace.sqlWarehouseId
    && job.workspaceUrl === workspace.workspaceUrl.replace(/^https:\/\//, '').replace(/\/$/, '').toLowerCase();

  return (
    <Panel title="Pipeline timeline permission setup" subtitle="Read access is checked first. Permission changes are separate and confirmed.">
      <div className="stack">
        <Callout tone="info" title="Check access before changing permissions">
          The first action verifies your signed-in identity and runs a read-only SELECT on
          system.lakeflow.pipeline_update_timeline. If it succeeds, no grants are needed or offered.
          Only a confirmed permission denial produces a grant preview. Missing tables, timeouts,
          and other errors are not treated as missing privileges.
        </Callout>
        <label className="field">
          <span className="field-label">Workspace for permission setup</span>
          <select className="select" disabled={busy || active} value={workspace?.workspaceId ?? ''}
            onChange={(event) => { setWorkspaceId(event.target.value); setConfirmed(false); }}>
            {!workspaces.length && <option value="">Select a SQL Warehouse in Configure first</option>}
            {workspaces.map((item) => <option key={item.workspaceId} value={item.workspaceId}>{item.name}</option>)}
          </select>
        </label>
        {workspace && <span className="break-anywhere">Workspace: {workspace.workspaceUrl} | Warehouse: {workspace.sqlWarehouseId}</span>}
        {!approved && <p>Approve SQL Warehouse use in the Approvals panel first. Identity and access checks can start a stopped warehouse and incur DBU charges.</p>}
        <div className="row">
          <button type="button" className="btn" disabled={!workspace || !approved || active || busy || requesting}
            onClick={() => {
              if (!workspace) return;
              setConfirmed(false);
              void preview(workspace, approved);
            }}>Check access and preview grants</button>
          {(job || busy) && <button type="button" className="btn btn-ghost" disabled={requesting} onClick={() => void refresh()}>Check setup status</button>}
        </div>
        {requesting && <Spinner label={job?.status === 'applying' ? 'Applying only the confirmed grants and verifying SELECT access...' : 'Checking identity, read access, and setup status...'} />}
        {error && <Callout tone="danger" title="Permission setup did not complete">{error}</Callout>}
        {job?.status === 'failed' && /PERMISSION_DENIED|INSUFFICIENT_PERMISSIONS|does not have MANAGE/i.test(job.error ?? '') && (
          <Callout tone="warn" title="An authorized Unity Catalog administrator is required">
            This identity cannot complete the requested operation with its current privileges.
            Ask an administrator with grant authority on the listed securables to apply the exact grants below.
            A username containing &quot;admin&quot; or Azure subscription access does not confer Unity Catalog grant authority.
            Retrying with the same privileges will not resolve a denied grant.
          </Callout>
        )}
        {error && !requesting && busy && (
          <div className="stack-sm">
            <span>Status checking has stopped; no request is currently running in this page. The server outcome is unresolved, so new live work is paused. Check setup status, or inspect the setup audit and actual Databricks permissions before dismissing. Dismissing does not cancel server work or revoke permissions.</span>
            <button type="button" className="btn" onClick={() => clear(true)}>I checked actual permissions; dismiss unknown status</button>
          </div>
        )}
        {job?.principal && (
          <div className="stack-sm">
            <strong className="break-anywhere">Verified assessment identity: {job.principal}</strong>
            <span className="break-anywhere">Preview target: {job.workspaceUrl} | Warehouse: {job.warehouseId}</span>
            {job.grants.map((grant) => (
              <div key={grant.statement}>
                <pre className="break-anywhere" style={{ whiteSpace: 'pre-wrap' }}>{grant.statement};</pre>
                <span>Status: {grant.status === 'submitted' ? 'submitted; outcome not yet verified' : grant.status === 'failed' ? 'failed; Databricks rejected this grant' : grant.status === 'not_attempted' ? 'not attempted' : grant.status}</span>
              </div>
            ))}
          </div>
        )}
        {job?.status === 'awaiting_confirmation' && (
          <>
            <Callout tone="warn" title="Pipeline timeline read access is missing">
              The read-only check was denied. These three grants change Unity Catalog permissions,
              can affect other workspaces sharing the metastore, and require existing grant authority.
              The tool does not acquire administrator credentials or elevate roles.
              {job.accessCheckError && <details><summary>Access check details</summary><span className="break-anywhere">{job.accessCheckError}</span></details>}
            </Callout>
            <span>Preview expires: {job.expiresAtUtc}. Identity is verified again before any grant.</span>
            {!matches && <Callout tone="warn" title="Selection changed">Verify a new preview for the current workspace and warehouse.</Callout>}
            <label className="radio">
              <input type="checkbox" checked={confirmed} disabled={busy || !matches || !approved || active}
                onChange={(event) => setConfirmed(event.target.checked)} />
              <span>I confirm these exact three grants for {job.principal} on the previewed target.</span>
            </label>
            <div className="row">
              <button type="button" className="btn btn-primary" disabled={!confirmed || !matches || !approved || active || busy || requesting}
                onClick={() => { setConfirmed(false); resetValidation(); void apply(approved); }}>Apply these three grants</button>
              <button type="button" className="btn" disabled={busy} onClick={() => { setConfirmed(false); clear(); }}>Cancel without granting</button>
            </div>
          </>
        )}
        {job?.status === 'completed' && job.accessVerified && !matches && (
          <Callout tone="info" title="Access result belongs to the previous selection">
            Check access for the currently selected workspace and warehouse. The saved result below does not verify this new target.
          </Callout>
        )}
        {job?.status === 'completed' && job.accessVerified && matches && (
          <Callout tone="ok" title={job.grants.length === 0 ? 'Already accessible - no grants needed' : 'Pipeline timeline SELECT access verified'}>
            {job.grants.length === 0
              ? 'The read-only SELECT succeeded for the displayed identity and target. No GRANT statements were submitted, and existing validation results are unchanged. An empty result is still successful access.'
              : 'The confirmed grants completed and a read-only SELECT succeeded. Run validation explicitly again.'}
            {' '}This does not certify other sources or resolve detailed Spark-metrics coverage.
          </Callout>
        )}
        {job?.status === 'completed' && job.accessVerified && matches && (
          <section className="stack-sm" aria-label="Next steps after permission setup">
            <Callout tone="info" title="Next: full validation, then assessment">
              Green here confirms pipeline-table access only, not full readiness for all workspaces.
              {validating
                ? ' Full validation is already running. Wait for it to finish; progress is above this panel.'
                : ' Run full validation if it has not completed, or re-run it after changing permissions.'}
              {' '}When validation allows it, choose Continue to run, then Start read-only assessment on step 3.
              Continuing does not start collection automatically. No new assessment is needed.
            </Callout>
            <ValidationActions onRun={onRun} />
          </section>
        )}
        <ManualPermissionGuide
          key={`${workspace?.workspaceId}:${workspace?.sqlWarehouseId}:${workspace?.workspaceUrl}:${job?.setupId}:${job?.principal}:${config.databricks.accountId}:${config.databricks.accountHost}`}
          job={matches ? job : null} account={config.databricks} blocked={busy || active || requesting} />
        <span className="muted">Setup results are recorded under the local output folder&apos;s .ui-server/permission-setup directory. Partial grants are not automatically rolled back or retried.</span>
      </div>
    </Panel>
  );
}
