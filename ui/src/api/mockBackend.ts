import type {
  AssessmentBackend,
  ArtifactPayload,
  RunApprovals,
  RunEvent,
  RunHandle,
  SnapshotDeletion,
  PermissionSetup,
} from './backend';
import type {
  AssessmentConfig,
  AssessmentResults,
  CollectionSource,
  RunSummary,
  SubscriptionOption,
  ValidationCheck,
  ValidationReport,
  ValidationProgress,
  ReviewEntry,
} from '@/types';
import { validateConfiguration } from '@/lib/validation';

import estateFixture from '../../mock/fixtures/estate.json';
import defaultConfigFixture from '../../mock/fixtures/default-config.json';
import runsFixture from '../../mock/fixtures/runs.json';
import contosoPartial from '../../mock/fixtures/contoso-partial.results.json';
import contosoClean from '../../mock/fixtures/contoso-clean.results.json';
import fabrikamFailed from '../../mock/fixtures/fabrikam-failed.results.json';
import contosoPartialTimeline from '../../mock/fixtures/contoso-partial.timeline.json';
import contosoCleanTimeline from '../../mock/fixtures/contoso-clean.timeline.json';
import fabrikamFailedTimeline from '../../mock/fixtures/fabrikam-failed.timeline.json';

interface TimelineFixture {
  runId: string;
  events: (Record<string, unknown> & { offsetMs: number; type: string })[];
}

const RESULTS: Record<string, AssessmentResults> = {
  'contoso-partial': contosoPartial as unknown as AssessmentResults,
  'contoso-clean': contosoClean as unknown as AssessmentResults,
  'fabrikam-failed': fabrikamFailed as unknown as AssessmentResults,
};

const TIMELINES: Record<string, TimelineFixture> = {
  'contoso-partial': contosoPartialTimeline as unknown as TimelineFixture,
  'contoso-clean': contosoCleanTimeline as unknown as TimelineFixture,
  'fabrikam-failed': fabrikamFailedTimeline as unknown as TimelineFixture,
};

const RUNS = runsFixture as unknown as RunSummary[];

/** Mutations made during the session (review decisions) live here only. */
const reviewOverrides = new Map<string, ReviewEntry[]>();

/**
 * Chooses which fixture a new run should replay. The Configure screen exposes
 * this as an explicit "demo scenario" control so reviewers can exercise the
 * healthy, degraded, and failed paths deliberately.
 */
export let activeScenarioId = 'contoso-partial';

export function setActiveScenario(id: string): void {
  if (RESULTS[id]) activeScenarioId = id;
}

export function listScenarioIds(): string[] {
  return Object.keys(RESULTS);
}

/** Playback speed multiplier for the simulated run. */
export let playbackSpeed = 6;

export function setPlaybackSpeed(multiplier: number): void {
  playbackSpeed = Math.max(1, multiplier);
}

const delay = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

function deepClone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

/** Environment probes the real adapter performs by shelling out. */
function mockEnvironmentChecks(scenarioId: string): ValidationCheck[] {
  const costManagementFails = scenarioId === 'fabrikam-failed';
  return [
    {
      id: 'powershell-version',
      title: 'PowerShell 7 or later is available',
      severity: 'blocker',
      status: 'pass',
      group: 'environment',
      detail: 'PowerShell 7.4.6 detected.',
    },
    {
      id: 'azure-cli',
      title: 'Azure CLI is installed and signed in',
      severity: 'blocker',
      status: 'pass',
      group: 'environment',
      detail: 'Azure CLI 2.69.0 signed in as assessment-runner@contoso.com.',
    },
    {
      id: 'python-runtime',
      title: 'Python 3 is available for the analysis pipeline',
      severity: 'blocker',
      status: 'pass',
      group: 'environment',
      detail: 'Python 3.13.15 detected. The pipeline has no third-party dependencies.',
    },
    {
      id: 'auth-context',
      title: 'Tenant context matches the selected scope',
      severity: 'blocker',
      status: 'pass',
      group: 'permissions',
      detail: 'Signed-in tenant matches azure.tenantId. Tokens are held in memory only and are never written to disk.',
    },
    {
      id: 'rbac-reader',
      title: 'One resource group may not be readable',
      severity: 'warning',
      status: 'warn',
      group: 'permissions',
      detail:
        'The signed-in account cannot read rg-analytics-archive. If you select that resource group, its data will be missing from the report.',
      remediation: 'Give the account Reader access, or do not select that resource group.',
    },
    {
      id: 'rbac-cost-management',
      title: 'Cost Management Reader is assigned on the cost scope',
      severity: 'blocker',
      status: costManagementFails ? 'fail' : 'pass',
      group: 'permissions',
      detail: costManagementFails
        ? '403 Forbidden when probing Cost Management. Without this role no cost baseline can be established and every cost figure would be absent, not zero.'
        : 'Cost Management Reader confirmed on the configured cost scope.',
      remediation: costManagementFails
        ? 'Assign Cost Management Reader on the target subscription, then re-validate.'
        : undefined,
    },
    {
      id: 'databricks-token',
      title: 'Databricks workspace access is available',
      severity: 'warning',
      status: 'pass',
      group: 'permissions',
      detail:
        'Entra token acquired for resource 2ff814a6-3304-4ab8-85cb-cd0e6f879c1d. Workspace admin is required for governance settings.',
    },
    {
      id: 'system-tables-access',
      title: 'Some Databricks system tables may not be available',
      severity: 'warning',
      status: 'warn',
      group: 'permissions',
      detail:
        'The signed-in account may not be able to read system tables in every workspace. Missing data will be shown as unavailable, not zero.',
      remediation: 'Give the account SELECT access to the required system tables.',
    },
  ];
}

