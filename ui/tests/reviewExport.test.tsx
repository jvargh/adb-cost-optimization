import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ExportPage } from '@/features/export/ExportPage';
import { getBackend, setBackend } from '@/api';
import { useResultsStore } from '@/state';
import type { AssessmentResults } from '@/types';
import fixture from '../mock/fixtures/contoso-clean.results.json';
import { defaultOptions } from '@/types/capabilities';

beforeEach(() => {
  setBackend(null);
  useResultsStore.getState().clear();
  const results = structuredClone(fixture) as AssessmentResults;
  useResultsStore.setState({ runId: results.manifest.runId, results });
  vi.spyOn(window, 'confirm').mockReturnValue(true);
});
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe('minimal review and export', () => {
  it('offers downloads with review collapsed and does not require decisions', async () => {
    const save = vi.spyOn(getBackend(), 'saveReview');
    vi.spyOn(getBackend(), 'readArtifact').mockResolvedValue({
      relativePath: 'reports/assessment-report.md', mimeType: 'text/markdown', content: '# Report',
    });
    vi.stubGlobal('URL', class extends URL {
      static createObjectURL = vi.fn(() => 'blob:test');
      static revokeObjectURL = vi.fn();
    });
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined);
    render(<ExportPage />);
    expect(screen.getByLabelText('Reviewer')).not.toBeVisible();
    expect(screen.getByText('Record a decision').closest('details')).not.toHaveAttribute('open');
    fireEvent.click(screen.getByRole('button', { name: 'Download report' }));
    await screen.findByText('Export complete');
    expect(useResultsStore.getState().exportedArtifactPaths).toContain('reports/assessment-report.md');
    expect(save).not.toHaveBeenCalled();
  });

  it('saves a selected decision and note without erasing detailed historical fields or other findings', async () => {
    const original = structuredClone(useResultsStore.getState().results!);
    original.review[0].validationExperiment = 'Preserve existing benchmark';
    original.review[0].ownerApprover = 'Original owner';
    useResultsStore.setState({ results: original });
    const save = vi.spyOn(getBackend(), 'saveReview').mockResolvedValue(undefined);
    render(<ExportPage />);
    fireEvent.click(screen.getByText('Record a decision'));
    fireEvent.change(screen.getByLabelText('Decision'), { target: { value: 'deferred' } });
    fireEvent.change(screen.getByLabelText('Reviewer'), { target: { value: 'Human reviewer' } });
    fireEvent.change(screen.getByLabelText('Note (optional)'), { target: { value: 'Check workload impact first.' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save review decisions' }));
    await screen.findByText(/^Review saved /);
    const saved = save.mock.calls[0][1];
    expect(saved[0]).toMatchObject({ decision: 'deferred', reviewer: 'Human reviewer',
      rationale: 'Check workload impact first.', validationExperiment: 'Preserve existing benchmark', ownerApprover: 'Original owner' });
    expect(saved.slice(1)).toEqual(original.review.slice(1));
    expect(useResultsStore.getState().results?.review).toEqual(saved);
  });

  it('reports missing reviewer and persistence errors, preserves edits, and retries safely', async () => {
    const save = vi.spyOn(getBackend(), 'saveReview').mockRejectedValueOnce(new Error('Disk unavailable')).mockResolvedValue(undefined);
    render(<ExportPage />);
    fireEvent.click(screen.getByText('Record a decision'));
    fireEvent.change(screen.getByLabelText('Decision'), { target: { value: 'accepted' } });
    fireEvent.change(screen.getByLabelText('Reviewer'), { target: { value: '' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save review decisions' }));
    await screen.findByText('Enter a reviewer name for each edited decision before saving.');
    expect(save).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText('Reviewer'), { target: { value: 'Reviewer' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save review decisions' }));
    await screen.findByText('Disk unavailable');
    expect(screen.getByLabelText('Decision')).toHaveValue('accepted');
    fireEvent.click(screen.getByRole('button', { name: 'Save review decisions' }));
    await screen.findByText(/^Review saved /);
    expect(save).toHaveBeenCalledTimes(2);
  });

  it('prevents workbook reload from discarding unsaved review changes', async () => {
    const results = useResultsStore.getState().results!;
    const coverage = { rows: 0, status: 'unavailable', completeWindow: false };
    useResultsStore.setState({ results: { ...results, capabilities: {
      schemaVersion: '1.0', origin: 'native', ruleVersion: '1.0', options: defaultOptions(), limitations: [],
      coverage: { utilization: coverage, sizing: coverage, jobs: coverage, queries: coverage,
        network: coverage, posture: coverage, assets: coverage, commitments: coverage }, workspaceCoverage: [],
    } } });
    render(<ExportPage />);
    fireEvent.click(screen.getByText('Record a decision'));
    fireEvent.change(screen.getByLabelText('Note (optional)'), { target: { value: 'Unsaved note' } });
    expect(screen.getByRole('button', { name: 'Generate workbook artifact' })).toBeDisabled();
    expect(screen.getByText('Unsaved review changes')).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: 'Discard changes' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Generate workbook artifact' })).toBeEnabled());
  });
});
