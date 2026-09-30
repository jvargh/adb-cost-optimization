import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Badge, Callout, ErrorBoundary, GuardrailStrip, MockBanner, Panel, ThemeToggle } from '@/components';
import { ConfigurePage } from '@/features/configure/ConfigurePage';
import { ValidatePage } from '@/features/validate/ValidatePage';
import { ValidationActions } from '@/features/validate/ValidationActions';
import { EvidenceImport } from '@/features/configure/EvidenceImport';
import { PermissionSetupPanel } from '@/features/validate/PermissionSetupPanel';
import { usePermissionStore } from '@/state/permissionStore';
import { ValidationProgressPanel } from '@/features/validate/ValidationProgressPanel';
import { summarizeValidationProgress } from '@/lib/validationProgress';
import { validateConfiguration } from '@/lib/validation';
import { RunPage } from '@/features/run/RunPage';
import { ResultsPage } from '@/features/results/ResultsPage';
import { SnapshotPicker } from '@/features/results/SnapshotPicker';
import { SnapshotSummary } from '@/features/results/SnapshotSummary';
import { getCollectionOutcome } from '@/features/results/CollectionOutcome';
import { SnapshotHistory } from '@/features/results/SnapshotHistory';
import { ExportPage } from '@/features/export/ExportPage';
import { useConfigStore, useResultsStore, useRunStore } from '@/state';
import { getBackend, setActiveScenario, activeScenarioId } from '@/api';
import scenarios from '../../mock/fixtures/scenarios.json';

type StepId = 'configure' | 'validate' | 'run' | 'results' | 'export';

const STEPS: { id: StepId; label: string; caption: string }[] = [
  { id: 'configure', label: 'Configure', caption: 'Scope, window, and safety' },
  { id: 'validate', label: 'Validate', caption: 'Pre-flight and approvals' },
  { id: 'run', label: 'Run analysis', caption: 'Collect and monitor' },
  { id: 'results', label: 'Visualize results', caption: 'Executive and technical' },
  { id: 'export', label: 'Review & export', caption: 'Downloads and optional review' },
];