class MockRunHandle implements RunHandle {
  readonly runId: string;
  private listeners = new Set<(event: RunEvent) => void>();
  private timers: number[] = [];
  private canceled = false;

  constructor(runId: string, timeline: TimelineFixture) {
    this.runId = runId;
    this.schedule(timeline);
  }

  private schedule(timeline: TimelineFixture): void {
    for (const raw of timeline.events) {
      const { offsetMs, ...rest } = raw;
      const atDelay = offsetMs / playbackSpeed;
      const timer = window.setTimeout(() => {
        if (this.canceled) return;
        const event = { ...rest, atUtc: new Date().toISOString() } as RunEvent;
        this.listeners.forEach((listener) => listener(event));
      }, atDelay);
      this.timers.push(timer);
    }
  }

  subscribe(listener: (event: RunEvent) => void): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  async cancel(): Promise<void> {
    if (this.canceled) return;
    this.canceled = true;
    this.timers.forEach((t) => window.clearTimeout(t));
    this.timers = [];
    const event: RunEvent = { type: 'canceled', atUtc: new Date().toISOString() };
    this.listeners.forEach((listener) => listener(event));
  }
}

export class MockAssessmentBackend implements AssessmentBackend {
  async capabilityOperation<T>(_runId: string | null, _action: string, _input: object): Promise<T> {
    throw new Error('Capability evidence operations require the local production host. Demo fixtures do not simulate cloud publication or imports.');
  }
  async previewPermissionSetup(): Promise<PermissionSetup> {
    throw new Error('Permission setup is unavailable in demo mode. No permissions were changed.');
  }

  async getPermissionSetup(): Promise<PermissionSetup> {
    throw new Error('Permission setup is unavailable in demo mode.');
  }

  async applyPermissionSetup(): Promise<PermissionSetup> {
    throw new Error('Permission setup is unavailable in demo mode. No permissions were changed.');
  }

  readonly id = 'mock';
  readonly isMock = true;
  private deletedRuns = new Set<string>();
  private activeRuns = new Set<string>();

  async discoverEstate(): Promise<SubscriptionOption[]> {
    await delay(420);
    return deepClone(estateFixture as unknown as SubscriptionOption[]);
  }

  async signIn(_tenantId: string): Promise<void> {
    await delay(160);
  }

  async loadDefaultConfig(): Promise<AssessmentConfig> {
    await delay(160);
    return deepClone(defaultConfigFixture as unknown as AssessmentConfig);
  }

  async validate(
    config: AssessmentConfig,
    approvals: RunApprovals,
    onProgress?: (progress: ValidationProgress) => void,
  ): Promise<ValidationReport> {
    const estate = deepClone(estateFixture as unknown as SubscriptionOption[]);
    const report = validateConfiguration({
      config,
      approvals,
      estate,
      environmentChecks: mockEnvironmentChecks(activeScenarioId),
    });
    const startedAtUtc = new Date().toISOString();
    const progress: ValidationProgress = {
      validationId: 'mock-validation',
      status: 'running',
      startedAtUtc,
      finishedAtUtc: null,
      lastActivityAtUtc: startedAtUtc,
      message: 'Checking demo configuration and access.',
      steps: report.checks.map((check) => ({
        id: check.id, title: check.title, status: 'pending', detail: 'Waiting.',
        startedAtUtc: null, finishedAtUtc: null, estimatedSeconds: 1,
      })),
    };
    for (let index = 0; index < report.checks.length; index++) {
      const step = progress.steps[index];
      step.status = 'running';
      step.startedAtUtc = new Date().toISOString();
      progress.message = step.title;
      progress.lastActivityAtUtc = step.startedAtUtc;
      onProgress?.(deepClone(progress));
      await delay(700 / report.checks.length);
      step.status = report.checks[index].status;
      step.detail = report.checks[index].detail;
      step.finishedAtUtc = new Date().toISOString();
    }
    progress.status = 'completed';
    progress.finishedAtUtc = new Date().toISOString();
    progress.lastActivityAtUtc = progress.finishedAtUtc;
    onProgress?.(deepClone(progress));
    return report;
  }

  async startRun(config: AssessmentConfig, approvals: RunApprovals): Promise<RunHandle> {
    await delay(260);
    void config;
    void approvals;
    const scenario = activeScenarioId;
    const timeline = TIMELINES[scenario];
    this.deletedRuns.delete(timeline.runId);
    this.activeRuns.add(timeline.runId);
    const handle = new MockRunHandle(timeline.runId, timeline);
    handle.subscribe((event) => {
      if (['completed', 'failed', 'canceled'].includes(event.type)) this.activeRuns.delete(timeline.runId);
    });
    return handle;
  }

