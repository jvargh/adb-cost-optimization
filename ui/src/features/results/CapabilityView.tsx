import { useEffect, useState } from 'react';
import { LineChart, Line, ResponsiveContainer, XAxis, YAxis, Tooltip, Legend } from 'recharts';
import { Callout, DataTable, Drawer, Panel, Spinner, type Column } from '@/components';
import { getBackend } from '@/api';
import { useResultsStore } from '@/state';
import { formatNumber } from '@/lib/format';
import type { CapabilityModule, CapabilityPage, CapabilityRow, JsonValue } from '@/types/capabilities';

const FIELDS: Record<CapabilityModule, string[]> = {
  utilization: ['cpuPercent', 'memoryPercent', 'peakCpuPercent', 'idlePercent', 'samples'],
  sizing: ['nodeType', 'minWorkers', 'maxWorkers', 'singleNode'],
  network: ['receivedMiB', 'sentMiB', 'cpuWaitPercent', 'samples'],
  jobs: ['runs', 'failedRuns', 'failureAlerts', 'tasks', 'retryPolicy'],
  queries: ['warehouseId', 'start', 'durationSeconds', 'queueSeconds', 'user'],
  posture: ['category', 'observed', 'severity'],
  assets: ['assetType'],
  commitments: ['region', 'sku', 'currency', 'hour', 'eligibleNodes', 'coveredNodes'],
};
const label = (s: string) => s.replace(/([A-Z])/g, ' $1').replace(/^./, c => c.toUpperCase());
const display = (v: JsonValue | undefined): string => v === null || v === undefined ? 'Not available' : typeof v === 'number' ? formatNumber(v, 2) : typeof v === 'object' ? JSON.stringify(v) : String(v);

