import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { CollectionOutcome, getCollectionOutcome } from '@/features/results/CollectionOutcome';
import type { AssessmentResults, CollectionStatus } from '@/types';
import fixture from '../mock/fixtures/contoso-clean.results.json';

function resultsFor(statuses: CollectionStatus[], manifestStatus: AssessmentResults['manifest']['status'] = 'passed') {
  const results = structuredClone(fixture) as AssessmentResults;
  results.manifest.status = manifestStatus;
  results.collection = statuses.map((status, index) => ({
    name: `Source ${index}`, status, startedAtUtc: null, completedAtUtc: null,
    itemCount: 0, outputs: [], limitations: [], error: '', domain: 'databricks',
  }));
  return results;
}

describe('completed collection outcome', () => {
  it('is green with intentional skips but does not count them as passes', () => {
    const results = resultsFor(['passed', 'skipped']);
    expect(getCollectionOutcome(results)).toMatchObject({ needsAttention: false, passed: 1, skipped: 1 });
    render(<CollectionOutcome results={results} />);
    expect(screen.getByText('Assessment completed - collected checks passed').closest('.callout')).toHaveClass('callout-ok');
    expect(screen.getByText(/1 passed; 0 partial/)).toHaveTextContent('1 skipped');
    expect(screen.queryByText(/no checks are running/)).not.toBeInTheDocument();
  });
  it.each<CollectionStatus>(['partial', 'failed', 'pending telemetry'])('is red for unresolved %s evidence even with a passed manifest', (status) => {
    const results = resultsFor(['passed', status, 'skipped']);
    render(<CollectionOutcome results={results} />);
    expect(screen.getByText('Assessment completed - evidence needs attention').closest('.callout')).toHaveClass('callout-danger');
  });
  it('never invents green without collected checks', () => {
    expect(getCollectionOutcome(resultsFor([])).needsAttention).toBe(true);
    expect(getCollectionOutcome(resultsFor(['skipped'])).needsAttention).toBe(true);
  });
  it('retains a failed manifest even if its collectors passed', () => {
    const outcome = getCollectionOutcome(resultsFor(['passed'], 'failed'));
    expect(outcome.needsAttention).toBe(true);
    expect(outcome.title).toBe('Assessment failed - action required');
  });
});
