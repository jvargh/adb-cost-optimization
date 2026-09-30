import { useMemo, useState } from 'react';
import { Callout, DataTable, Panel, Tabs, type Column } from '@/components';
import { BreakdownChart, RankedBarChart, TrendChart } from '@/components/charts';
import { formatMoney, formatPercent } from '@/lib/format';
import { useResultsStore, filterByScope } from '@/state';
import type { AssessmentResults, CostBreakdownSlice, CostDriver } from '@/types';

const DIMENSIONS: { id: CostBreakdownSlice['dimension']; label: string; hint: string }[] = [
  { id: 'service', label: 'Service', hint: 'Which Azure services carry the spend.' },
  { id: 'meterCategory', label: 'Meter category', hint: 'Billing meters behind the service totals.' },
  { id: 'sku', label: 'SKU', hint: 'The specific SKUs being billed.' },
  { id: 'resourceGroup', label: 'Resource group', hint: 'Spend by scope container.' },
  { id: 'workspace', label: 'Workspace', hint: 'Spend attributed to each Databricks workspace.' },
  { id: 'tagOwner', label: 'Owner tag', hint: 'Chargeback readiness. Untagged spend cannot be charged back.' },
];

export function CostTab({ results }: { results: AssessmentResults }) {
  const filters = useResultsStore((s) => s.filters);
  const [dimension, setDimension] = useState<CostBreakdownSlice['dimension']>('service');
  const currency = results.reconciliation.currency;

  const drivers = useMemo(
    () => filterByScope(results.costDrivers as unknown as (CostDriver & { workspaceName: string | null })[], filters),
    [results.costDrivers, filters],
  );

  const slices = results.costBreakdown.filter((s) => s.dimension === dimension);
  const dimensionTotal = slices.reduce((total, s) => total + s.cost, 0);

  if (results.reconciliation.authoritativeTotal === null || results.reconciliation.authoritativeTotal <= 0) {
    return (
      <Callout tone="danger" title="No cost evidence for this run">
        Azure Cost Management could not be read for the selected scope, so no cost analysis can be
        presented. The remaining tabs still contain configuration and governance evidence.
      </Callout>
    );
  }

  const driverColumns: Column<CostDriver>[] = [
    { key: 'rank', header: '#', align: 'right', width: '52px', render: (r) => r.rank, sortValue: (r) => r.rank },
    {
      key: 'name',
      header: 'Resource',
      render: (r) => (
        <div className="stack-sm">
          <span>{r.displayName}</span>
          <span className="muted mono truncate">{r.resourceType}</span>
        </div>
      ),
      sortValue: (r) => r.displayName,
    },
    { key: 'rg', header: 'Resource group', render: (r) => r.resourceGroup, sortValue: (r) => r.resourceGroup },
    {
      key: 'ws',
      header: 'Workspace',
      render: (r) => r.workspaceName ?? <span className="muted">Unattributed</span>,
      sortValue: (r) => r.workspaceName,
    },
    {
      key: 'cost',
      header: 'Observed cost',
      align: 'right',
      render: (r) => <span className="numeric">{formatMoney(r.observedCost, r.currency)}</span>,
      sortValue: (r) => r.observedCost,
    },
  ];

  return (
    <div className="stack-lg">
      <Panel
        title="Daily cost"
        subtitle="Actual and amortized side by side so reservation and savings-plan effects stay visible."
      >
        <TrendChart
          data={results.costTrend as unknown as Record<string, string | number>[]}
          currency={currency}
          series={[
            { key: 'actualCost', label: 'Actual' },
            { key: 'amortizedCost', label: 'Amortized' },
          ]}
        />
      </Panel>

      <Panel
        title="Cost breakdown"
        subtitle={DIMENSIONS.find((d) => d.id === dimension)?.hint}
        actions={
          <Tabs
            active={dimension}
            onChange={(id) => setDimension(id as CostBreakdownSlice['dimension'])}
            tabs={DIMENSIONS.map((d) => ({ id: d.id, label: d.label }))}
          />
        }
      >
        <div className="grid-2">
          <BreakdownChart
            data={slices.map((s) => ({ key: s.key, label: s.label, value: s.cost }))}
            currency={currency}
          />
          <DataTable
            columns={[
              { key: 'label', header: DIMENSIONS.find((d) => d.id === dimension)!.label, render: (r: CostBreakdownSlice) => r.label, sortValue: (r) => r.label },
              {
                key: 'cost',
                header: 'Cost',
                align: 'right',
                render: (r: CostBreakdownSlice) => <span className="numeric">{formatMoney(r.cost, r.currency)}</span>,
                sortValue: (r) => r.cost,
              },
              {
                key: 'share',
                header: 'Share',
                align: 'right',
                render: (r: CostBreakdownSlice) => (
                  <span className="numeric">{formatPercent(dimensionTotal ? r.cost / dimensionTotal : 0)}</span>
                ),
                sortValue: (r) => r.cost,
              },
            ]}
            rows={slices}
            rowKey={(r) => `${r.dimension}:${r.key}`}
            maxHeight={300}
          />
        </div>
      </Panel>

      <Panel
        title="Attribution coverage"
        subtitle="Unattributed spend is the ceiling on any chargeback or accountability conversation."
      >
        <div className="grid-2">
          <BreakdownChart
            currency={currency}
            data={[
              {
                key: 'attributed',
                label: 'Attributed to a workspace',
                value: results.attribution.attributedSpend,
              },
              {
                key: 'unattributed',
                label: 'Unattributed',
                value: Math.max(0, results.attribution.totalSpend - results.attribution.attributedSpend),
              },
            ]}
          />
          <div className="stack">
            <p className="muted">
              {formatPercent(results.attribution.spendCoveragePercent / 100)} of spend and{' '}
              {formatPercent(results.attribution.resourceCoveragePercent / 100)} of resources map to a
              known workspace. Everything else is reported as unattributed rather than being
              distributed by assumption.
            </p>
            <RankedBarChart
              currency={currency}
              height={220}
              data={results.costBreakdown
                .filter((s) => s.dimension === 'tagOwner')
                .map((s) => ({ key: s.key, label: s.label, value: s.cost }))}
            />
          </div>
        </div>
      </Panel>

      <Panel
        title="Top cost drivers"
        subtitle={`${drivers.length} resource(s) after filters. Sorted by observed cost.`}
      >
        <DataTable columns={driverColumns} rows={drivers} rowKey={(r) => r.driver} maxHeight={420} />
      </Panel>
    </div>
  );
}
