import { useMemo } from 'react';
import { Callout, KeyValue, Panel, Spinner } from '@/components';
import { useConfigStore } from '@/state';
import { formatDate } from '@/lib/format';
import { assignLegacyDeepDiveTargets, isResourceGroupSelected } from '@/lib/scopeSelection';
import type { CostBasis } from '@/types';
import { CapabilityOptionsEditor } from '@/components/CapabilityOptionsEditor';

export function ConfigurePage({ onValidate }: { onValidate: () => void }) {
  const {
    config,
    estate,
    loading,
    error,
    signingIn,
    bootstrap,
    signIn,
    patch,
    toggleSubscription,
    toggleResourceGroup,
    toggleWorkspace,
    setWarehouse,
  } = useConfigStore();

  const selectedSubs = useMemo(
    () => estate.filter((s) => config?.azure.subscriptions.includes(s.subscriptionId)),
    [estate, config],
  );

  if (loading || !config) {
    return (
      <div className="stack-lg">
        <Panel title="Discovering the estate">
          {error ? (
            <Callout tone="danger" title="Discovery failed">
              {error}
              <div>
                <button type="button" className="btn btn-sm" onClick={() => void bootstrap()}>
                  Retry configuration
                </button>
              </div>
            </Callout>
          ) : (
            <Spinner label="Enumerating subscriptions, resource groups, and Azure Databricks workspaces..." />
          )}
        </Panel>
      </div>
    );
  }

  const includedWorkspaces = config.databricks.workspaces.filter((w) => w.include);
  const warehouseCount = includedWorkspaces.filter((w) => w.sqlWarehouseId).length;
  const missingWarehouses = includedWorkspaces.filter((workspace) => !workspace.sqlWarehouseId);
  const hasLegacyTargets = config.databricks.deepDiveJobRunIds.length > 0 || config.databricks.deepDiveTableNames.length > 0;

  return (
    <div className="stack-lg">
      <Callout tone="info" title="Scope determines everything downstream">
        Only the resource groups you select here are collected. Azure Databricks managed resource
        groups are added automatically so VM, disk, and networking cost lands in the same scope as
        the workspace that caused it. Nothing outside this selection is read or reported.
        {' '}Selecting a subscription, or first loading a setup with one already selected, checks its discovered workspace resource groups and workspaces automatically.
        You can deselect any before validating. New assessments include editable IDs and a 30-day UTC analysis window.
      </Callout>

      {error ? (
        <Callout tone="warn" title="The live Azure scope could not be loaded">
          <div className="stack-sm">
            <span>
              {error} Your saved configuration is still available, but do not validate or start a
              new assessment until discovery succeeds.
            </span>
            <div>
              <button
                type="button"
                className="btn btn-primary btn-sm"
                disabled={loading || signingIn}
                onClick={() => void signIn()}
              >
                {signingIn ? 'Waiting for Azure sign-in…' : 'Sign in to Azure and retry'}
              </button>
            </div>
          </div>
        </Callout>
      ) : null}

      <Panel
        title="Engagement"
        subtitle="New assessments get generated IDs. Keep these defaults or edit them for your engagement."
      >
        <div className="grid-2">
          <label className="field">
            <span className="field-label">Customer ID</span>
            <input
              className="input"
              value={config.customerId}
              onChange={(e) => patch((d) => { d.customerId = e.target.value; })}
            />
            <span className="field-hint">Used in the run directory name and report header.</span>
          </label>
          <label className="field">
            <span className="field-label">Assessment ID</span>
            <input
              className="input"
              value={config.assessmentId}
              onChange={(e) => patch((d) => { d.assessmentId = e.target.value; })}
            />
            <span className="field-hint">Distinguishes repeat assessments for the same customer.</span>
          </label>
        </div>
      </Panel>

      <Panel
        title="Azure subscriptions"
        subtitle={error ? 'Live subscription list unavailable' : `${config.azure.subscriptions.length} of ${estate.length} selected`}
      >
        <div className="stack-sm">
          {estate.map((sub) => {
            const checked = config.azure.subscriptions.includes(sub.subscriptionId);
            const workspaceCount = sub.resourceGroups.reduce(
              (total, group) => total + group.workspaces.length,
              0,
            );
            return (
              <label key={sub.subscriptionId} className="radio">
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={() => toggleSubscription(sub.subscriptionId)}
                />
                <span className="checkbox-body">
                  <span className="checkbox-title">{sub.displayName}</span>
                  <span className="checkbox-note mono">
                    {sub.subscriptionId} &middot; {sub.state} &middot; {workspaceCount} workspace(s)
                  </span>
                </span>
              </label>
            );
          })}
        </div>
      </Panel>

      <Panel
        title="Resource groups"
        subtitle="Workspace groups are selected on initial setup load and when checking a subscription. Your later deselections are kept; associated managed groups are included during collection."
      >
        {selectedSubs.length === 0 ? (
          <span className="muted">Select at least one subscription to list its resource groups.</span>
        ) : (
          <div className="stack-lg">
            {selectedSubs.map((sub) => (
              <div className="stack-sm" key={sub.subscriptionId}>
                <span className="field-label">{sub.displayName}</span>
                {sub.resourceGroups.map((group) => {
                  const checked = isResourceGroupSelected(config, group);
                  return (
                    <label key={group.resourceGroupId} className="radio">
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => toggleResourceGroup(sub.subscriptionId, group.name)}
                      />
                      <span className="checkbox-body">
                        <span className="checkbox-title">
                          {group.name}
                          {group.isManagedResourceGroup ? ' \u00b7 managed' : ''}
                        </span>
                        <span className="checkbox-note">
                          {group.location} &middot; {group.workspaces.length} workspace(s)
                          {group.permissionIssue ? ` \u00b7 ${group.permissionIssue}` : ''}
                        </span>
                      </span>
                    </label>
                  );
                })}
              </div>
            ))}
          </div>
        )}
      </Panel>

      <Panel
        title="Azure Databricks workspaces"
        subtitle={`${includedWorkspaces.length} included \u00b7 ${warehouseCount} with a SQL Warehouse selected. Defaults prefer the smallest running warehouse, then the smallest stopped warehouse. Approval is still required in Validate.`}
      >
        {missingWarehouses.length > 0 && (
          <Callout tone="warn" title="Select warehouses for SQL-backed evidence">
            <div className="stack-sm">
              <span>Not configured: {missingWarehouses.map((workspace) => workspace.name).join(', ')}.</span>
              <span>
                Use each workspace&apos;s dropdown below, then explicitly approve SQL Warehouse use in Validate.
                Queries can start stopped warehouses and incur DBU charges. Warehouse CAN USE and system-table read access are required.
              </span>
              <span>
                You may leave None selected for API-only collection, but SQL-backed billing, timelines, and query history will not be checked.
                If no warehouse is listed, ask the workspace administrator for access to an appropriate warehouse.
              </span>
            </div>
          </Callout>
        )}
        {config.databricks.workspaces.length === 0 ? (
          <span className="muted">
            {config.azure.resourceGroups.length === 0
              ? 'Select resource groups to list their Azure Databricks workspaces.'
              : 'No workspace was discovered in the selected resource groups. Azure cost evidence will still be collected, but no workload-level findings can be produced.'}
          </span>
        ) : (
          <div className="stack">
            {config.databricks.workspaces.map((workspace) => {
              const discovered = estate
                .flatMap((s) => s.resourceGroups)
                .flatMap((g) => g.workspaces)
                .find((w) => w.workspaceId === workspace.workspaceId);
              const warehouseWasDiscovered = discovered?.sqlWarehouses.some(
                (warehouse) => warehouse.id === workspace.sqlWarehouseId,
              );
              return (
                <div className="stack-sm" key={workspace.workspaceId}>
                  <label className="radio">
                    <input
                      type="checkbox"
                      checked={workspace.include}
                      onChange={() => toggleWorkspace(workspace.workspaceId)}
                    />
                    <span className="checkbox-body">
                      <span className="checkbox-title">{workspace.name}</span>
                      <span className="checkbox-note mono">{workspace.workspaceUrl}</span>
                    </span>
                  </label>
                  {workspace.include && (
                    <label className="field" style={{ paddingLeft: 28 }}>
                      <span className="field-label">SQL Warehouse for system-table queries</span>
                      <select
                        className="select"
                        value={workspace.sqlWarehouseId ?? ''}
                        onChange={(e) =>
                          setWarehouse(workspace.workspaceId, e.target.value || undefined)
                        }
                      >
                        <option value="">None &mdash; skip warehouse-backed collection</option>
                        {workspace.sqlWarehouseId && !warehouseWasDiscovered ? (
                          <option value={workspace.sqlWarehouseId}>
                            Configured warehouse ({workspace.sqlWarehouseId})
                          </option>
                        ) : null}
                        {(discovered?.sqlWarehouses ?? []).map((wh) => (
                          <option key={wh.id} value={wh.id}>
                            {wh.name} ({wh.size}, {wh.state})
                          </option>
                        ))}
                      </select>
                      <span className="field-hint">
                        Selecting a warehouse does not start it. Queries can start it and incur DBU charges;
                        explicitly approve use in Validate. Your selection, including None, is preserved.
                      </span>
                      {discovered?.warehouseDiscoveryError && (
                        <span role="alert" className="field-hint">{discovered.warehouseDiscoveryError}</span>
                      )}
                    </label>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </Panel>

      <Panel
        title="Databricks account settings"
        subtitle="Optional account workspace and budget evidence. These settings do not grant account permissions."
      >
        <div className="grid-2">
          <label className="field">
            <span className="field-label">Account ID</span>
            <input className="input" value={config.databricks.accountId ?? ''}
              onChange={(e) => patch((d) => {
                d.databricks.accountId = e.target.value.trim();
                if (d.databricks.accountId && !d.databricks.accountHost) d.databricks.accountHost = 'accounts.azuredatabricks.net';
                if (!d.databricks.accountId) d.databricks.accountHost = '';
              })} />
            <span className="field-hint">Use the Databricks account UUID, not the Azure tenant or workspace ID. Clear it to omit account-level coverage.</span>
          </label>
          <label className="field">
            <span className="field-label">Account host</span>
            <input className="input" value={config.databricks.accountHost ?? ''}
              placeholder="accounts.azuredatabricks.net"
              onChange={(e) => patch((d) => { d.databricks.accountHost = e.target.value.trim(); })} />
            <span className="field-hint">Hostname only, without https:// or a path. Readiness checks whether your identity can read this account.</span>
          </label>
        </div>
      </Panel>

      <Panel title="Analysis window and cost basis" subtitle="New assessments default to the previous 30 complete UTC days. Change either date if needed.">
        <div className="grid-3">
          <label className="field">
            <span className="field-label">Start (UTC)</span>
            <input
              className="input"
              type="date"
              value={config.analysis.startUtc.slice(0, 10)}
              onChange={(e) =>
                patch((d) => { d.analysis.startUtc = `${e.target.value}T00:00:00Z`; })
              }
            />
          </label>
          <label className="field">
            <span className="field-label">End (UTC)</span>
            <input
              className="input"
              type="date"
              value={config.analysis.endUtc.slice(0, 10)}
              onChange={(e) => patch((d) => { d.analysis.endUtc = `${e.target.value}T00:00:00Z`; })}
            />
          </label>
          <label className="field">
            <span className="field-label">Time zone</span>
            <input
              className="input"
              value={config.analysis.timeZone}
              onChange={(e) => patch((d) => { d.analysis.timeZone = e.target.value; })}
            />
          </label>
        </div>
        <div className="grid-3" style={{ marginTop: 'var(--space-4)' }}>
          <div className="field">
            <span className="field-label">Cost basis</span>
            <div className="row-wrap">
              {(['ActualCost', 'AmortizedCost'] as CostBasis[]).map((basis) => (
                <button
                  key={basis}
                  type="button"
                  className={config.azure.costBasis.includes(basis) ? 'chip active' : 'chip'}
                  onClick={() =>
                    patch((d) => {
                      const set = new Set(d.azure.costBasis);
                      if (set.has(basis) && set.size > 1) set.delete(basis);
                      else set.add(basis);
                      d.azure.costBasis = [...set];
                    })
                  }
                >
                  {basis}
                </button>
              ))}
            </div>
            <span className="field-hint">
              Both bases are collected when selected; the report always names the basis behind every
              figure so reservations and savings plans are never double-counted.
            </span>
          </div>
          <label className="field">
            <span className="field-label">Currency</span>
            <input
              className="input"
              value={config.azure.currency}
              onChange={(e) => patch((d) => { d.azure.currency = e.target.value; })}
            />
          </label>
          <div className="field">
            <span className="field-label">Window summary</span>
            <span className="muted">
              {formatDate(config.analysis.startUtc)} &rarr; {formatDate(config.analysis.endUtc)}
            </span>
          </div>
        </div>
      </Panel>

      <Panel
        title="Deep-dive targets"
        subtitle="Optional and workspace-specific. Targets are never sent to other workspaces. Blank lists skip the optional deep dive."
      >
        <div className="stack-lg">
          {hasLegacyTargets && (
            <Callout tone="warn" title="Legacy deep-dive targets need a workspace">
              <div className="stack-sm">
                <span>The loaded configuration has unassigned global targets. Choose their workspace instead of querying every workspace.</span>
                <span>Run IDs: {config.databricks.deepDiveJobRunIds.join(', ') || 'None'}</span>
                <span>Tables: {config.databricks.deepDiveTableNames.join(', ') || 'None'}</span>
                <label className="field">
                  <span className="field-label">Workspace for legacy targets</span>
                  <select className="select" value="" onChange={(e) => {
                    if (e.target.value) patch((draft) => assignLegacyDeepDiveTargets(draft, e.target.value));
                  }}>
                    <option value="">Select the owning workspace</option>
                    {includedWorkspaces.map((workspace) => (
                      <option key={workspace.workspaceId} value={workspace.workspaceId}>{workspace.name}</option>
                    ))}
                  </select>
                </label>
                <button type="button" className="btn btn-sm" onClick={() => patch((draft) => {
                  draft.databricks.deepDiveJobRunIds = [];
                  draft.databricks.deepDiveTableNames = [];
                })}>Clear unassigned targets</button>
              </div>
            </Callout>
          )}
          {includedWorkspaces.length === 0 && <span className="muted">Include a workspace to configure optional deep-dive targets.</span>}
          {includedWorkspaces.map((workspace) => (
            <div className="grid-2" key={workspace.workspaceId}>
              <label className="field">
                <span className="field-label">Job run IDs - {workspace.name}</span>
                <textarea className="textarea" rows={3} value={(workspace.deepDiveJobRunIds ?? []).join('\n')}
                  onChange={(e) => patch((draft) => {
                    const target = draft.databricks.workspaces.find((item) => item.workspaceId === workspace.workspaceId)!;
                    target.deepDiveJobRunIds = e.target.value.split('\n').map((value) => value.trim()).filter(Boolean);
                  })}
                />
                <span className="field-hint">
                  One numeric run ID per line, from this workspace only. Collects job metadata and cluster events.
                  Detailed Spark metrics require separate Spark UI or event-log review; there is no event-log importer.
                </span>
              </label>
              <label className="field">
                <span className="field-label">Table names - {workspace.name}</span>
                <textarea className="textarea" rows={3} value={(workspace.deepDiveTableNames ?? []).join('\n')}
                  onChange={(e) => patch((draft) => {
                    const target = draft.databricks.workspaces.find((item) => item.workspaceId === workspace.workspaceId)!;
                    target.deepDiveTableNames = e.target.value.split('\n').map((value) => value.trim()).filter(Boolean);
                  })}
                />
                <span className="field-hint">One catalog.schema.table per line, accessible from this workspace&apos;s selected warehouse.</span>
              </label>
            </div>
          ))}
        </div>
      </Panel>

      <Panel
        title="Redaction and output"
        subtitle="Relaxing redaction increases the sensitivity of the artifacts this run writes."
      >
        <div className="stack-sm">
          <RedactionToggle
            label="Include query text"
            hint="Query text can contain literals and business data. Off by default."
            checked={config.databricks.includeQueryText}
            onChange={(value) =>
              patch((d) => {
                d.databricks.includeQueryText = value;
                d.redaction.omitQueryText = !value;
              })
            }
          />
          <RedactionToggle
            label="Include identities"
            hint="When off, user and service principal identifiers are salted-hashed."
            checked={config.databricks.includeIdentities}
            onChange={(value) =>
              patch((d) => {
                d.databricks.includeIdentities = value;
                d.redaction.hashIdentities = !value;
              })
            }
          />
          <RedactionToggle
            label="Include notebook paths"
            hint="Notebook paths often encode project and team names."
            checked={config.databricks.includeNotebookPaths}
            onChange={(value) =>
              patch((d) => {
                d.databricks.includeNotebookPaths = value;
                d.redaction.hashNotebookPaths = !value;
              })
            }
          />
        </div>
        <div className="grid-2" style={{ marginTop: 'var(--space-4)' }}>
          <label className="field">
            <span className="field-label">Output root</span>
            <input
              className="input mono"
              value={config.outputs.root}
              onChange={(e) => patch((d) => { d.outputs.root = e.target.value; })}
            />
          </label>
          <div className="field">
            <span className="field-label">Formats</span>
            <div className="row-wrap">
              {(
                [
                  ['writeMarkdown', 'Markdown report'],
                  ['writeCsv', 'CSV extracts'],
                  ['writeJson', 'JSON artifacts'],
                  ['retainRaw', 'Retain raw responses'],
                ] as const
              ).map(([key, label]) => (
                <button
                  key={key}
                  type="button"
                  className={config.outputs[key] ? 'chip active' : 'chip'}
                  onClick={() => patch((d) => { d.outputs[key] = !d.outputs[key]; })}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
        </div>
      </Panel>

      <CapabilityOptionsEditor value={config.capabilities} onChange={options => patch(draft => { draft.capabilities = options; })} />
      <Panel
        title="Effective scope"
        footer={
          <div className="row-between">
            <span className="muted">
              Validation first checks required fields locally, then reads source evidence to check access and can take several minutes.
              It does not run analysis or create the final report.
            </span>
            <button type="button" className="btn btn-primary" onClick={onValidate}>
              Validate configuration
            </button>
          </div>
        }
      >
        <KeyValue
          items={[
            { label: 'Tenant', value: <span className="mono">{config.azure.tenantId}</span> },
            { label: 'Subscriptions', value: config.azure.subscriptions.length || 'None selected' },
            {
              label: 'Resource groups',
              value: config.azure.resourceGroups.length
                ? config.azure.resourceGroups.join(', ')
                : 'None selected',
            },
            {
              label: 'Workspaces',
              value: includedWorkspaces.length
                ? includedWorkspaces.map((w) => w.name).join(', ')
                : 'None included',
            },
            {
              label: 'Cost scope',
              value: <span className="mono">{config.azure.costScope}</span>,
            },
            { label: 'Cost basis', value: config.azure.costBasis.join(' + ') },
          ]}
        />
      </Panel>
    </div>
  );
}

function RedactionToggle({
  label,
  hint,
  checked,
  onChange,
}: {
  label: string;
  hint: string;
  checked: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <label className="radio">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <span className="checkbox-body">
        <span className="checkbox-title">{label}</span>
        <span className="checkbox-note">{hint}</span>
      </span>
    </label>
  );
}