export function CapabilityView({ module }: { module: CapabilityModule }) {
  const { runId, results, filters, selectFinding } = useResultsStore();
  const [page, setPage] = useState<CapabilityPage | null>(null);
  const [search, setSearch] = useState('');
  const [sort, setSort] = useState('name');
  const [groupBy, setGroupBy] = useState('');
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<CapabilityRow | null>(null);
  const [node, setNode] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [retry, setRetry] = useState(0);
  const [quantity, setQuantity] = useState(1);
  const [scenario, setScenario] = useState<JsonValue | null>(null);
  const [scenarioBusy, setScenarioBusy] = useState(false);
  const scopeKey = JSON.stringify([filters.workspaces, filters.subscriptionIds, filters.resourceGroups]);
  useEffect(() => { setOffset(0); setSelected(null); setScenario(null); }, [module, runId, search, sort, scopeKey, groupBy]);
  useEffect(() => {
    let current = true;
    if (!runId || !results?.capabilities) { setPage(null); return; }
    setLoading(true); setError(null);
    const workspaceId = results.manifest.scope.workspaces.filter(w => !filters.workspaces.length || filters.workspaces.includes(w.workspaceId) || filters.workspaces.includes(w.name)).map(w => w.workspaceId);
    getBackend().capabilityOperation<CapabilityPage>(runId, 'dataset', { dataset: module, search, sort, offset, limit: 50, groupBy: groupBy || undefined,
      workspaceId: filters.workspaces.length ? workspaceId : [], subscriptionId: filters.subscriptionIds, resourceGroup: filters.resourceGroups,
    }).then(data => { if (current) setPage(data); }).catch(err => { if (current) setError(err instanceof Error ? err.message : String(err)); }).finally(() => { if (current) setLoading(false); });
    return () => { current = false; };
  }, [module, runId, results, search, sort, offset, scopeKey, retry, groupBy]);
  if (!results?.capabilities) return <Callout tone="info" title="Not collected in this version">Use Evidence quality to re-analyze saved evidence into a new child snapshot. Opening this view does not query cloud services.</Callout>;
  const fields = module === 'queries' && groupBy ? ['queryCount', 'failedQueries', 'p95DurationSeconds', 'p95QueueSeconds'] : FIELDS[module];
  const columns: Column<CapabilityRow>[] = [
    { key: 'name', header: 'Resource', render: r => <button className="btn btn-ghost btn-sm" onClick={() => setSelected(r)}>{r.name}</button> },
    { key: 'workspace', header: 'Workspace', render: r => <span>{r.workspaceName}<br /><span className="muted mono">{r.workspaceId}</span></span> },
    ...fields.map(field => ({ key: field, header: label(field), render: (r: CapabilityRow) => display(r[field]) })),
    { key: 'status', header: 'Evidence / outcome', render: r => r.status },
  ];
  const related = selected ? results.candidates.findings.filter(f => f.scope.workspaceId === selected.workspaceId && f.scope.workload === selected.name) : [];
  const series = selected?.detail?.series;
  const chartRows = Array.isArray(series) ? series.filter((v): v is { [key: string]: JsonValue } => v !== null && typeof v === 'object' && !Array.isArray(v)) : [];
  const nodeKey = (row: { [key: string]: JsonValue }) => `${row.role}: ${row.instanceId ?? 'instance ID unavailable'}`;
  const nodes = [...new Set(chartRows.map(nodeKey))];
  const chartNode = nodes.includes(node) ? node : nodes[0];
  return <div className="stack">
    <Callout tone="info" title={`${label(module)}: saved evidence`}>
      {results.capabilities.coverage[module].status}. Rule {results.capabilities.ruleVersion}. Counts describe saved rows, not full-window coverage.
      {module === 'network' && ' Network MiB is node traffic, not Azure billed egress.'}
      {module === 'posture' && ' Two supported Azure configuration checks; no compliance score or certification.'}
      {module === 'commitments' && ' Hourly demand, existing coverage, eligible SKU/region and both prices are required. No purchase is made.'}
    </Callout>
    {module === 'queries' && <label className="field"><span className="field-label">Query view</span><select className="select" value={groupBy} onChange={e => { setGroupBy(e.target.value); setSort('name'); }}><option value="">Individual queries</option><option value="warehouseId">Warehouse summaries</option><option value="user">User summaries</option></select></label>}
    <div className="grid-2">
      <label className="field"><span className="field-label">Search {module}</span><input className="input" value={search} onChange={e => setSearch(e.target.value)} /></label>
      <label className="field"><span className="field-label">Sort saved dataset</span><select className="select" value={sort} onChange={e => setSort(e.target.value)}>{['name', 'status', ...fields].map(f => <option key={f} value={f}>{label(f)}</option>)}</select></label>
    </div>
    {error && <Callout tone="danger" title="Evidence request failed">{error}<button className="btn btn-sm" onClick={() => setRetry(r => r + 1)}>Retry evidence read</button></Callout>}
    {loading ? <Spinner label="Reading saved dataset..." /> : page && <Panel title={`${page.total} matching saved rows`}>
      <DataTable columns={columns} rows={page.rows} rowKey={r => r.key} emptyTitle={search ? 'No rows match these filters' : 'Evidence unavailable or no collected rows'} emptyDetail="Inspect Evidence quality for selection, permissions and collection limitations. Missing evidence is not zero utilization or a passing control." />
      <div className="row-between"><button className="btn btn-sm" disabled={offset === 0} onClick={() => setOffset(n => Math.max(0, n - 50))}>Previous page</button><span>{page.total ? offset + 1 : 0}-{Math.min(offset + 50, page.total)} of {page.total}</span><button className="btn btn-sm" disabled={offset + 50 >= page.total} onClick={() => setOffset(n => n + 50)}>Next page</button></div>
    </Panel>}
    {module === 'commitments' && <Panel title="Saved-input commitment scenario" subtitle="Uses all saved rows matching workspace/subscription/resource-group filters, not search or pagination. Requires one SKU/region/currency and unique hourly demand. Results cover sampled hours only.">
      <label className="field"><span className="field-label">Proposed committed nodes</span><input className="input" type="number" min="1" value={quantity} onChange={e => setQuantity(e.target.valueAsNumber)} /></label>
      <button className="btn" disabled={scenarioBusy || !runId} onClick={async () => {
        setScenarioBusy(true); setError(null); setScenario(null);
        try { setScenario(await getBackend().capabilityOperation<JsonValue>(runId, 'scenario', { quantity,
          workspaceId: filters.workspaces.length ? results.manifest.scope.workspaces.filter(w => filters.workspaces.includes(w.workspaceId) || filters.workspaces.includes(w.name)).map(w => w.workspaceId) : [],
          subscriptionId: filters.subscriptionIds, resourceGroup: filters.resourceGroups,
        })); }
        catch (err) { setError(err instanceof Error ? err.message : String(err)); }
        finally { setScenarioBusy(false); }
      }}>{scenarioBusy ? 'Calculating...' : 'Calculate scenario'}</button>
      {scenario && <pre className="markdown-preview">{JSON.stringify(scenario, null, 2)}</pre>}
    </Panel>}
    {selected && <Drawer open title={selected.name} subtitle={`${selected.workspaceName} / ${selected.workspaceId}`} onClose={() => setSelected(null)}>
      <div className="stack">
        <p>Source: {display(selected.evidence)}. All actions are local evidence review.</p>
        {chartRows.length > 0 && module === 'utilization' && <><label className="field"><span className="field-label">Node sample series</span><select className="select" value={chartNode} onChange={e => setNode(e.target.value)}>{nodes.map(id => <option key={id}>{id}</option>)}</select></label><div style={{ height: 260 }} role="img" aria-label="Observed CPU and memory sample series; gaps are unavailable values">
          <ResponsiveContainer><LineChart data={chartRows.filter(row => nodeKey(row) === chartNode)}><XAxis dataKey="start" hide /><YAxis unit="%" /><Tooltip /><Legend />
            <Line dataKey="cpuPercent" name="CPU %" stroke="var(--cp-chart-1)" dot={false} connectNulls={false} isAnimationActive={false} />
            <Line dataKey="memoryPercent" name="Memory %" stroke="var(--cp-chart-2)" dot={false} connectNulls={false} isAnimationActive={false} />
          </LineChart></ResponsiveContainer>
        </div></>}
        {related.map(f => <button className="btn" key={f.findingId ?? f.detectorId} onClick={() => { setSelected(null); selectFinding(f); }}>Review: {f.title}</button>)}
        <pre className="markdown-preview" tabIndex={0} aria-label="Metric definitions and evidence details">{JSON.stringify(selected, null, 2)}</pre>
      </div>
    </Drawer>}
  </div>;
}
