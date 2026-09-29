import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { App } from '@/app/App';
import { getBackend, setBackend } from '@/api';
import { MockAssessmentBackend } from '@/api/mockBackend';
import { useConfigStore, useResultsStore, useRunStore } from '@/state';

describe('confirmed snapshot deletion', () => {
  beforeEach(() => {
    vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} });
    setBackend(new MockAssessmentBackend());
    useConfigStore.getState().reset();
    useResultsStore.getState().clear();
    useRunStore.getState().reset();
    useRunStore.setState({ runs: [], runsError: null, loadingRuns: false });
  });
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    setBackend(null);
    window.history.replaceState(null, '', '/');
  });

  async function openHistory() {
    const backend = getBackend();
    const runs = await backend.listRuns();
    window.history.replaceState(null, '', `/?run=${runs[0].runId}`);
    render(<App />);
    await screen.findByText('Viewing a saved snapshot');
    fireEvent.click(screen.getByRole('button', { name: 'Manage snapshots' }));
    const dialog = screen.getByRole('dialog', { name: 'Manage saved snapshots' });
    await waitFor(() => expect(within(dialog).getByRole('button', { name: 'Delete all snapshots' })).toBeEnabled());
    return { backend, runs, dialog };
  }

  it('cancels without deleting, then deletes one snapshot and clears its selected results and URL', async () => {
    const { backend, runs, dialog } = await openHistory();
    const remove = vi.spyOn(backend, 'deleteSnapshots');
    const validate = vi.spyOn(backend, 'validate');
    const discover = vi.spyOn(backend, 'discoverEstate');
    fireEvent.click(within(dialog).getByRole('button', { name: `Delete snapshot ${runs[0].runId}` }));
    expect(remove).not.toHaveBeenCalled();
    expect(within(dialog).getByText(/raw evidence, reports, exports, and review decisions/)).toBeVisible();
    fireEvent.click(within(dialog).getByRole('button', { name: 'Keep snapshots' }));
    expect(remove).not.toHaveBeenCalled();
    fireEvent.click(within(dialog).getByRole('button', { name: `Delete snapshot ${runs[0].runId}` }));
    fireEvent.click(within(dialog).getByRole('button', { name: 'Permanently delete' }));
    await screen.findByText('1 snapshot(s) permanently deleted.');
    expect(remove).toHaveBeenCalledWith([runs[0].runId]);
    expect(new URLSearchParams(window.location.search).get('run')).toBeNull();
    expect(useResultsStore.getState().results).toBeNull();
    await waitFor(() => expect(useRunStore.getState().runs).toHaveLength(runs.length - 1));
    await act(async () => {
      await expect(backend.loadResults(runs[0].runId)).rejects.toThrow('No persisted assessment run');
    });
    expect(validate).not.toHaveBeenCalled();
    expect(discover).not.toHaveBeenCalled();
  });

  it('deletes exactly the confirmed all-history list, not snapshots arriving afterward', async () => {
    const { backend, runs, dialog } = await openHistory();
    const remove = vi.spyOn(backend, 'deleteSnapshots');
    fireEvent.click(within(dialog).getByRole('button', { name: 'Delete all snapshots' }));
    act(() => useRunStore.setState({ runs: [...runs, { ...runs[0], runId: 'newly-arrived' }] }));
    fireEvent.click(within(dialog).getByRole('button', { name: 'Permanently delete' }));
    await screen.findByText(`${runs.length} snapshot(s) permanently deleted.`);
    expect(remove).toHaveBeenCalledTimes(1);
    expect(new Set(remove.mock.calls[0][0])).toEqual(new Set(runs.map((run) => run.runId)));
    await waitFor(() => expect(within(dialog).getByText('No saved snapshots.')).toBeVisible());
  });

  it('shows per-run failures and keeps failed snapshots available', async () => {
    const { backend, runs, dialog } = await openHistory();
    vi.spyOn(backend, 'deleteSnapshots').mockResolvedValue({
      deletedRunIds: [], failures: [{ runId: runs[0].runId, message: 'Active assessments cannot be deleted.' }],
    });
    fireEvent.click(within(dialog).getByRole('button', { name: `Delete snapshot ${runs[0].runId}` }));
    fireEvent.click(within(dialog).getByRole('button', { name: 'Permanently delete' }));
    await screen.findByText('Snapshot deletion did not fully complete');
    expect(within(dialog).getByText(/Active assessments cannot be deleted/)).toBeVisible();
    expect(useResultsStore.getState().runId).toBe(runs[0].runId);
    expect(within(dialog).queryByText('1 snapshot(s) permanently deleted.')).not.toBeInTheDocument();
  });

  it('disables deletion during an active assessment', async () => {
    const { runs, dialog } = await openHistory();
    act(() => useRunStore.setState({ phase: 'collecting' }));
    expect(within(dialog).getByRole('button', { name: 'Delete all snapshots' })).toBeDisabled();
    expect(within(dialog).getByRole('button', { name: `Delete snapshot ${runs[0].runId}` })).toBeDisabled();
  });
});