export function App() {
  const freshAssessment = new URLSearchParams(window.location.search).get('new') === '1';
  const [importMode, setImportMode] = useState(() => new URLSearchParams(window.location.search).get('import') === '1');
  const [initialRunId] = useState(() => freshAssessment ? null : new URLSearchParams(window.location.search).get('run'));
  const [step, setStep] = useState<StepId>(initialRunId ? 'results' : 'configure');
  const contentRef = useRef<HTMLDivElement>(null);
  const [scenarioPickerOpen, setScenarioPickerOpen] = useState(false);
  const [scenario, setScenario] = useState(activeScenarioId);

  const config = useConfigStore((s) => s.config);
  const configLoading = useConfigStore((s) => s.loading);
  const configError = useConfigStore((s) => s.error);
  const estate = useConfigStore((s) => s.estate);
  const approvals = useConfigStore((s) => s.approvals);
  const signingIn = useConfigStore((s) => s.signingIn);
  const permissionBusy = usePermissionStore((s) => s.busy);
  const bootstrapConfig = useConfigStore((s) => s.bootstrap);
  const validation = useConfigStore((s) => s.validation);
  const validating = useConfigStore((s) => s.validating);
  const validationProgress = useConfigStore((s) => s.validationProgress);
  const validationError = useConfigStore((s) => s.validationError);
  const runPhase = useRunStore((s) => s.phase);
  const runSources = useRunStore((s) => s.sources);
  const refreshRuns = useRunStore((s) => s.refreshRuns);
  const loadResults = useResultsStore((s) => s.load);
  const results = useResultsStore((s) => s.results);
  const resultsError = useResultsStore((s) => s.error);
  const selectedRunId = useResultsStore((s) => s.runId);
  const snapshotMode = Boolean(selectedRunId);
  const exportedArtifactPaths = useResultsStore((s) => s.exportedArtifactPaths);
  const backend = getBackend();

  useEffect(() => {
    if (contentRef.current) contentRef.current.scrollTop = 0;
  }, [step]);

  useEffect(() => {
    void refreshRuns();
  }, [refreshRuns]);

  useEffect(() => {
    if (!importMode && !snapshotMode && ['configure', 'validate', 'run'].includes(step) && !config && !configLoading && !configError) void bootstrapConfig(freshAssessment);
  }, [bootstrapConfig, config, configLoading, configError, freshAssessment, snapshotMode, step, importMode]);

  const openResults = useCallback(
    (runId: string) => {
      const url = new URL(window.location.href);
      url.searchParams.delete('new');
      url.searchParams.delete('import');
      url.searchParams.set('run', runId);
      window.history.replaceState(null, '', url);
      void loadResults(runId);
      void refreshRuns();
      setImportMode(false);
      setStep('results');
    },
    [loadResults, refreshRuns],
  );

  useEffect(() => {
    if (initialRunId) openResults(initialRunId);
  }, [initialRunId, openResults]);

  const configurationComplete = useMemo(() => {
    if (!config || configLoading || configError) return false;
    const report = validateConfiguration({ config, approvals, estate, environmentChecks: [] });
    return !report.checks.some((check) =>
      check.id !== 'sql-warehouse-approval' && check.severity === 'blocker' && check.status === 'fail',
    );
  }, [config, configLoading, configError, approvals, estate]);

  const collectionOutcome = results ? getCollectionOutcome(results) : null;
  const liveCollectionOutcome = getCollectionOutcome({ manifest: { status: 'passed' }, collection: runSources });
  const stepState = (id: StepId): 'done' | 'attention' | 'available' | 'disabled' => {
    switch (id) {
      case 'configure':
        if (snapshotMode) return results ? 'done' : 'available';
        return configurationComplete ? 'done' : 'available';
      case 'validate':
        if (snapshotMode) return resultsError ? 'attention' : collectionOutcome ? collectionOutcome.needsAttention ? 'attention' : 'done' : 'available';
        if (!validating && (validationError || (validation && !validation.canRun))) return 'attention';
        return !validating && !validationError && validation?.canRun ? 'done' : config ? 'available' : 'disabled';
      case 'run':
        if (snapshotMode) return resultsError ? 'attention' : collectionOutcome ? collectionOutcome.needsAttention ? 'attention' : 'done' : 'available';
        if (runPhase === 'failed' || runPhase === 'canceled') return 'attention';
        if (runPhase === 'completed') return liveCollectionOutcome.needsAttention ? 'attention' : 'done';
        if (runPhase === 'idle' && collectionOutcome) return collectionOutcome.needsAttention ? 'attention' : 'done';
        return config ? 'available' : 'disabled';
      case 'results':
        return results ? 'done' : 'available';
      case 'export':
        return exportedArtifactPaths.length > 0 ? 'done' : results ? 'available' : 'disabled';
      default:
        return results ? 'available' : 'disabled';
    }
  };

  const activeScenario = (scenarios as { id: string; label: string; description: string }[]).find(
    (s) => s.id === scenario,
  );
  const runActive = !['idle', 'completed', 'failed', 'canceled'].includes(runPhase);
  const resetBlocked = runActive || validating || configLoading || signingIn || permissionBusy;
  const openLiveStep = (next: StepId) => {
    const url = new URL(window.location.href);
    url.searchParams.delete('run');
    window.history.replaceState(null, '', url);
    useResultsStore.getState().clear();
    setStep(next);
  };
  const startValidation = () => {
    setStep('validate');
    if (!useConfigStore.getState().validation) {
      void useConfigStore.getState().validate().catch(() => undefined);
    }
  };
  const snapshotsDeleted = (runIds: string[]) => {
    const currentRunId = useRunStore.getState().runId;
    if (currentRunId && runIds.includes(currentRunId)) useRunStore.getState().reset();
    const currentSnapshot = useResultsStore.getState().runId;
    if (currentSnapshot && runIds.includes(currentSnapshot)) {
      const url = new URL(window.location.href);
      url.searchParams.delete('run');
      window.history.replaceState(null, '', url);
      useResultsStore.getState().clear();
      useConfigStore.getState().resetValidation();
      setStep('results');
    }
  };
  const newAssessment = () => {
    if (!window.confirm('Start a new assessment setup? Unsaved setup and review edits will be discarded. Saved snapshots are kept.')) return;
    const url = new URL(window.location.href);
    url.searchParams.delete('run');
    url.searchParams.delete('import');
    setImportMode(false);
    url.searchParams.set('new', '1');
    window.history.replaceState(null, '', url);
    useRunStore.getState().reset();
    useResultsStore.getState().clear();
    useConfigStore.getState().reset();
    usePermissionStore.getState().clear();
    setScenarioPickerOpen(false);
    setStep('configure');
    if (contentRef.current) contentRef.current.scrollTop = 0;
  };
  const progressCount = validationProgress ? summarizeValidationProgress(validationProgress, Date.now()) : null;
  const statusLabel = (id: StepId): string => {
    if (snapshotMode) {
      if (id === 'configure') return 'Saved scope';
      if (id === 'validate') return resultsError ? 'Saved checks unavailable' : collectionOutcome
        ? collectionOutcome.needsAttention ? 'Saved checks need attention' : 'Saved checks passed'
        : 'Loading saved checks';
      if (id === 'run') return results ? `Saved run - ${results.manifest.status}` : 'Loading snapshot';
    }
    switch (id) {
      case 'configure': return configLoading ? 'Loading' : configError ? 'Needs attention'
        : configurationComplete ? 'Complete' : config ? 'Needs configuration'
        : 'Not configured';
      case 'validate': return validating
        ? `Running${progressCount?.total ? ` - ${progressCount.completed}/${progressCount.total}` : ''}`
        : validationError ? 'Stopped - needs attention'
        : validation ? validation.canRun ? `Ready${validation.warningCount ? ' with warnings' : ''}` : 'Blocked'
        : 'Not checked';
      case 'run': return runActive ? 'Running' : runPhase === 'completed' ? liveCollectionOutcome.needsAttention ? 'Finished - needs attention' : 'Finished - checks passed'
        : runPhase === 'failed' ? 'Failed' : runPhase === 'canceled' ? 'Canceled'
        : validating ? 'Waiting for validation' : results ? 'Saved run available' : 'Not started';
      case 'results': return results ? 'Saved results open' : 'No results open';
      case 'export': return exportedArtifactPaths.length ? 'Downloaded' : results ? 'Ready to export' : 'Needs results';
    }
  };

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <span className="sidebar-brand-title">Azure Databricks Cost Assessment</span>
          <span className="sidebar-brand-sub">Read-only assessment</span>
        </div>
        <nav className="sidebar-nav">
          <div className="sidebar-nav-header">
            <span className="sidebar-section-label">Workflow</span>
          </div>
          {STEPS.map((item, index) => {
            const state = stepState(item.id);
            const classes = ['nav-item'];
            if (item.id === step) classes.push('active');
            if (state === 'done') classes.push('done');
            if (state === 'attention') classes.push('attention');
            if (state === 'disabled') classes.push('disabled');
            return (
              <button
                key={item.id}
                type="button"
                className={classes.join(' ')}
                disabled={state === 'disabled'}
                aria-current={item.id === step ? 'step' : undefined}
                onClick={() => setStep(item.id)}
              >
                <span className="nav-step">{index + 1}</span>
                <span className="stack-sm" style={{ minWidth: 0 }}>
                  <span>{item.label}</span>
                  <span className="muted truncate">{snapshotMode && item.id === 'validate' ? 'Saved collection checks' : item.caption}</span>
                  <Badge tone={state === 'attention' ? 'danger' : state === 'done' ? 'ok' : !snapshotMode && ((item.id === 'validate' && validating) || (item.id === 'run' && runActive)) ? 'pending' : 'neutral'}>
                    {statusLabel(item.id)}
                  </Badge>
                </span>
              </button>
            );
          })}
        </nav>
      </aside>

      <main className="main">
        <header className="topbar">
          <div className="panel-header-text">
            <span className="topbar-title">{STEPS.find((s) => s.id === step)?.label}</span>
            <span className="topbar-sub">{snapshotMode && step === 'validate' ? 'Saved collection checks' : STEPS.find((s) => s.id === step)?.caption}</span>
          </div>
          <div className="topbar-actions">
            <GuardrailStrip />
            <button type="button" className="btn btn-sm" disabled={resetBlocked} onClick={() => {
              if (!window.confirm('Open local evidence import? Save any review edits first. Existing saved snapshots are kept.')) return;
              const url = new URL(window.location.href); url.searchParams.set('import', '1'); url.searchParams.delete('run'); url.searchParams.delete('new'); window.history.replaceState(null, '', url);
              setImportMode(true); setStep('configure');
            }}>Import evidence</button>
            <button
              type="button"
              className="btn btn-sm new-assessment"
              disabled={resetBlocked}
              title={resetBlocked
                ? 'Wait for discovery, sign-in, validation, or the current run to finish before resetting.'
                : 'Clear the current setup and results and return to Step 1. Saved snapshots are kept.'}
              onClick={newAssessment}
            >
              New assessment
            </button>
            <div className="topbar-controls">
              <SnapshotPicker onOpen={openResults} />
              <SnapshotHistory onDeleted={snapshotsDeleted} />
              <ThemeToggle />
            </div>
          </div>
        </header>

        <div className="content" ref={contentRef}>
          <div className="content-inner stack-lg">
            {backend.isMock && (
              <MockBanner
                scenarioLabel={activeScenario?.label ?? scenario}
                onOpenScenarios={() => setScenarioPickerOpen(!scenarioPickerOpen)}
              />
            )}

            {scenarioPickerOpen && (
              <Panel
                title="Demo scenarios"
                subtitle="Each scenario exercises a different evidence outcome so reviewers can judge the honest-failure behavior, not just the happy path."
              >
                <div className="stack-sm">
                  {(scenarios as { id: string; label: string; description: string }[]).map((s) => (
                    <label className="radio" key={s.id}>
                      <input
                        type="radio"
                        name="scenario"
                        checked={scenario === s.id}
                        onChange={() => {
                          setActiveScenario(s.id);
                          setScenario(s.id);
                          useRunStore.getState().reset();
                          useResultsStore.getState().clear();
                          useConfigStore.getState().reset();
                          void refreshRuns();
                          setStep('configure');
                        }}
                      />
                      <span className="checkbox-body">
                        <span className="checkbox-title">{s.label}</span>
                        <span className="checkbox-note">{s.description}</span>
                      </span>
                    </label>
                  ))}
                </div>
              </Panel>
            )}

            {snapshotMode && validating && (
              <Callout tone="info" title="A separate live validation is still running">
                It was started for the current setup, not by opening this snapshot.
                <button type="button" className="btn btn-ghost btn-sm" onClick={() => openLiveStep('validate')}>View live validation</button>
              </Callout>
            )}
            {permissionBusy && (snapshotMode || step !== 'validate') && (
              <Callout tone="warn" title="A separate permission setup is in progress">
                This is not assessment collection. Check its status before starting other live work.
                <button type="button" className="btn btn-ghost btn-sm" onClick={() => openLiveStep('validate')}>View permission setup</button>
              </Callout>
            )}
            {!snapshotMode && step !== 'validate' && (validating || validationError) && (
              <ValidationProgressPanel compact onOpen={() => setStep('validate')} />
            )}
            {!snapshotMode && step !== 'validate' && !validating && !validationError && validation && runPhase === 'idle' && (
              <Callout tone={validation.canRun ? 'ok' : 'warn'} title={validation.canRun ? 'Validation finished - analysis has not started' : 'Validation found blocking items'}>
                {validation.canRun ? 'Review any warnings in step 2, then start the assessment in step 3.' : 'Open step 2 to see what must be fixed before starting.'}
              </Callout>
            )}
            {runActive && (snapshotMode || step !== 'run') && (
              <Callout tone="info" title={snapshotMode ? 'A separate live assessment is running' : 'Assessment is running'}>
                <button type="button" className="btn btn-ghost btn-sm" onClick={() => openLiveStep('run')}>View run progress</button>
              </Callout>
            )}
            <ErrorBoundary label={STEPS.find((s) => s.id === step)?.label ?? 'This step'} key={step}>
              {importMode && step === 'configure' && <EvidenceImport onOpen={openResults} onCancel={() => {
                const url = new URL(window.location.href); url.searchParams.delete('import'); window.history.replaceState(null, '', url); setImportMode(false);
              }} />}
              {!importMode && snapshotMode && ['configure', 'validate', 'run'].includes(step) && <SnapshotSummary onResults={() => setStep('results')} />}
              {!importMode && !snapshotMode && step === 'configure' && <ConfigurePage onValidate={startValidation} />}
              {!snapshotMode && step === 'validate' && <div className="stack-lg">
                <ValidatePage onRun={() => setStep('run')} onConfigure={() => setStep('configure')} hideContinue />
                <PermissionSetupPanel hideActions />
                <Panel title="Next step: analysis"><ValidationActions onRun={() => setStep('run')} showValidation={false} /></Panel>
              </div>}
              {!snapshotMode && step === 'run' && <RunPage onViewResults={openResults} onValidate={() => setStep('validate')} />}
              {step === 'results' && <ResultsPage onExport={() => setStep('export')} />}
              {step === 'export' && <ExportPage />}
            </ErrorBoundary>
          </div>
        </div>
      </main>
    </div>
  );
}
