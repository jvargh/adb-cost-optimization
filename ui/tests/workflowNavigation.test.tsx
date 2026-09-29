import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { App } from '@/app/App';
import { RunPage } from '@/features/run/RunPage';
import { useConfigStore, useResultsStore, useRunStore } from '@/state';
import { isReviewComplete } from '@/state/resultsStore';
import { getReviewProgress } from '@/features/review/ReviewPage';
import cleanResults from '../mock/fixtures/contoso-clean.results.json';
import defaultConfig from '../mock/fixtures/default-config.json';
import estate from '../mock/fixtures/estate.json';
import type { RunHandle } from '@/api';
import { getBackend } from '@/api';
import type { AssessmentConfig, AssessmentResults, SubscriptionOption } from '@/types';

describe('workflow navigation', () => {
  beforeEach(() => {
    vi.stubGlobal('ResizeObserver', class {
      observe() {}
      unobserve() {}
      disconnect() {}
    });
    window.history.replaceState(null, '', '/');
    useConfigStore.getState().reset();
    useResultsStore.getState().clear();
    useRunStore.getState().reset();
  });
  afterEach(() => { vi.unstubAllGlobals(); window.history.replaceState(null, '', '/'); });

  it('loads configuration outside the Configure screen and enables earlier workflow steps', async () => {
    render(<App />);

    await waitFor(
      () =>
        expect(
          screen.getByRole('button', { name: /Validate.*Pre-flight and approvals/ }),
        ).toBeEnabled(),
      { timeout: 3000 },
    );

    expect(
      screen.getByRole('button', { name: /Run analysis.*Collect and monitor/ }),
    ).toBeEnabled();
    const workflowHeader = screen.getByText('Workflow').parentElement;
    expect(workflowHeader).toHaveClass('sidebar-nav-header');
    expect(screen.queryByText('Highlighted = page you are viewing, not an error.')).not.toBeInTheDocument();
    expect(screen.queryByText('Backend adapter')).not.toBeInTheDocument();
    expect(screen.queryByText('mock-assessment-backend')).not.toBeInTheDocument();
    expect(screen.getByRole('navigation').querySelector('.sidebar-footer')).toBeNull();
  });

  it('marks configuration complete from valid local inputs without requiring backend readiness', async () => {
    await useConfigStore.getState().bootstrap(true);
    render(<App />);
    const configure = screen.getByRole('button', { name: /1 Configure/ });
    expect(configure).not.toHaveClass('done');
    act(() => {
      useConfigStore.getState().toggleSubscription(estate[0].subscriptionId);
    });

    expect(configure).toHaveClass('done');
    expect(configure).toHaveTextContent('Complete');
    expect(screen.getByRole('button', { name: /2 Validate/ })).not.toHaveClass('done');
    act(() => useConfigStore.getState().patch((config) => { config.analysis.endUtc = config.analysis.startUtc; }));
    expect(configure).not.toHaveClass('done');
  });

  it('starts validation from the explicit Configure action but not sidebar navigation', async () => {
    const validate = vi.spyOn(getBackend(), 'validate');
    render(<App />);
    await screen.findByRole('button', { name: 'Validate configuration' });
    fireEvent.click(screen.getByRole('button', { name: /2 Validate/ }));
    expect(screen.getByRole('button', { name: 'Run validation' })).toBeVisible();
    expect(validate).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('checkbox', { name: /^Approve SQL Warehouse auto-start/ }));
    expect(validate).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: /1 Configure/ }));
    fireEvent.click(screen.getByRole('button', { name: 'Validate configuration' }));
    await waitFor(() => expect(useConfigStore.getState().validating).toBe(false));
    expect(validate).toHaveBeenCalledTimes(1);
    validate.mockRestore();
  });

  it('uses numbered completion states for all six steps and never treats the active page as complete', () => {
    useConfigStore.setState({
      config: structuredClone(defaultConfig) as AssessmentConfig,
      estate: structuredClone(estate) as SubscriptionOption[],
    });
    render(<App />);
    const steps = () => Array.from(screen.getByRole('navigation').querySelectorAll('.nav-item'));
    expect(steps().map((step) => step.classList.contains('done'))).toEqual([true, false, false, false, false, false]);
    const ready = { generatedAtUtc: '', checks: [], blockerCount: 0, warningCount: 1, canRun: true, requiresSqlWarehouseApproval: false };
    act(() => useConfigStore.setState({ validation: ready }));
    expect(steps()[1]).toHaveClass('done');
    act(() => useConfigStore.setState({ validating: true }));
    expect(steps()[1]).not.toHaveClass('done');
    act(() => {
      useConfigStore.setState({ validating: false, validation: { ...ready, blockerCount: 1, canRun: false } });
      useRunStore.setState({ phase: 'collecting' });
    });
    expect(steps()[1]).not.toHaveClass('done');
    expect(steps()[2]).not.toHaveClass('done');
    act(() => useRunStore.setState({ phase: 'completed' }));
    expect(steps()[2]).toHaveClass('done');
    act(() => useResultsStore.setState({ results: structuredClone(cleanResults) as AssessmentResults }));
    expect(steps()[3]).toHaveClass('done');
    expect(steps()[4]).not.toHaveClass('done');
    expect(steps()[5]).not.toHaveClass('done');
    const reviewed = structuredClone(cleanResults) as AssessmentResults;
    reviewed.review = reviewed.review.map((entry) => ({ ...entry, decision: 'deferred', reviewer: 'Reviewer' }));
    act(() => {
      useResultsStore.setState({ results: reviewed });
      useResultsStore.getState().markArtifactExported('reports/assessment-report.md');
      useConfigStore.setState({ validation: ready });
    });
    expect(steps().every((step) => step.classList.contains('done'))).toBe(true);
    expect(steps().map((step) => step.querySelector('.nav-step')?.textContent)).toEqual(['1', '2', '3', '4', '5', '6']);
    expect(screen.getByRole('navigation')).not.toHaveTextContent('\u2713');
    for (const phase of ['collecting', 'failed', 'canceled'] as const) {
      act(() => useRunStore.setState({ phase }));
      expect(steps()[2]).not.toHaveClass('done');
    }
  });

  it('marks review complete only when every finding has a decision and reviewer', () => {
    const results = structuredClone(cleanResults) as unknown as AssessmentResults;
    expect(isReviewComplete(results)).toBe(false);

    results.review = results.review.map((entry) => ({
      ...entry,
      decision: entry.decision === 'pending' ? 'deferred' : entry.decision,
      reviewer: entry.reviewer || 'Reviewer',
    }));

    expect(isReviewComplete(results)).toBe(true);
  });

  it('reports missing reviewer names separately from pending decisions', () => {
    const results = structuredClone(cleanResults) as unknown as AssessmentResults;
    const entries = results.review.map((entry) => ({
      ...entry,
      decision: 'accepted' as const,
      reviewer: '',
    }));

    expect(getReviewProgress(entries)).toEqual({
      decisionCount: 3,
      pendingDecisionCount: 0,
      missingReviewerCount: 3,
      complete: false,
    });
  });

  it('does not enable cancellation until the backend run handle exists', () => {
    useConfigStore.setState({
      config: structuredClone(defaultConfig) as AssessmentConfig,
      validation: {
        generatedAtUtc: new Date().toISOString(),
        checks: [],
        blockerCount: 0,
        warningCount: 0,
        canRun: true,
        requiresSqlWarehouseApproval: false,
      },
    });
    useRunStore.setState({ phase: 'preflight', handle: null });
    render(<RunPage onViewResults={() => undefined} />);

    expect(screen.getByRole('button', { name: 'Cancel run' })).toBeDisabled();

    const handle: RunHandle = {
      runId: 'test-run',
      subscribe: () => () => undefined,
      cancel: async () => undefined,
    };
    act(() => useRunStore.setState({ handle }));

    expect(screen.getByRole('button', { name: 'Cancel run' })).toBeEnabled();
  });
});
