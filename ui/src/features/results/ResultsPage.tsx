import { useMemo, useState } from 'react';
import {
  Callout,
  ChipGroup,
  EmptyState,
  Panel,
  Spinner,
  Tabs,
  WorkflowNextStep,
} from '@/components';
import { useConfigStore, useResultsStore, useRunStore, activeFilterCount, filterFindings } from '@/state';
import { FINDING_CATEGORY_LABELS } from '@/types';
import { ExecutiveTab } from './ExecutiveTab';
import { CostTab } from './CostTab';
import { ComputeTab } from './ComputeTab';
import { FindingsTab } from './FindingsTab';
import { QualityTab } from './QualityTab';
import { RoadmapTab } from './RoadmapTab';
import { FindingDrawer } from './FindingDrawer';

const TAB_IDS = ['executive', 'cost', 'compute', 'findings', 'quality', 'roadmap'] as const;
type TabId = (typeof TAB_IDS)[number];

export function ResultsPage({ onReview }: { onReview: () => void }) {
  const { results, loading, error, runId, filters, toggleFilter, setFilter, clearFilters } =
    useResultsStore();
  const { phase } = useRunStore();
  const validating = useConfigStore((s) => s.validating);
  const [tab, setTab] = useState<TabId>('executive');
  const [showFilters, setShowFilters] = useState(false);

  const facets = useMemo(() => {
    if (!results) return null;
    const findings = results.candidates.findings;
    const unique = (values: (string | null)[]) =>
      [...new Set(values.filter((v): v is string => Boolean(v)))].sort();
    return {
      subscriptions: unique(results.manifest.scope.subscriptionIds),
      resourceGroups: unique(results.manifest.scope.resourceGroups),
      workspaces: unique(results.manifest.scope.workspaces.map((w) => w.name)),
      workloads: unique(findings.map((f) => f.scope.workload)),
      categories: unique(findings.map((f) => f.category)),
    };
  }, [results]);

  const visibleFindingCount = useMemo(
    () => (results ? filterFindings(results.candidates.findings, filters).length : 0),
    [results, filters],
  );

  if (loading) {
    return (
      <Panel title="Loading assessment run">
        <Spinner label="Reading persisted artifacts from the run directory..." />
      </Panel>
    );
  }

  if (error) {
    return (
      <div className="stack-lg">
        <Callout tone="danger" title="Could not load the run">
          {error}
          <p>Select another saved snapshot from the dropdown next to Light/Dark.</p>
        </Callout>
      </div>
    );
  }

  if (!results || !runId) {
    return (
      <div className="stack-lg">
        <EmptyState
          title={validating ? 'No new results yet - validation is still running' : 'No assessment run is open'}
          detail={validating ? 'Step 2 is checking access. Start analysis in step 3 after validation finishes, or select an earlier snapshot from the dropdown next to Light/Dark.'
            : !['idle', 'completed', 'failed', 'canceled'].includes(phase) ? 'The current assessment is still running. Earlier snapshots are available in the dropdown next to Light/Dark.'
            : 'Select a saved snapshot from the dropdown next to Light/Dark, or start a new assessment in step 3. Browsing this page does not start an assessment.'}
        />
      </div>
    );
  }

  const filterCount = activeFilterCount(filters);

  return (
    <div className="stack-lg">
      <Callout tone="info" title="Viewing a saved snapshot">
        These results were collected {results.manifest.startedAtUtc.slice(0, 10)} and are not live.
        Reopening them does not query Azure or Databricks. The snapshot remains available after restarting the app.
        Select another run using the Saved snapshots dropdown next to Light/Dark.
      </Callout>
      <Panel
        title={`Run ${results.manifest.runId}`}
        subtitle={`${results.manifest.customerId} \u00b7 ${results.manifest.analysisWindow.startUtc.slice(0, 10)} to ${results.manifest.analysisWindow.endUtc.slice(0, 10)} \u00b7 basis ${results.reconciliation.reportingBasis}`}
        actions={
          <>
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              onClick={() => setShowFilters(!showFilters)}
            >
              {showFilters ? 'Hide filters' : 'Filters'}
              {filterCount > 0 ? ` (${filterCount})` : ''}
            </button>
            {filterCount > 0 && (
              <button type="button" className="btn btn-ghost btn-sm" onClick={clearFilters}>
                Clear
              </button>
            )}
          </>
        }
      >
        {showFilters && facets ? (
          <div className="stack">
            <label className="field">
              <span className="field-label">Search findings</span>
              <input
                className="input"
                value={filters.search}
                placeholder="Detector ID, title, or explanation"
                onChange={(e) => setFilter('search', e.target.value)}
              />
            </label>
            <div className="grid-2">
              <ChipGroup
                label="Subscription"
                options={facets.subscriptions.map((v) => ({ value: v, label: v.slice(0, 8) }))}
                selected={filters.subscriptionIds}
                onToggle={(v) => toggleFilter('subscriptionIds', v)}
              />
              <ChipGroup
                label="Resource group"
                options={facets.resourceGroups.map((v) => ({ value: v, label: v }))}
                selected={filters.resourceGroups}
                onToggle={(v) => toggleFilter('resourceGroups', v)}
              />
              <ChipGroup
                label="Workspace"
                options={facets.workspaces.map((v) => ({ value: v, label: v }))}
                selected={filters.workspaces}
                onToggle={(v) => toggleFilter('workspaces', v)}
              />
              <ChipGroup
                label="Workload"
                options={facets.workloads.map((v) => ({ value: v, label: v }))}
                selected={filters.workloads}
                onToggle={(v) => toggleFilter('workloads', v)}
              />
              <ChipGroup
                label="Finding category"
                options={facets.categories.map((v) => ({
                  value: v,
                  label: FINDING_CATEGORY_LABELS[v as keyof typeof FINDING_CATEGORY_LABELS] ?? v,
                }))}
                selected={filters.categories}
                onToggle={(v) => toggleFilter('categories', v)}
              />
              <div className="grid-2">
                <ChipGroup
                  label="Confidence"
                  options={['high', 'medium', 'low'].map((v) => ({ value: v, label: v }))}
                  selected={filters.confidence}
                  onToggle={(v) => toggleFilter('confidence', v)}
                />
                <ChipGroup
                  label="Status"
                  options={[
                    { value: 'candidate', label: 'candidate' },
                    { value: 'insufficient_evidence', label: 'insufficient evidence' },
                  ]}
                  selected={filters.status}
                  onToggle={(v) => toggleFilter('status', v)}
                />
              </div>
            </div>
          </div>
        ) : (
          <span className="muted">
            Filters apply to findings and to every scope-aware table on the technical tabs.
          </span>
        )}
      </Panel>

      <Tabs
        active={tab}
        onChange={(id) => setTab(id as TabId)}
        tabs={[
          { id: 'executive', label: 'Executive summary' },
          { id: 'cost', label: 'Cost analysis' },
          { id: 'compute', label: 'Compute and SQL' },
          { id: 'findings', label: 'Findings', badge: visibleFindingCount },
          { id: 'quality', label: 'Evidence quality' },
          { id: 'roadmap', label: 'Roadmap' },
        ]}
      />

      {tab === 'executive' && <ExecutiveTab results={results} />}
      {tab === 'cost' && <CostTab results={results} />}
      {tab === 'compute' && <ComputeTab results={results} />}
      {tab === 'findings' && <FindingsTab results={results} />}
      {tab === 'quality' && <QualityTab results={results} />}
      {tab === 'roadmap' && <RoadmapTab results={results} />}

      <WorkflowNextStep
        title="Record review decisions"
        detail="Review each finding, enter the reviewer name, and save the decisions."
        actionLabel="Continue to review"
        onAction={onReview}
      />

      <FindingDrawer />
    </div>
  );
}
