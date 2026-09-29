import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { App } from '@/app/App';
import { setBackend } from '@/api';
import { MockAssessmentBackend } from '@/api/mockBackend';
import { ValidatePage } from '@/features/validate/ValidatePage';
import { ValidationProgressPanel } from '@/features/validate/ValidationProgressPanel';
import { summarizeValidationProgress } from '@/lib/validationProgress';
import { useConfigStore, useResultsStore, useRunStore } from '@/state';
import type { AssessmentConfig, SubscriptionOption, ValidationProgress } from '@/types';
import defaultConfig from '../mock/fixtures/default-config.json';
import estate from '../mock/fixtures/estate.json';

const start = '2026-09-27T12:00:00Z';
const progress: ValidationProgress = {
  validationId: 'test-validation', status: 'running', startedAtUtc: start, finishedAtUtc: null,
  lastActivityAtUtc: start, message: 'Waiting for Azure costs.',
  steps: [
    { id: 'scope', title: 'Scope', status: 'pass', detail: 'Scope checked.', startedAtUtc: start, finishedAtUtc: start, estimatedSeconds: 5 },
    { id: 'cost', title: 'Azure costs', status: 'running', detail: 'Reading costs.', startedAtUtc: start, finishedAtUtc: null, estimatedSeconds: 60 },
    { id: 'sql', title: 'SQL evidence', status: 'pending', detail: 'Waiting.', startedAtUtc: null, finishedAtUtc: null, estimatedSeconds: 30 },
  ],
};

beforeEach(() => {
  useConfigStore.getState().reset();
  useRunStore.getState().reset();
  useResultsStore.getState().clear();
  useConfigStore.setState({
    config: structuredClone(defaultConfig) as AssessmentConfig,
    estate: structuredClone(estate) as SubscriptionOption[],
  });
});
afterEach(() => { vi.useRealTimers(); setBackend(null); });

it('counts only finished checks, including warnings, rather than estimating completion', () => {
  const state = structuredClone(progress);
  state.steps[0].status = 'warn';
  expect(summarizeValidationProgress(state, Date.parse(start) + 10000)).toMatchObject({
    completed: 1, total: 3, percent: 33, overdue: false, eta: { min: 1, max: 2 },
  });
});

it('distinguishes not-applicable checks and makes fixes visible in the progress list', () => {
    const state = structuredClone(progress);
    state.status = 'completed';
    state.steps[0].status = 'not-applicable';
    state.steps[1].status = 'warn';
    state.steps[1].issues = [{
      title: 'Pipeline timeline SELECT access is missing', detail: 'Selected evidence was denied.',
      remediation: 'Ask the system-table administrator for SELECT access.',
      evidence: [{ source: 'Pipeline timeline', detail: 'INSUFFICIENT_PERMISSIONS' }],
    }];
    useConfigStore.setState({ validationProgress: state, validating: false });
    render(<ValidationProgressPanel />);
    expect(screen.getByText('Not applicable', { exact: true })).toBeInTheDocument();
    expect(screen.getByText('Ask the system-table administrator for SELECT access.')).toBeVisible();
    expect(screen.getByText('INSUFFICIENT_PERMISSIONS')).not.toBeVisible();
    fireEvent.click(screen.getByText('Source details (1)'));
    expect(screen.getByText('INSUFFICIENT_PERMISSIONS')).toBeVisible();
});

it('does not promise a zero ETA when a check takes longer than estimated', () => {
  expect(summarizeValidationProgress(progress, Date.parse(start) + 91000)).toMatchObject({
    completed: 1, overdue: true, eta: null,
  });
});

it('updates elapsed time without inventing progress and explains a slow check', () => {
  vi.useFakeTimers();
  vi.setSystemTime(Date.parse(start));
  useConfigStore.setState({ validating: true, validationProgress: progress, validationStartedAtUtc: start, validationLastResponseAtUtc: start });
  render(<ValidationProgressPanel />);
  expect(screen.getByText('1/3 checks completed')).toBeInTheDocument();
  expect(screen.getByRole('progressbar')).toHaveAttribute('value', '1');
  expect(screen.getByText('Elapsed: 0s')).toBeInTheDocument();
  act(() => vi.advanceTimersByTime(92000));
  expect(screen.getByText('Elapsed: 1m 32s')).toBeInTheDocument();
  expect(screen.getByText('1/3 checks completed')).toBeInTheDocument();
  expect(screen.getByText('Waiting for this check to return')).toBeInTheDocument();
  expect(screen.getByText(/Unknown - this check/)).toBeInTheDocument();
});

