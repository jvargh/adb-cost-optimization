import { Callout, KpiCard, Meter, Panel, StatusBadge, DataTable, type Column } from '@/components';
import { TrendChart, RankedBarChart } from '@/components/charts';
import { formatMoney, formatPercent, formatNumber, STATUS_MEANING } from '@/lib/format';
import type { AssessmentResults, CollectionSource } from '@/types';

export function ExecutiveTab({ results }: { results: AssessmentResults }) {
  const { reconciliation, attribution, telemetry, candidates, benefits, collection } = results;
  const costAvailable = reconciliation.authoritativeTotal !== null && reconciliation.authoritativeTotal > 0;
  const currency = reconciliation.currency;

  const degraded = collection.filter((s) => s.status !== 'passed' && s.status !== 'skipped');
  const failed = collection.filter((s) => s.status === 'failed');

  const topDrivers = results.costDrivers.slice(0, 8).map((d) => ({
    key: d.driver,
    label: d.displayName,
    value: d.observedCost,
  }));

  const sourceColumns: Column<CollectionSource>[] = [
    { key: 'name', header: 'Source', render: (r) => r.name, sortValue: (r) => r.name },
    {
      key: 'status',
      header: 'Status',
      render: (r) => <StatusBadge status={r.status} title={STATUS_MEANING[r.status]} />,
      sortValue: (r) => r.status,
    },
    {
      key: 'items',
      header: 'Items',
      align: 'right',
      render: (r) => formatNumber(r.itemCount),
      sortValue: (r) => r.itemCount,
    },
    {
      key: 'limitations',
      header: 'Limitation',
      render: (r) => <span className="muted">{r.error || r.limitations[0] || '\u2014'}</span>,
    },
  ];

  return (
    <div className="stack-lg">
      {failed.length > 0 && (
        <Callout tone="danger" title={`${failed.length} source(s) failed`}>
          The affected evidence is absent, not zero. Figures that depend on it are shown as
          unavailable so no conclusion is drawn from missing data.
        </Callout>
      )}
      {failed.length === 0 && degraded.length > 0 && (
        <Callout tone="warn" title={`${degraded.length} source(s) returned partial or pending telemetry`}>
          The assessment is usable, but confidence on the affected findings is reduced and the gaps
          are itemized on the Evidence quality tab.
        </Callout>
      )}
      {degraded.length === 0 && (
        <Callout tone="ok" title="Every source collected cleanly">
          All configured sources returned complete evidence for the analysis window.
        </Callout>
      )}

      <div className="grid-4">
        <KpiCard
          label={`Authoritative cost (${reconciliation.reportingBasis})`}
          value={costAvailable ? formatMoney(reconciliation.authoritativeTotal, currency) : null}
          note={costAvailable ? 'Azure Cost Management is the single source of truth.' : 'Cost Management evidence was not collected.'}
          accent={costAvailable ? 'accent' : 'danger'}
        />
        <KpiCard
          label="Spend attributed to a workspace"
          value={costAvailable ? formatPercent(attribution.spendCoveragePercent / 100) : null}
          note={
            costAvailable
              ? `${formatNumber(attribution.attributedResourceCount)} of ${formatNumber(attribution.resourceCount)} resources attributed`
              : undefined
          }
          accent={attribution.spendCoveragePercent >= 90 ? 'ok' : 'warn'}
        />
        <KpiCard
          label="Optimization candidates"
          value={candidates.candidateCount}
          note={`${candidates.insufficientEvidenceCount} more need additional evidence before they can be judged.`}
          accent={candidates.candidateCount > 0 ? 'warn' : 'ok'}
        />
        <KpiCard
          label="Estimated savings"
          value={null}
          absentText="Not estimated"
          note="Savings are never estimated without human validation of business context and SLAs."
          accent="neutral"
        />
      </div>

      <div className="grid-2">
        <Panel
          title="Evidence confidence"
          subtitle={`Overall ${telemetry.overall.level} \u00b7 score ${telemetry.overall.score.toFixed(2)}`}
        >
          <div className="stack-sm">
            {Object.entries(telemetry.overall.metrics).map(([metric, value]) => (
              <div className="stack-sm" key={metric}>
                <div className="row-between">
                  <span className="muted">{humanize(metric)}</span>
                  <span className="numeric">{formatPercent(value as number)}</span>
                </div>
                <Meter
                  value={value as number}
                  color={(value as number) >= 0.8 ? 'var(--ok)' : (value as number) >= 0.6 ? 'var(--warn)' : 'var(--danger)'}
                />
              </div>
            ))}
          </div>
        </Panel>

        <Panel
          title="Cost reconciliation"
          subtitle="Proves the collected detail ties back to the authoritative billing total."
        >
          {costAvailable ? (
            <div className="stack-sm">
              <Row label="Authoritative total" value={formatMoney(reconciliation.authoritativeTotal, currency)} />
              <Row label="Matched to a workspace" value={formatMoney(reconciliation.matchedCost, currency)} />
              <Row label="Unmatched" value={formatMoney(reconciliation.unmatchedCost, currency)} />
              <Row label="Shared cost allocated" value={formatMoney(reconciliation.allocatedSharedCost, currency)} />
              <Row
                label="Variance"
                value={`${formatMoney(reconciliation.varianceAmount, currency)} (${formatPercent(reconciliation.variancePercent === null ? null : reconciliation.variancePercent / 100)})`}
              />
              <Callout tone={reconciliation.withinTolerance ? 'ok' : 'warn'}>
                {reconciliation.withinTolerance
                  ? 'Variance is within tolerance, so the detail below can be trusted for prioritization.'
                  : 'Variance is outside tolerance. Treat per-workspace attribution as indicative until the gap is explained.'}
              </Callout>
            </div>
          ) : (
            <Callout tone="danger" title="No cost baseline">
              Cost Management returned no usable data for this scope, so reconciliation could not be
              performed. This is reported rather than substituted with zero.
            </Callout>
          )}
        </Panel>
      </div>

      <Panel
        title="Cost trend"
        subtitle={`Daily ${reconciliation.reportingBasis} across the analysis window, split by DBU and infrastructure.`}
      >
        {results.costTrend.length > 0 ? (
          <TrendChart
            data={results.costTrend as unknown as Record<string, string | number>[]}
            currency={currency}
            series={[
              { key: 'dbuCost', label: 'DBU' },
              { key: 'infrastructureCost', label: 'Infrastructure' },
            ]}
          />
        ) : (
          <Callout tone="danger" title="No daily cost series">
            Daily cost could not be retrieved for this scope.
          </Callout>
        )}
      </Panel>

      <Panel title="Top cost drivers" subtitle="Ranked by observed cost in the analysis window.">
        {topDrivers.length > 0 ? (
          <RankedBarChart data={topDrivers} currency={currency} />
        ) : (
          <Callout tone="danger" title="No cost drivers">Cost detail is unavailable for this scope.</Callout>
        )}
      </Panel>

      <Panel
        title="Source collection status"
        subtitle="Explicit per-source outcome. Nothing is hidden behind an aggregate."
      >
        <DataTable columns={sourceColumns} rows={collection} rowKey={(r) => r.name} />
      </Panel>

      <Panel
        title="Benefits baseline"
        subtitle="Locked so later realized savings can be measured against a defensible starting point."
      >
        <div className="grid-3">
          <KpiCard
            label="Baseline cost"
            value={costAvailable ? formatMoney(benefits.authoritativeCost, benefits.currency) : null}
            note={`Basis ${benefits.reportingBasis}`}
          />
          <KpiCard
            label="Realized savings"
            value={benefits.realizedSavings}
            absentText="Not yet measurable"
            note="Realized savings require a post-change measurement window."
          />
          <KpiCard
            label="Workload normalization"
            value={benefits.workloadNormalization.method}
            note={benefits.workloadNormalization.reason}
          />
        </div>
      </Panel>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="row-between">
      <span className="muted">{label}</span>
      <span className="numeric">{value}</span>
    </div>
  );
}

function humanize(key: string): string {
  return key.replace(/([A-Z])/g, ' $1').replace(/^./, (c) => c.toUpperCase());
}
