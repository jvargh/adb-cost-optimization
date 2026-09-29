import { useMemo } from 'react';
import { Badge, Callout, DataTable, KpiCard, Panel, type Column } from '@/components';
import { DistributionChart } from '@/components/charts';
import { formatMoney, formatNumber, formatPercent } from '@/lib/format';
import { useResultsStore } from '@/state';
import type { AssessmentResults, ComputeRecord, WarehouseRecord, WorkloadRecord } from '@/types';

export function ComputeTab({ results }: { results: AssessmentResults }) {
  const filters = useResultsStore((s) => s.filters);

  const inScope = <T extends { workspaceName: string }>(rows: T[]) =>
    filters.workspaces.length === 0
      ? rows
      : rows.filter((r) => filters.workspaces.includes(r.workspaceName));

  const compute = useMemo(() => inScope(results.compute), [results.compute, filters.workspaces]);
  const warehouses = useMemo(
    () => inScope(results.warehouses),
    [results.warehouses, filters.workspaces],
  );
  const workloads = useMemo(
    () =>
      inScope(results.workloads).filter(
        (w) => filters.workloads.length === 0 || filters.workloads.includes(w.jobName),
      ),
    [results.workloads, filters.workspaces, filters.workloads],
  );

  const measuredIdle = compute.filter((c) => c.idlePercent !== null);
  const avgIdle = measuredIdle.length
    ? measuredIdle.reduce((sum, c) => sum + (c.idlePercent ?? 0), 0) / measuredIdle.length
    : null;

  const computeColumns: Column<ComputeRecord>[] = [
    {
      key: 'name',
      header: 'Cluster',
      render: (r) => (
        <div className="stack-sm">
          <span>{r.clusterName}</span>
          <span className="muted mono">{r.clusterId}</span>
        </div>
      ),
      sortValue: (r) => r.clusterName,
    },
    { key: 'ws', header: 'Workspace', render: (r) => r.workspaceName, sortValue: (r) => r.workspaceName },
    {
      key: 'source',
      header: 'Created by',
      render: (r) => <Badge tone={r.source === 'JOB' ? 'ok' : 'warn'}>{r.source}</Badge>,
      sortValue: (r) => r.source,
    },
    { key: 'node', header: 'Node type', render: (r) => <span className="mono">{r.nodeTypeId}</span>, sortValue: (r) => r.nodeTypeId },
    {
      key: 'photon',
      header: 'Photon',
      render: (r) => (r.photon ? <Badge tone="ok">on</Badge> : <Badge tone="neutral">off</Badge>),
      sortValue: (r) => String(r.photon),
    },
    {
      key: 'autoterm',
      header: 'Auto-termination',
      align: 'right',
      render: (r) =>
        r.autoterminationMinutes > 0 ? (
          <span className="numeric">{r.autoterminationMinutes} min</span>
        ) : (
          <Badge tone="danger">disabled</Badge>
        ),
      sortValue: (r) => r.autoterminationMinutes,
    },
    {
      key: 'scale',
      header: 'Workers',
      align: 'right',
      render: (r) =>
        r.minWorkers === null ? (
          <span className="muted">fixed</span>
        ) : (
          <span className="numeric">
            {r.minWorkers}&ndash;{r.maxWorkers}
          </span>
        ),
      sortValue: (r) => r.maxWorkers,
    },
    {
      key: 'uptime',
      header: 'Uptime (h)',
      align: 'right',
      render: (r) => <span className="numeric">{formatNumber(r.observedUptimeHours, 1)}</span>,
      sortValue: (r) => r.observedUptimeHours,
    },
    {
      key: 'idle',
      header: 'Idle',
      align: 'right',
      render: (r) =>
        r.idlePercent === null ? (
          <span className="muted">No telemetry</span>
        ) : (
          <span className="numeric">{formatPercent(r.idlePercent / 100)}</span>
        ),
      sortValue: (r) => r.idlePercent,
    },
    {
      key: 'spot',
      header: 'Driver on spot',
      render: (r) => (r.spotDriver ? <Badge tone="danger">yes</Badge> : <span className="muted">no</span>),
      sortValue: (r) => String(r.spotDriver),
    },
  ];

  const warehouseColumns: Column<WarehouseRecord>[] = [
    { key: 'name', header: 'Warehouse', render: (r) => r.name, sortValue: (r) => r.name },
    { key: 'ws', header: 'Workspace', render: (r) => r.workspaceName, sortValue: (r) => r.workspaceName },
    { key: 'size', header: 'Size', render: (r) => r.size, sortValue: (r) => r.size },
    {
      key: 'type',
      header: 'Type',
      render: (r) => <Badge tone={r.serverless ? 'accent' : 'neutral'}>{r.serverless ? 'serverless' : 'classic'}</Badge>,
      sortValue: (r) => String(r.serverless),
    },
    {
      key: 'autostop',
      header: 'Auto-stop',
      align: 'right',
      render: (r) => <span className="numeric">{r.autoStopMinutes} min</span>,
      sortValue: (r) => r.autoStopMinutes,
    },
    {
      key: 'clusters',
      header: 'Clusters',
      align: 'right',
      render: (r) => (
        <span className="numeric">
          {r.minClusters}&ndash;{r.maxClusters}
        </span>
      ),
      sortValue: (r) => r.maxClusters,
    },
    {
      key: 'queries',
      header: 'Queries',
      align: 'right',
      render: (r) =>
        r.queryCount === null ? <span className="muted">Pending telemetry</span> : <span className="numeric">{formatNumber(r.queryCount)}</span>,
      sortValue: (r) => r.queryCount,
    },
    {
      key: 'queue',
      header: 'p95 queue',
      align: 'right',
      render: (r) =>
        r.p95QueueSeconds === null ? <span className="muted">&mdash;</span> : <span className="numeric">{formatNumber(r.p95QueueSeconds, 1)}s</span>,
      sortValue: (r) => r.p95QueueSeconds,
    },
    {
      key: 'spill',
      header: 'Spill',
      align: 'right',
      render: (r) =>
        r.spillGb === null ? <span className="muted">&mdash;</span> : <span className="numeric">{formatNumber(r.spillGb, 1)} GB</span>,
      sortValue: (r) => r.spillGb,
    },
  ];

  const workloadColumns: Column<WorkloadRecord>[] = [
    { key: 'name', header: 'Job', render: (r) => r.jobName, sortValue: (r) => r.jobName },
    { key: 'ws', header: 'Workspace', render: (r) => r.workspaceName, sortValue: (r) => r.workspaceName },
    {
      key: 'compute',
      header: 'Compute',
      render: (r) => <Badge tone={r.computeType === 'all-purpose' ? 'danger' : 'neutral'}>{r.computeType}</Badge>,
      sortValue: (r) => r.computeType,
    },
    { key: 'runs', header: 'Runs', align: 'right', render: (r) => formatNumber(r.runCount), sortValue: (r) => r.runCount },
    {
      key: 'fail',
      header: 'Failure rate',
      align: 'right',
      render: (r) =>
        r.failureRatePercent === null ? <span className="muted">&mdash;</span> : <span className="numeric">{formatPercent(r.failureRatePercent / 100)}</span>,
      sortValue: (r) => r.failureRatePercent,
    },
    {
      key: 'p95',
      header: 'p95 duration',
      align: 'right',
      render: (r) =>
        r.p95DurationSeconds === null ? <span className="muted">&mdash;</span> : <span className="numeric">{formatNumber(r.p95DurationSeconds / 60, 1)} min</span>,
      sortValue: (r) => r.p95DurationSeconds,
    },
    {
      key: 'cost',
      header: 'Observed cost',
      align: 'right',
      render: (r) =>
        r.observedCost === null ? (
          <span className="muted">Not attributable</span>
        ) : (
          <span className="numeric">{formatMoney(r.observedCost, r.currency)}</span>
        ),
      sortValue: (r) => r.observedCost,
    },
    {
      key: 'owner',
      header: 'Owner',
      render: (r) => r.owner ?? <span className="muted">Unowned</span>,
      sortValue: (r) => r.owner,
    },
  ];

  const computeTypeDistribution = Object.entries(
    results.workloads.reduce<Record<string, number>>((acc, w) => {
      acc[w.computeType] = (acc[w.computeType] ?? 0) + 1;
      return acc;
    }, {}),
  ).map(([label, value]) => ({ label, value }));

  return (
    <div className="stack-lg">
      <div className="grid-4">
        <KpiCard label="Clusters observed" value={compute.length} accent="neutral" />
        <KpiCard
          label="Average idle"
          value={avgIdle === null ? null : formatPercent(avgIdle / 100)}
          absentText="No idle telemetry"
          note={
            avgIdle === null
              ? 'Cluster event telemetry was not available for the window.'
              : `Measured across ${measuredIdle.length} of ${compute.length} clusters.`
          }
          accent={avgIdle !== null && avgIdle > 40 ? 'warn' : 'ok'}
        />
        <KpiCard
          label="Interactive clusters without auto-termination"
          value={compute.filter((c) => c.source !== 'JOB' && c.autoterminationMinutes === 0).length}
          accent="danger"
        />
        <KpiCard
          label="SQL warehouses"
          value={warehouses.length}
          note={`${warehouses.filter((w) => w.serverless).length} serverless`}
          accent="neutral"
        />
      </div>

      {compute.some((c) => c.idlePercent === null) && (
        <Callout tone="warn" title="Some clusters have no idle telemetry">
          Those rows show &ldquo;No telemetry&rdquo; instead of zero, and no idle-based finding is raised
          against them.
        </Callout>
      )}

      <Panel title="Clusters" subtitle="Configuration and observed behavior for every cluster in scope.">
        <DataTable columns={computeColumns} rows={compute} rowKey={(r) => r.clusterId} maxHeight={460} />
      </Panel>

      <Panel title="SQL warehouses" subtitle="Sizing, auto-stop, and query behavior.">
        <DataTable columns={warehouseColumns} rows={warehouses} rowKey={(r) => r.id} />
      </Panel>

      <div className="grid-2">
        <Panel title="Workloads by compute type" subtitle="All-purpose compute for scheduled work is the classic overspend pattern.">
          <DistributionChart data={computeTypeDistribution} unit=" jobs" />
        </Panel>
        <Panel title="Workload cost attribution">
          <p className="muted">
            {workloads.filter((w) => w.observedCost !== null).length} of {workloads.length} jobs could
            be tied to observed cost. The remainder ran on shared compute that cannot be split
            without instrumentation, and is reported as not attributable rather than estimated.
          </p>
        </Panel>
      </div>

      <Panel title="Jobs and pipelines">
        <DataTable columns={workloadColumns} rows={workloads} rowKey={(r) => r.jobId} maxHeight={420} />
      </Panel>
    </div>
  );
}
