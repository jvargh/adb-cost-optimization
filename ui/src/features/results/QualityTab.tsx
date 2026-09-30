import { Callout, DataTable, KpiCard, Panel, StatusBadge, type Column } from '@/components';
import { QualityRadar } from '@/components/charts';
import { STATUS_MEANING, formatNumber, formatPercent } from '@/lib/format';
import type { AssessmentResults, EvidenceGap, CollectionSource } from '@/types';
import { MODULES } from '@/types/capabilities';
import { CollectionOutcome } from './CollectionOutcome';

export function QualityTab({ results }: { results: AssessmentResults }) {
  const { telemetry, collection, evidenceGaps, scopeFilter } = results;

  const radar = Object.entries(telemetry.overall.metrics).map(([metric, value]) => ({
    metric: metric.replace(/([A-Z])/g, ' $1'),
    value: value as number,
  }));

  const sourceColumns: Column<(typeof telemetry.sources)[number]> = {
    key: 'source',
    header: 'Source',
    render: (r) => r.source,
    sortValue: (r) => r.source,
  };

  const gapColumns: Column<EvidenceGap>[] = [
    { key: 'source', header: 'Source', render: (r) => r.source, sortValue: (r) => r.source },
    { key: 'status', header: 'Status', render: (r) => r.status, sortValue: (r) => r.status },
    { key: 'impact', header: 'What this blocks', render: (r) => <span className="muted">{r.impact}</span> },
    {
      key: 'unlock',
      header: 'Required to unlock',
      render: (r) => (
        <div className="stack-sm">
          {r.requiredToUnlock.map((item, index) => (
            <span className="muted" key={index}>
              &bull; {item}
            </span>
          ))}
        </div>
      ),
    },
  ];

  const scopeRows = Object.entries(scopeFilter.entities).map(([entity, counts]) => ({
    entity,
    ...counts,
  }));

  const limitationSources: CollectionSource[] = collection.filter(
    (s) => s.limitations.length > 0 || s.error,
  );

  return (
    <div className="stack-lg">
      <CollectionOutcome results={results} />
      <Callout tone="info" title="Confidence is derived, not asserted">
        Every finding carries a confidence score built from completeness, coverage, freshness,
        consistency, sample adequacy, attribution quality, source authority, and collection success.
        Low scores are surfaced rather than hidden so reviewers can weight the findings correctly.
      </Callout>

      {results.capabilities?.workspaceCoverage && <Panel title="Workspace capability coverage" subtitle="Saved evidence only, not a live permission check. Unknown and unselected modules are not passing controls.">
        <DataTable rows={results.capabilities.workspaceCoverage} rowKey={r => r.workspaceId} columns={[
          { key: 'workspace', header: 'Workspace', render: r => <>{r.workspaceName}<br />{r.workspaceId}</> },
          ...MODULES.map(module => ({ key: module, header: module, render: (r: NonNullable<NonNullable<AssessmentResults['capabilities']>['workspaceCoverage']>[number]) => `${r.modules[module].status} (${r.modules[module].rows} rows)` })),
        ]} />
      </Panel>}

      <div className="grid-4">
        <KpiCard
          label="Overall confidence"
          value={`${telemetry.overall.level} (${telemetry.overall.score.toFixed(2)})`}
          accent={
            telemetry.overall.level === 'high' ? 'ok' : telemetry.overall.level === 'medium' ? 'warn' : 'danger'
          }
        />
        <KpiCard
          label="Sources passed"
          value={`${collection.filter((s) => s.status === 'passed').length} / ${collection.length}`}
          accent="neutral"
        />
        <KpiCard
          label="Pending telemetry"
          value={collection.filter((s) => s.status === 'pending telemetry').length}
          note="Pending telemetry means the source exists but the evidence window was empty. It is not zero."
          accent="warn"
        />
        <KpiCard
          label="Evidence gaps"
          value={evidenceGaps.length}
          note="Each gap names exactly what would unlock it."
          accent={evidenceGaps.length ? 'warn' : 'ok'}
        />
      </div>

      <div className="grid-2">
        <Panel title="Quality dimensions" subtitle="Overall scores across the eight measured dimensions.">
          <QualityRadar metrics={radar} />
        </Panel>
        <Panel title="Per-source confidence">
          <DataTable
            columns={[
              sourceColumns,
              {
                key: 'level',
                header: 'Level',
                render: (r) => r.level,
                sortValue: (r) => r.score,
              },
              {
                key: 'score',
                header: 'Score',
                align: 'right',
                render: (r) => <span className="numeric">{r.score.toFixed(2)}</span>,
                sortValue: (r) => r.score,
              },
              {
                key: 'missing',
                header: 'Missing metrics',
                render: (r) =>
                  r.missingRequiredMetrics.length === 0 ? (
                    <span className="muted">None</span>
                  ) : (
                    <span className="muted">{r.missingRequiredMetrics.join(', ')}</span>
                  ),
              },
            ]}
            rows={telemetry.sources}
            rowKey={(r) => r.source}
            maxHeight={320}
          />
        </Panel>
      </div>

      <Panel
        title="Evidence gaps"
        subtitle="Stated explicitly so nobody mistakes a gap for a clean result."
      >
        <DataTable columns={gapColumns} rows={evidenceGaps} rowKey={(r) => r.source} />
      </Panel>

      <Panel
        title="Source limitations"
        subtitle="Recorded failures, partial evidence and skipped-source reasons. A skipped source is not a successful collection."
      >
        <DataTable
          columns={[
            { key: 'name', header: 'Source', render: (r: CollectionSource) => r.name, sortValue: (r) => r.name },
            {
              key: 'status',
              header: 'Status',
              render: (r: CollectionSource) => <StatusBadge status={r.status} title={STATUS_MEANING[r.status]} />,
              sortValue: (r) => r.status,
            },
            {
              key: 'detail',
              header: 'Detail',
              render: (r: CollectionSource) => (
                <div className="stack-sm">
                  {r.error && <span className="muted">{r.error}</span>}
                  {r.limitations.map((l, i) => (
                    <span className="muted" key={i}>
                      &bull; {l}
                    </span>
                  ))}
                </div>
              ),
            },
          ]}
          rows={limitationSources}
          rowKey={(r) => r.name}
          emptyTitle="No collector reported a limitation"
        />
      </Panel>

      <Panel
        title="Scope isolation proof"
        subtitle="Records excluded because they fell outside the selected resource groups."
      >
        <DataTable
          columns={[
            { key: 'entity', header: 'Entity', render: (r: (typeof scopeRows)[number]) => r.entity, sortValue: (r) => r.entity },
            {
              key: 'in',
              header: 'Input',
              align: 'right',
              render: (r: (typeof scopeRows)[number]) => formatNumber(r.inputRecords),
              sortValue: (r) => r.inputRecords,
            },
            {
              key: 'kept',
              header: 'Included',
              align: 'right',
              render: (r: (typeof scopeRows)[number]) => formatNumber(r.includedRecords),
              sortValue: (r) => r.includedRecords,
            },
            {
              key: 'excluded',
              header: 'Excluded',
              align: 'right',
              render: (r: (typeof scopeRows)[number]) => formatNumber(r.excludedRecords),
              sortValue: (r) => r.excludedRecords,
            },
            {
              key: 'rate',
              header: 'Retained',
              align: 'right',
              render: (r: (typeof scopeRows)[number]) => (
                <span className="numeric">
                  {formatPercent(r.inputRecords ? r.includedRecords / r.inputRecords : 0)}
                </span>
              ),
              sortValue: (r) => (r.inputRecords ? r.includedRecords / r.inputRecords : 0),
            },
          ]}
          rows={scopeRows}
          rowKey={(r) => r.entity}
        />
      </Panel>
    </div>
  );
}
