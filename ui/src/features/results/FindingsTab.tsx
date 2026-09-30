import { useMemo } from 'react';
import { Badge, Callout, ConfidenceBadge, DataTable, KpiCard, Panel, type Column } from '@/components';
import { useResultsStore, filterFindings } from '@/state';
import { FINDING_CATEGORY_LABELS, type AssessmentResults, type Finding } from '@/types';

export function FindingsTab({ results }: { results: AssessmentResults }) {
  const { filters, selectFinding, selectedFinding } = useResultsStore();
  const findings = useMemo(
    () => filterFindings(results.candidates.findings, filters),
    [results.candidates.findings, filters],
  );

  const columns: Column<Finding>[] = [
    {
      key: 'title',
      header: 'Finding',
      render: (r) => (
        <div className="stack-sm">
          <span>{r.title}</span>
          <span className="muted mono">{r.detectorId}</span>
        </div>
      ),
      sortValue: (r) => r.title,
    },
    {
      key: 'category',
      header: 'Category',
      render: (r) => FINDING_CATEGORY_LABELS[r.category] ?? r.category,
      sortValue: (r) => r.category,
    },
    {
      key: 'scope',
      header: 'Scope',
      render: (r) => (
        <div className="stack-sm">
          <span>{r.scope.workspaceName ?? 'Estate-wide'}</span>
          <span className="muted">{r.scope.workload ?? r.scope.resourceGroup ?? '\u2014'}</span>
        </div>
      ),
      sortValue: (r) => r.scope.workspaceName,
    },
    {
      key: 'status',
      header: 'Status',
      render: (r) =>
        r.status === 'candidate' ? (
          <Badge tone="warn">candidate</Badge>
        ) : (
          <Badge tone="neutral">insufficient evidence</Badge>
        ),
      sortValue: (r) => r.status,
    },
    {
      key: 'confidence',
      header: 'Confidence',
      render: (r) => <ConfidenceBadge level={r.confidence.level} score={r.confidence.score} />,
      sortValue: (r) => r.confidence.score,
    },
    {
      key: 'evidence',
      header: 'Evidence',
      align: 'right',
      render: (r) => <span className="numeric">{r.evidence.length}</span>,
      sortValue: (r) => r.evidence.length,
    },
    {
      key: 'savings',
      header: 'Estimated savings',
      align: 'right',
      render: (r) =>
        r.estimatedSavings === null ? (
          <span className="muted">Not estimated</span>
        ) : (
          <span className="numeric">{r.estimatedSavings}</span>
        ),
    },
  ];

  const byCategory = Object.entries(
    findings.reduce<Record<string, number>>((acc, f) => {
      acc[f.category] = (acc[f.category] ?? 0) + 1;
      return acc;
    }, {}),
  );

  return (
    <div className="stack-lg">
      <Callout tone="info" title="Every finding requires human validation">
        These are candidates derived from observed evidence. None of them is a recommendation to act
        until a human has confirmed the business context, SLA, and risk. The toolkit deliberately
        does not estimate savings, because savings depend on decisions it cannot observe.
      </Callout>

      <div className="grid-4">
        <KpiCard label="Findings after filters" value={findings.length} accent="neutral" />
        <KpiCard
          label="Candidates"
          value={findings.filter((f) => f.status === 'candidate').length}
          accent="warn"
        />
        <KpiCard
          label="Insufficient evidence"
          value={findings.filter((f) => f.status === 'insufficient_evidence').length}
          note="A first-class outcome: the pattern may exist but the evidence to judge it is missing."
          accent="neutral"
        />
        <KpiCard
          label="High confidence"
          value={findings.filter((f) => f.confidence.level === 'high').length}
          accent="ok"
        />
      </div>

      <Panel title="Findings by category" subtitle="Aligned to the Azure Databricks cost-optimization pillars.">
        <div className="row-wrap">
          {byCategory.map(([category, count]) => (
            <span className="chip" key={category}>
              {FINDING_CATEGORY_LABELS[category as keyof typeof FINDING_CATEGORY_LABELS] ?? category}
              <strong> {count}</strong>
            </span>
          ))}
        </div>
      </Panel>

      <Panel title="All findings" subtitle="Select a row to inspect its evidence and limitations.">
        <DataTable
          columns={columns}
          rows={findings}
          rowKey={(r) => r.findingId ?? `${r.detectorId}:${r.scope.workspaceName ?? 'estate'}:${r.title}`}
          onRowClick={(r) => selectFinding(r)}
          selectedKey={
            selectedFinding
              ? selectedFinding.findingId ?? `${selectedFinding.detectorId}:${selectedFinding.scope.workspaceName ?? 'estate'}:${selectedFinding.title}`
              : null
          }
        />
      </Panel>
    </div>
  );
}