  async listRuns(): Promise<RunSummary[]> {
    await delay(220);
    return deepClone(RUNS.filter((run) => !this.deletedRuns.has(run.runId) && !this.activeRuns.has(run.runId)));
  }

  async deleteSnapshots(runIds: string[]): Promise<SnapshotDeletion> {
    await delay(220);
    const result: SnapshotDeletion = { deletedRunIds: [], failures: [] };
    for (const runId of new Set(runIds)) {
      if (this.activeRuns.has(runId)) {
        result.failures.push({ runId, message: 'Active or unfinished assessments cannot be deleted.' });
      } else if (!RUNS.some((run) => run.runId === runId) || this.deletedRuns.has(runId)) {
        result.failures.push({ runId, message: 'Saved snapshot not found.' });
      } else {
        this.deletedRuns.add(runId);
        reviewOverrides.delete(runId);
        result.deletedRunIds.push(runId);
      }
    }
    return result;
  }

  async loadResults(runId: string): Promise<AssessmentResults> {
    await delay(480);
    const scenarioId =
      RUNS.find((r) => r.runId === runId)?.scenarioId ??
      Object.keys(RESULTS).find((key) => RESULTS[key].manifest.runId === runId);
    if (!scenarioId || !RESULTS[scenarioId] || this.deletedRuns.has(runId)) {
      throw new Error(`No persisted assessment run was found with id '${runId}'.`);
    }
    const results = deepClone(RESULTS[scenarioId]);
    const override = reviewOverrides.get(runId);
    if (override) results.review = deepClone(override);
    return results;
  }

  async saveReview(runId: string, entries: ReviewEntry[]): Promise<void> {
    await delay(220);
    reviewOverrides.set(runId, deepClone(entries));
  }

  async readArtifact(runId: string, relativePath: string): Promise<ArtifactPayload> {
    const results = await this.loadResults(runId);
    if (relativePath.endsWith('.md')) {
      return { relativePath, mimeType: 'text/markdown', content: results.reportMarkdown };
    }
    if (relativePath.endsWith('.csv')) {
      return { relativePath, mimeType: 'text/csv', content: buildCsv(relativePath, results) };
    }
    return {
      relativePath,
      mimeType: 'application/json',
      content: JSON.stringify(jsonArtifact(relativePath, results), null, 2),
    };
  }
}

function csvEscape(value: string | number | null): string {
  const text = value === null || value === undefined ? '' : String(value);
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

function buildCsv(relativePath: string, results: AssessmentResults): string {
  if (relativePath.includes('top-cost-drivers')) {
    const rows = [['rank', 'driver', 'observedCost', 'currency']];
    results.costDrivers.forEach((d) =>
      rows.push([String(d.rank), d.driver, String(d.observedCost), d.currency]),
    );
    return rows.map((r) => r.map(csvEscape).join(',')).join('\n');
  }
  if (relativePath.includes('prioritized-backlog')) {
    const rows = [['order', 'detectorId', 'title', 'status', 'confidence', 'estimatedSavings']];
    [...results.candidates.findings]
      .sort((a, b) => b.confidence.score - a.confidence.score)
      .forEach((f, index) =>
        rows.push([
          String(index + 1),
          f.detectorId,
          f.title,
          f.status,
          f.confidence.level,
          'Not estimated',
        ]),
      );
    return rows.map((r) => r.map(csvEscape).join(',')).join('\n');
  }
  const rows = [
    [
      'findingId',
      'finding',
      'evidenceLinks',
      'reviewer',
      'role',
      'reviewedAtUtc',
      'decision',
      'businessSlaContext',
      'performanceReliabilityRisk',
      'securityGovernanceImpact',
      'validationExperiment',
      'ownerApprover',
      'rationale',
    ],
  ];
  results.review.forEach((entry) =>
    rows.push([
      entry.findingId,
      entry.finding,
      entry.evidenceLinks.join('; '),
      entry.reviewer,
      entry.role,
      entry.reviewedAtUtc ?? '',
      entry.decision,
      entry.businessSlaContext,
      entry.performanceReliabilityRisk,
      entry.securityGovernanceImpact,
      entry.validationExperiment,
      entry.ownerApprover,
      entry.rationale,
    ]),
  );
  return rows.map((r) => r.map(csvEscape).join(',')).join('\n');
}

function jsonArtifact(relativePath: string, results: AssessmentResults): unknown {
  if (relativePath.includes('optimization-candidates')) return results.candidates;
  if (relativePath.includes('cost-reconciliation')) return results.reconciliation;
  if (relativePath.includes('telemetry-quality')) return results.telemetry;
  if (relativePath.includes('collection-status')) return results.collection;
  if (relativePath.includes('scope-filter')) return results.scopeFilter;
  if (relativePath.includes('benefits-baseline')) return results.benefits;
  if (relativePath.includes('attribution-coverage')) return results.attribution;
  return results.manifest;
}

export function getCollectionSources(results: AssessmentResults): CollectionSource[] {
  return results.collection;
}