it('keeps validation visible across Configure, Run, and Visualize without starting again', () => {
  useConfigStore.setState({ validating: true, validationProgress: progress, validationStartedAtUtc: start });
  render(<App />);
  expect(screen.getByText('1/3 checks completed')).toBeInTheDocument();
  const content = screen.getByRole('main').querySelector('.content');
  if (!content) throw new Error('Workflow scroll container is missing.');
  content.scrollTop = 900;
  fireEvent.click(screen.getByRole('button', { name: /Run analysis.*Collect and monitor/ }));
  expect(content.scrollTop).toBe(0);
  expect(screen.getByText('Analysis has not started - validation is still running')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Start read-only assessment' })).toBeDisabled();
  fireEvent.click(screen.getByRole('button', { name: /Visualize results.*Executive and technical/ }));
  expect(screen.getByText('No new results yet - validation is still running')).toBeInTheDocument();
  expect(screen.getByText('1/3 checks completed')).toBeInTheDocument();
});

describe('validation errors and stale results', () => {
  it('confirms a rerun, preserving the report and Continue action when canceled', async () => {
    const backend = new MockAssessmentBackend();
    setBackend(backend);
    const report = { generatedAtUtc: start, checks: [], blockerCount: 0, warningCount: 0, canRun: true, requiresSqlWarehouseApproval: false };
    useConfigStore.setState({ validation: report, approvals: { approveSqlWarehouseAutoStart: true, continueOnCollectorError: true, acknowledgedReadOnly: true } });
    const validate = vi.spyOn(backend, 'validate').mockResolvedValue(report);
    const confirmation = vi.spyOn(window, 'confirm').mockReturnValue(false);
    const continueToRun = vi.fn();
    render(<ValidatePage onRun={continueToRun} />);
    try {
      fireEvent.click(screen.getByRole('button', { name: 'Re-run validation' }));
      expect(confirmation).toHaveBeenCalledWith(expect.stringContaining('from the beginning'));
      expect(validate).not.toHaveBeenCalled();
      expect(useConfigStore.getState().validation).toBe(report);
      fireEvent.click(screen.getByRole('button', { name: 'Continue to run' }));
      expect(continueToRun).toHaveBeenCalledOnce();
      expect(validate).not.toHaveBeenCalled();
      confirmation.mockReturnValue(true);
      fireEvent.click(screen.getByRole('button', { name: 'Re-run validation' }));
      await waitFor(() => expect(validate).toHaveBeenCalledOnce());
      await waitFor(() => expect(useConfigStore.getState().validating).toBe(false));
    } finally {
      confirmation.mockRestore();
    }
  });

  it('validates only on an explicit action, not page mount or approval changes', async () => {
    const backend = new MockAssessmentBackend();
    const validate = vi.spyOn(backend, 'validate');
    setBackend(backend);
    render(<ValidatePage onRun={() => undefined} />);
    expect(validate).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Run validation' }));
    await waitFor(() => expect(useConfigStore.getState().validating).toBe(false));
    expect(validate).toHaveBeenCalledTimes(1);
    act(() => useConfigStore.getState().setApproval('continueOnCollectorError', false));
    expect(screen.getByRole('button', { name: 'Run validation' })).toBeEnabled();
    expect(validate).toHaveBeenCalledTimes(1);
  });

  it('reports missing IDs and dates immediately without a backend request, then validates corrected inputs', async () => {
    const backend = new MockAssessmentBackend();
    const validate = vi.spyOn(backend, 'validate');
    setBackend(backend);
    useConfigStore.getState().patch((config) => {
      config.customerId = '';
      config.assessmentId = '';
      config.analysis.startUtc = '';
      config.analysis.endUtc = '';
    });
    const back = vi.fn();
    render(<ValidatePage onRun={() => undefined} onConfigure={back} />);
    fireEvent.click(screen.getByRole('button', { name: 'Run validation' }));
    await screen.findByText('3 items must be fixed before the run');
    expect(screen.getAllByText('Customer ID is blank.').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Assessment ID is blank.').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Start (UTC) and End (UTC) must both contain valid dates.').length).toBeGreaterThan(0);
    expect(validate).not.toHaveBeenCalled();
    expect(useConfigStore.getState()).toMatchObject({
      validating: false, validationError: null, validationProgress: null,
    });
    expect(screen.getByRole('button', { name: 'Continue to run' })).toBeDisabled();
    expect(screen.queryByRole('button', { name: 'Retry validation' })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Back to Configure' }));
    expect(back).toHaveBeenCalledTimes(1);
    act(() => useConfigStore.getState().patch((config) => {
      config.customerId = defaultConfig.customerId;
      config.assessmentId = defaultConfig.assessmentId;
      config.analysis = structuredClone(defaultConfig.analysis);
    }));
    expect(validate).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Run validation' }));
    await waitFor(() => expect(validate).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(useConfigStore.getState().validating).toBe(false));
    expect(useConfigStore.getState().validationError).toBeNull();
  });

  it('does not leave a finished, early failure showing Preparing the check list', () => {
    useConfigStore.setState({
      validationProgress: { ...progress, status: 'completed', finishedAtUtc: start, steps: [] },
      validating: false,
    });
    render(<ValidationProgressPanel />);
    expect(screen.getByText('Source checks did not start')).toBeInTheDocument();
    expect(screen.getByText('No source checks ran')).toBeInTheDocument();
    expect(screen.queryByText('Preparing the check list')).not.toBeInTheDocument();
  });

  it('shows a failure once and retries only when requested', async () => {
    const backend = new MockAssessmentBackend();
    const validate = vi.spyOn(backend, 'validate').mockRejectedValue(new Error('Local server is offline.'));
    setBackend(backend);
    render(<ValidatePage onRun={() => undefined} />);
    fireEvent.click(screen.getByRole('button', { name: 'Run validation' }));
    await screen.findByText('Local server is offline.');
    expect(validate).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole('button', { name: 'Retry validation' }));
    await waitFor(() => expect(validate).toHaveBeenCalledTimes(2));
    await screen.findByText('Local server is offline.');
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
  });

  it('does not apply the old validation report after the scope changes', async () => {
    const backend = new MockAssessmentBackend();
    setBackend(backend);
    const validating = useConfigStore.getState().validate();
    useConfigStore.getState().patch((config) => { config.customerId = 'changed'; });
    await expect(validating).rejects.toThrow('Configuration changed');
    expect(useConfigStore.getState().validation).toBeNull();
    expect(useConfigStore.getState().validating).toBe(false);
  });

  it('does not let an old request alter a reset workflow', async () => {
    setBackend(new MockAssessmentBackend());
    const validating = useConfigStore.getState().validate();
    useConfigStore.getState().reset();
    await validating;
    expect(useConfigStore.getState().validation).toBeNull();
    expect(useConfigStore.getState().validationProgress).toBeNull();
  });
});
