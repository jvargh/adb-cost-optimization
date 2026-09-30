import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { App } from '@/app/App';
import { SnapshotPicker } from '@/features/results/SnapshotPicker';
import { getBackend, setBackend } from '@/api';
import { useConfigStore, useResultsStore, useRunStore } from '@/state';
import { EMPTY_FILTERS } from '@/state/resultsStore';
import type { AssessmentResults } from '@/types';
import type { RunEvent as BackendRunEvent } from '@/api/backend';

describe('saved snapshots', () => {
  beforeEach(() => {
    vi.stubGlobal('ResizeObserver', class {
      observe() {}
      unobserve() {}
      disconnect() {}
    });
    setBackend(null);
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    window.history.replaceState(null, '', '/');
    useConfigStore.getState().reset();
    useResultsStore.getState().clear();
    useRunStore.getState().reset();
    useRunStore.setState({ runs: [], runsError: null, loadingRuns: false });
  });
  afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); window.history.replaceState(null, '', '/'); });

  it.each([true, false])('shows a persistent red/green saved outcome instead of gray, needs attention: %s', async (needsAttention) => {
    const backend = getBackend();
    const runs = await backend.listRuns();
    const saved = structuredClone(await backend.loadResults(runs[0].runId));
    saved.manifest.status = needsAttention ? 'partial' : 'passed';
    saved.collection = [
      { ...saved.collection[0], status: needsAttention ? 'partial' : 'passed', limitations: needsAttention ? ['Fixture missing evidence'] : [], error: '' },
      { ...saved.collection[0], name: 'Optional source', status: 'skipped', limitations: ['Not selected'], error: '' },
    ];
    vi.spyOn(backend, 'loadResults').mockResolvedValue(saved);
    const validate = vi.spyOn(backend, 'validate');
    const start = vi.spyOn(backend, 'startRun');
    window.history.replaceState(null, '', `/?run=${runs[0].runId}`);
    const rendered = render(<App />);
    await screen.findByText('Viewing a saved snapshot');
    const expected = needsAttention ? 'attention' : 'done';
    expect(screen.getByRole('button', { name: /2 Validate/ })).toHaveClass(expected);
    expect(screen.getByRole('button', { name: /3 Run analysis/ })).toHaveClass(expected);
    fireEvent.click(screen.getByRole('button', { name: /2 Validate/ }));
    expect(screen.getByText(/^Assessment completed -/).closest('.callout')).toHaveClass(needsAttention ? 'callout-danger' : 'callout-ok');
    expect(screen.getByText('Not selected')).toBeVisible();
    rendered.unmount();
    useResultsStore.getState().clear();
    render(<App />);
    await screen.findByText('Viewing a saved snapshot');
    expect(screen.getByRole('button', { name: /2 Validate/ })).toHaveClass(expected);
    expect(validate).not.toHaveBeenCalled();
    expect(start).not.toHaveBeenCalled();
  });

  it('reopens a saved snapshot on reload without discovery, validation, or collection', async () => {
    const backend = getBackend();
    const runs = await backend.listRuns();
    const discover = vi.spyOn(backend, 'discoverEstate');
    const validate = vi.spyOn(backend, 'validate');
    const start = vi.spyOn(backend, 'startRun');
    window.history.replaceState(null, '', `/?run=${runs[0].runId}`);
    const rendered = render(<App />);
    await screen.findByText('Viewing a saved snapshot');
    expect(useResultsStore.getState().runId).toBe(runs[0].runId);
    const picker = screen.getByRole('combobox', { name: 'Saved snapshots' });
    expect(picker.closest('.topbar-controls')).toBe(screen.getByRole('button', { name: /Switch to .* mode/ }).closest('.topbar-controls'));
    expect(screen.getByRole('navigation')).not.toHaveTextContent('Saved snapshots');
    expect(screen.queryByRole('textbox', { name: 'Find a saved snapshot' })).not.toBeInTheDocument();
    fireEvent.change(picker, { target: { value: runs[1].runId } });
    await screen.findByText('Viewing a saved snapshot');
    expect(new URLSearchParams(window.location.search).get('run')).toBe(runs[1].runId);
    rendered.unmount();
    useResultsStore.getState().clear();
    render(<App />);
    await screen.findByText('Viewing a saved snapshot');
    expect(useResultsStore.getState().runId).toBe(runs[1].runId);
    expect(screen.getByRole('combobox', { name: 'Saved snapshots' })).toHaveValue(runs[1].runId);
    expect(discover).not.toHaveBeenCalled();
    expect(validate).not.toHaveBeenCalled();
    expect(start).not.toHaveBeenCalled();
  });

  it('shows list errors and retries without starting an assessment', async () => {
    const backend = getBackend();
    vi.spyOn(backend, 'listRuns').mockRejectedValueOnce(new Error('Disk unavailable')).mockResolvedValue([]);
    await useRunStore.getState().refreshRuns();
    render(<SnapshotPicker onOpen={() => undefined} />);
    expect(screen.getByRole('alert')).toHaveTextContent('Disk unavailable');
    fireEvent.click(screen.getByRole('button', { name: 'Retry snapshots' }));
    await screen.findByRole('option', { name: 'No saved snapshots yet' });
  });

  it('keeps snapshot workflow pages historical without loading or validating a live setup', async () => {
    const backend = getBackend();
    const runs = await backend.listRuns();
    const discover = vi.spyOn(backend, 'discoverEstate');
    const config = vi.spyOn(backend, 'loadDefaultConfig');
    const validate = vi.spyOn(backend, 'validate');
    const start = vi.spyOn(backend, 'startRun');
    const preview = vi.spyOn(backend, 'previewPermissionSetup');
    const apply = vi.spyOn(backend, 'applyPermissionSetup');
    window.history.replaceState(null, '', `/?run=${runs[0].runId}`);
    render(<App />);
    await screen.findByText('Viewing a saved snapshot');
    for (const step of [/1 Configure/, /2 Validate/, /3 Run analysis/]) {
      fireEvent.click(screen.getByRole('button', { name: step }));
      await screen.findByText(/Assessment completed - (evidence needs attention|collected checks passed)/);
      expect(screen.getByRole('heading', { name: 'Saved collection checks' })).toBeVisible();
      expect(screen.queryByRole('button', { name: 'Start read-only assessment' })).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: 'Run validation' })).not.toBeInTheDocument();
      expect(screen.queryByText('Pipeline timeline permission setup')).not.toBeInTheDocument();
    }
    expect(discover).not.toHaveBeenCalled();
    expect(config).not.toHaveBeenCalled();
    expect(validate).not.toHaveBeenCalled();
    expect(start).not.toHaveBeenCalled();
    expect(preview).not.toHaveBeenCalled();
    expect(apply).not.toHaveBeenCalled();
  });

  it('does not show current-setup validation as belonging to a selected snapshot', async () => {
    const backend = getBackend();
    const runs = await backend.listRuns();
    useConfigStore.setState({
      config: await backend.loadDefaultConfig(),
      validation: { generatedAtUtc: '', checks: [], blockerCount: 0, warningCount: 0, canRun: true, requiresSqlWarehouseApproval: false },
    });
    const validate = vi.spyOn(backend, 'validate');
    render(<App />);
    await screen.findByRole('option', { name: new RegExp(runs[0].runId) });
    fireEvent.change(screen.getByRole('combobox', { name: 'Saved snapshots' }), { target: { value: runs[0].runId } });
    await screen.findByText('Viewing a saved snapshot');
    expect(screen.queryByText('Validation finished - analysis has not started')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /2 Validate/ })).toHaveTextContent(/Saved checks (need attention|passed)/);
    fireEvent.click(screen.getByRole('button', { name: /2 Validate/ }));
    await screen.findByText(/Assessment completed - (evidence needs attention|collected checks passed)/);
    expect(validate).not.toHaveBeenCalled();
  });

  it('starts fresh at Configure, stays fresh on reload, and preserves saved snapshots', async () => {
    const backend = getBackend();
    const runs = await backend.listRuns();
    const config = await backend.loadDefaultConfig();
    vi.spyOn(backend, 'discoverEstate').mockResolvedValue([]);
    vi.spyOn(backend, 'loadDefaultConfig').mockResolvedValue(config);
    const load = vi.spyOn(backend, 'loadResults');
    const validate = vi.spyOn(backend, 'validate');
    const start = vi.spyOn(backend, 'startRun');
    const save = vi.spyOn(backend, 'saveReview');
    useConfigStore.setState({
      config, dirty: true,
      approvals: { approveSqlWarehouseAutoStart: true, continueOnCollectorError: false, acknowledgedReadOnly: false },
      validation: { generatedAtUtc: '', checks: [], blockerCount: 0, warningCount: 0, canRun: true, requiresSqlWarehouseApproval: false },
      validationProgress: {
        validationId: 'prior-validation', status: 'completed', steps: [],
        startedAtUtc: '2026-09-01T00:00:00Z', finishedAtUtc: '2026-09-01T01:00:00Z',
        lastActivityAtUtc: '2026-09-01T01:00:00Z', message: 'Previous validation finished',
      },
      validationStartedAtUtc: '2026-09-01T00:00:00Z',
      validationLastResponseAtUtc: '2026-09-01T01:00:00Z',
    });

    useRunStore.setState({
      phase: 'completed', runId: runs[0].runId, error: 'Prior warning',
      console: [{ level: 'info', message: 'Prior run', atUtc: '' }],
    });
    window.history.replaceState(null, '', `/?mock=1&run=${runs[0].runId}`);
    const rendered = render(<App />);
    await screen.findByText('Viewing a saved snapshot');
    act(() => {
      useResultsStore.getState().setFilter('search', 'prior filter');
      useResultsStore.getState().markArtifactExported('reports/assessment-report.md');
    });
    fireEvent.click(screen.getByRole('button', { name: /5 Review & export/ }));
    fireEvent.click(screen.getByRole('button', { name: 'New assessment' }));
    await screen.findByText('Scope determines everything downstream');
    const firstCustomerId = useConfigStore.getState().config!.customerId;
    expect(firstCustomerId).toMatch(/^customer-[0-9a-f]{8}$/);
    expect(screen.getByLabelText('Customer ID', { exact: false })).toHaveValue(firstCustomerId);
    expect(useConfigStore.getState().config?.assessmentId).toMatch(/^assessment-[0-9a-f]{8}$/);
    expect(screen.getByText('Select resource groups to list their Azure Databricks workspaces.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /1 Configure/ })).toHaveAttribute('aria-current', 'step');
    expect(useResultsStore.getState()).toMatchObject({
      runId: null, results: null, loading: false, error: null, filters: EMPTY_FILTERS,
      selectedFinding: null, exportedArtifactPaths: [],
    });
    expect(useRunStore.getState()).toMatchObject({
      phase: 'idle', runId: null, console: [], sources: [], error: null, handle: null,
    });
    expect(useConfigStore.getState()).toMatchObject({
      validation: null, validationProgress: null, validationError: null,
      validationStartedAtUtc: null, validationLastResponseAtUtc: null,
      approvals: { approveSqlWarehouseAutoStart: false, continueOnCollectorError: true, acknowledgedReadOnly: true },
      config: { azure: { subscriptions: [], resourceGroups: [], costScope: '' }, databricks: { workspaces: [] } },
    });
    expect(new URLSearchParams(window.location.search).get('run')).toBeNull();
    expect(new URLSearchParams(window.location.search).get('new')).toBe('1');
    expect(new URLSearchParams(window.location.search).get('mock')).toBe('1');
    expect(screen.getByRole('combobox', { name: 'Saved snapshots' })).toHaveValue('');
    expect(useRunStore.getState().runs).toHaveLength(runs.length);
    rendered.unmount();
    useConfigStore.getState().reset();
    useResultsStore.getState().clear();
    useRunStore.getState().reset();
    render(<App />);
    await screen.findByText('Scope determines everything downstream');
    expect(useConfigStore.getState().config?.customerId).toMatch(/^customer-[0-9a-f]{8}$/);
    expect(useConfigStore.getState().config?.customerId).not.toBe(firstCustomerId);
    expect(screen.getByRole('button', { name: /1 Configure/ })).toHaveAttribute('aria-current', 'step');
    expect(load).toHaveBeenCalledTimes(1);
    expect(validate).not.toHaveBeenCalled();
    expect(start).not.toHaveBeenCalled();
    expect(save).not.toHaveBeenCalled();
    fireEvent.change(screen.getByRole('combobox', { name: 'Saved snapshots' }), { target: { value: runs[0].runId } });
    await screen.findByText('Viewing a saved snapshot');
    expect(new URLSearchParams(window.location.search).get('new')).toBeNull();
    expect(new URLSearchParams(window.location.search).get('run')).toBe(runs[0].runId);
  });

  it('does not reset while discovery, sign-in, validation, or collection is active', async () => {
    const runs = await getBackend().listRuns();
    window.history.replaceState(null, '', `/?run=${runs[0].runId}`);
    render(<App />);
    await screen.findByText('Viewing a saved snapshot');
    const button = screen.getByRole('button', { name: 'New assessment' });
    for (const key of ['loading', 'signingIn', 'validating'] as const) {
      act(() => useConfigStore.setState({ [key]: true }));
      expect(button).toBeDisabled();
      fireEvent.click(button);
      expect(useResultsStore.getState().runId).toBe(runs[0].runId);
      act(() => useConfigStore.setState({ [key]: false }));
    }
    act(() => useRunStore.setState({ phase: 'collecting' }));
    expect(button).toBeDisabled();
    fireEvent.click(button);
    expect(useRunStore.getState().phase).toBe('collecting');
    expect(new URLSearchParams(window.location.search).get('run')).toBe(runs[0].runId);
  });

  it('discards a snapshot response that arrives after New assessment', async () => {
    const backend = getBackend();
    const runs = await backend.listRuns();
    const result = await backend.loadResults(runs[0].runId);
    let finish!: (value: AssessmentResults) => void;
    vi.spyOn(backend, 'loadResults').mockImplementation(() => new Promise((resolve) => { finish = resolve; }));
    vi.spyOn(backend, 'discoverEstate').mockResolvedValue([]);
    window.history.replaceState(null, '', `/?run=${runs[0].runId}`);
    render(<App />);
    fireEvent.click(screen.getByRole('button', { name: 'New assessment' }));
    await screen.findByText('Scope determines everything downstream');
    await act(async () => finish(result));
    expect(useResultsStore.getState().results).toBeNull();
    expect(useResultsStore.getState().runId).toBeNull();
    expect(screen.queryByText('Viewing a saved snapshot')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /1 Configure/ })).toHaveAttribute('aria-current', 'step');
  });

  it('lists every recorded snapshot by collection timestamp, newest first', async () => {
    const template = (await getBackend().listRuns())[0];
    const runs = [
      { ...template, runId: 'oldest', startedAtUtc: '2026-09-01T00:00:00Z' },
      { ...template, runId: 'middle', startedAtUtc: '2026-09-02T01:30:00+02:00' },
      { ...template, runId: 'newest', startedAtUtc: '2026-09-02T00:00:00Z' },
    ];
    useRunStore.setState({ runs });
    const open = vi.fn();
    render(<SnapshotPicker onOpen={open} />);
    const options = screen.getAllByRole('option').slice(1);
    expect(options.map((option) => option.getAttribute('value'))).toEqual(['newest', 'middle', 'oldest']);
    expect(options[0]).toHaveTextContent('2026-09-02 00:00:00 UTC');
    expect(useRunStore.getState().runs.map((run) => run.runId)).toEqual(['oldest', 'middle', 'newest']);
    fireEvent.change(screen.getByRole('combobox', { name: 'Saved snapshots' }), { target: { value: 'oldest' } });
    expect(open).toHaveBeenCalledWith('oldest');
  });

  it('loads fresh recorded snapshots on dropdown focus', async () => {
    const backend = getBackend();
    const runs = await backend.listRuns();
    const list = vi.spyOn(backend, 'listRuns').mockResolvedValue(runs);
    render(<SnapshotPicker onOpen={() => undefined} />);
    fireEvent.focus(screen.getByRole('combobox', { name: 'Saved snapshots' }));
    await waitFor(() => expect(screen.getAllByRole('option')).toHaveLength(runs.length + 1));
    expect(list).toHaveBeenCalledTimes(1);
  });

  it('does not let a slow earlier snapshot overwrite the current selection', async () => {
    const backend = getBackend();
    const runs = await backend.listRuns();
    const first = await backend.loadResults(runs[0].runId);
    const second = await backend.loadResults(runs[1].runId);
    let resolveFirst!: (value: AssessmentResults) => void;
    vi.spyOn(backend, 'loadResults')
      .mockImplementationOnce(() => new Promise((resolve) => { resolveFirst = resolve; }))
      .mockResolvedValueOnce(second);
    const pending = useResultsStore.getState().load(first.manifest.runId);
    await useResultsStore.getState().load(second.manifest.runId);
    resolveFirst(first);
    await pending;
    expect(useResultsStore.getState().results?.manifest.runId).toBe(second.manifest.runId);
    expect(useResultsStore.getState().selectedFinding).toBeNull();
  });

  it('refreshes snapshots when a collection finishes', async () => {
    const backend = getBackend();
    const config = await backend.loadDefaultConfig();
    useConfigStore.setState({ config, validation: { generatedAtUtc: '', checks: [], blockerCount: 0, warningCount: 0, canRun: true, requiresSqlWarehouseApproval: false } });
    let listener!: (event: BackendRunEvent) => void;
    vi.spyOn(backend, 'startRun').mockResolvedValue({
      runId: 'new-run', cancel: async () => undefined,
      subscribe: (next) => { listener = next; return () => undefined; },
    });
    const refresh = vi.spyOn(backend, 'listRuns').mockResolvedValue([]);
    await useRunStore.getState().start();
    act(() => listener({ type: 'completed', runId: 'new-run', atUtc: new Date().toISOString() }));
    await waitFor(() => expect(refresh).toHaveBeenCalledTimes(1));
  });
});
