import { describe, expect, it } from 'vitest';
import {
  MockAssessmentBackend,
  setActiveScenario,
  setPlaybackSpeed,
  listScenarioIds,
} from '@/api/mockBackend';
import { COLLECTION_STATUSES } from '@/types';

const backend = new MockAssessmentBackend();

describe('mock backend fixture conformance', () => {
  it('exposes the three review scenarios', () => {
    expect(listScenarioIds().sort()).toEqual(
      ['contoso-clean', 'contoso-partial', 'fabrikam-failed'].sort(),
    );
  });

  it('discovers an estate with resource groups and workspaces', async () => {
    const estate = await backend.discoverEstate();
    expect(estate.length).toBeGreaterThan(0);
    expect(estate.some((s) => s.resourceGroups.some((g) => g.workspaces.length > 0))).toBe(true);
    expect(estate.some((s) => s.resourceGroups.some((g) => g.isManagedResourceGroup))).toBe(true);
  });

  it('lists persisted runs that all resolve to loadable results', async () => {
    const runs = await backend.listRuns();
    expect(runs.length).toBeGreaterThan(0);
    for (const run of runs) {
      const results = await backend.loadResults(run.runId);
      expect(results.manifest.runId).toBe(run.runId);
    }
  });

  it.each(listScenarioIds())('scenario %s produces a contract-conformant result set', async (id) => {
    setActiveScenario(id);
    const runs = await backend.listRuns();
    const run = runs.find((r) => r.scenarioId === id);
    expect(run, `scenario ${id} must have a persisted run`).toBeDefined();
    const results = await backend.loadResults(run!.runId);

    for (const source of results.collection) {
      expect(COLLECTION_STATUSES).toContain(source.status);
      expect(['azure', 'databricks']).toContain(source.domain);
    }

    for (const finding of results.candidates.findings) {
      expect(finding.humanValidationRequired).toBe(true);
      expect(finding.estimatedSavings).toBeNull();
      expect(['candidate', 'insufficient_evidence']).toContain(finding.status);
    }

    expect(results.benefits.realizedSavings).toBeNull();
    expect(results.reportMarkdown).toContain('# ');
    expect(results.exports.length).toBeGreaterThan(0);
  });

  it('marks the run partial whenever any source is degraded', async () => {
    setActiveScenario('contoso-partial');
    const runs = await backend.listRuns();
    const run = runs.find((r) => r.scenarioId === 'contoso-partial')!;
    const results = await backend.loadResults(run.runId);
    const degraded = results.collection.filter(
      (s) => s.status === 'partial' || s.status === 'failed' || s.status === 'pending telemetry',
    );
    expect(degraded.length).toBeGreaterThan(0);
    expect(results.manifest.status).toBe('partial');
  });

  it('reports absent cost rather than zero when cost collection failed', async () => {
    setActiveScenario('fabrikam-failed');
    const runs = await backend.listRuns();
    const run = runs.find((r) => r.scenarioId === 'fabrikam-failed')!;
    const results = await backend.loadResults(run.runId);
    const costSource = results.collection.find((s) => s.name.includes('Cost Management'));
    expect(costSource?.status).toBe('failed');
    expect(costSource?.error).toBeTruthy();
    expect(results.costTrend.length).toBe(0);
  });

  it('persists review decisions without touching the analysis', async () => {
    setActiveScenario('contoso-clean');
    const runs = await backend.listRuns();
    const run = runs.find((r) => r.scenarioId === 'contoso-clean')!;
    const before = await backend.loadResults(run.runId);
    const updated = before.review.map((entry) => ({
      ...entry,
      decision: 'accepted' as const,
      reviewer: 'Test Reviewer',
    }));
    await backend.saveReview(run.runId, updated);
    const after = await backend.loadResults(run.runId);
    expect(after.review.every((e) => e.decision === 'accepted')).toBe(true);
    expect(after.candidates.candidateCount).toBe(before.candidates.candidateCount);
  });

  it('renders every export artifact it advertises', async () => {
    setActiveScenario('contoso-partial');
    const runs = await backend.listRuns();
    const run = runs.find((r) => r.scenarioId === 'contoso-partial')!;
    const results = await backend.loadResults(run.runId);
    for (const artifact of results.exports) {
      const payload = await backend.readArtifact(run.runId, artifact.relativePath);
      expect(payload.content.length).toBeGreaterThan(0);
    }
  }, 30000);

  it('streams a progress timeline that terminates', async () => {
    setActiveScenario('contoso-clean');
    setPlaybackSpeed(400);
    const config = await backend.loadDefaultConfig();
    const handle = await backend.startRun(config, {
      approveSqlWarehouseAutoStart: true,
      continueOnCollectorError: true,
      acknowledgedReadOnly: true,
    });
    const types: string[] = [];
    await new Promise<void>((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error('timeline never completed')), 15000);
      handle.subscribe((event) => {
        types.push(event.type);
        if (event.type === 'completed') {
          clearTimeout(timeout);
          resolve();
        }
      });
    });
    expect(types).toContain('phase');
    expect(types).toContain('source');
    expect(types[types.length - 1]).toBe('completed');
    setPlaybackSpeed(6);
  }, 20000);

  it('stops the timeline and emits canceled when cancellation is requested', async () => {
    setActiveScenario('contoso-partial');
    setPlaybackSpeed(1);
    const config = await backend.loadDefaultConfig();
    const handle = await backend.startRun(config, {
      approveSqlWarehouseAutoStart: false,
      continueOnCollectorError: true,
      acknowledgedReadOnly: true,
    });
    const types: string[] = [];
    handle.subscribe((event) => types.push(event.type));

    await handle.cancel();
    await new Promise((resolve) => setTimeout(resolve, 100));

    expect(types).toEqual(['canceled']);
    setPlaybackSpeed(6);
  });
});
