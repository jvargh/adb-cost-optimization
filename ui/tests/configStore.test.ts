import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MockAssessmentBackend } from '@/api/mockBackend';
import { setBackend } from '@/api';
import { useConfigStore } from '@/state/configStore';
import { validateConfiguration } from '@/lib/validation';
import { isResourceGroupSelected } from '@/lib/scopeSelection';
import type { AssessmentConfig, SubscriptionOption } from '@/types';
import defaultConfig from '../mock/fixtures/default-config.json';
import estateFixture from '../mock/fixtures/estate.json';

describe('configuration store scenario isolation', () => {
  beforeEach(() => {
    useConfigStore.getState().reset();
  });

  describe('subscription workspace defaults', () => {
    let estate: SubscriptionOption[];
    beforeEach(() => {
      useConfigStore.getState().reset();
      const config = structuredClone(defaultConfig) as AssessmentConfig;
      estate = structuredClone(estateFixture) as SubscriptionOption[];
      config.azure.subscriptions = [];
      config.azure.resourceGroups = [];
      config.azure.resourceGroupIds = [];
      config.azure.costScopes = [];
      config.azure.costScope = '';
      config.databricks.workspaces = [];
      delete config.databricks.sqlWarehouseId;
      config.databricks.allowSqlWarehouseAutoStart = false;
      useConfigStore.setState({ config, estate });
    });

    it('selects all and only workspace-containing groups and their workspaces without warehouse approval', () => {
      const validate = vi.spyOn(useConfigStore.getState(), 'validate');
      useConfigStore.getState().toggleSubscription(estate[0].subscriptionId);
      const { config, approvals, dirty, validation } = useConfigStore.getState();
      const expected = estate[0].resourceGroups.filter((group) => group.workspaces.length);
      expect(config!.azure.resourceGroupIds).toEqual(expected.map((group) => group.resourceGroupId.toLowerCase()));
      expect(config!.azure.resourceGroups).toEqual(expected.map((group) => group.name));
      expect(config!.databricks.workspaces.map((workspace) => workspace.workspaceId)).toEqual(expected.flatMap((group) => group.workspaces.map((workspace) => workspace.workspaceId)));
      expect(config!.databricks.workspaces.every((workspace) => workspace.include)).toBe(true);
      expect(config!.databricks.workspaces.map((workspace) => workspace.sqlWarehouseId)).toEqual(['19dfff78c4e639c4', '77c0e41ab2d95f18']);
      expect(approvals.approveSqlWarehouseAutoStart).toBe(false);
      expect(dirty).toBe(true);
      expect(validation).toBeNull();
      expect(validate).not.toHaveBeenCalled();
      validate.mockRestore();
    });

    it('preserves manual exclusions and warehouse settings when another subscription is selected', () => {
      const store = useConfigStore.getState();
      store.toggleSubscription(estate[0].subscriptionId);
      const group = estate[0].resourceGroups.find((item) => item.workspaces.length)!;
      store.toggleResourceGroup(estate[0].subscriptionId, group.name);
      const workspace = useConfigStore.getState().config!.databricks.workspaces[0];
      store.setWarehouse(workspace.workspaceId, 'explicit-warehouse');
      store.toggleWorkspace(workspace.workspaceId);
      store.toggleSubscription(estate[1].subscriptionId);
      const config = useConfigStore.getState().config!;
      expect(isResourceGroupSelected(config, group)).toBe(false);
      expect(config.databricks.workspaces.find((item) => item.workspaceId === workspace.workspaceId)).toMatchObject({
        include: false, sqlWarehouseId: 'explicit-warehouse',
      });
      expect(config.azure.costScopes).toHaveLength(2);
      expect(config.azure.costScope).toBe('');
      store.toggleSubscription(estate[1].subscriptionId);
      expect(useConfigStore.getState().config!.databricks.workspaces).toHaveLength(1);
      expect(useConfigStore.getState().config!.azure.costScope).toBe(`/subscriptions/${estate[0].subscriptionId}`);
      store.toggleSubscription(estate[0].subscriptionId);
      expect(useConfigStore.getState().config).toMatchObject({
        azure: { subscriptions: [], resourceGroups: [], resourceGroupIds: [], costScope: '', costScopes: [] },
        databricks: { workspaces: [] },
      });
    });

    it('keeps same-named groups isolated between subscriptions, including deselection', () => {
      const first = estate[0].resourceGroups[0];
      const second = estate[1].resourceGroups[0];
      second.name = first.name;
      second.resourceGroupId = `/subscriptions/${estate[1].subscriptionId}/resourcegroups/${first.name}`;
      second.workspaces.forEach((workspace) => { workspace.resourceGroup = first.name; });
      const store = useConfigStore.getState();
      store.toggleSubscription(estate[0].subscriptionId);
      store.toggleSubscription(estate[1].subscriptionId);
      store.toggleResourceGroup(estate[1].subscriptionId, first.name);
      let config = useConfigStore.getState().config!;
      expect(isResourceGroupSelected(config, first)).toBe(true);
      expect(isResourceGroupSelected(config, second)).toBe(false);
      expect(config.databricks.workspaces.some((workspace) => workspace.workspaceId === first.workspaces[0].workspaceId)).toBe(true);
      expect(config.databricks.workspaces.some((workspace) => workspace.workspaceId === second.workspaces[0].workspaceId)).toBe(false);
      store.toggleResourceGroup(estate[1].subscriptionId, first.name);
      store.toggleSubscription(estate[0].subscriptionId);
      config = useConfigStore.getState().config!;
      expect(config.azure.resourceGroupIds).toEqual([second.resourceGroupId]);
      expect(config.databricks.workspaces.map((workspace) => workspace.workspaceId)).toEqual(second.workspaces.map((workspace) => workspace.workspaceId));
    });

    it('does not select empty groups even when another subscription has the same group name', () => {
      const first = estate[0].resourceGroups[0];
      const other = estate[1].resourceGroups[0];
      other.name = first.name;
      other.resourceGroupId = `/subscriptions/${estate[1].subscriptionId}/resourcegroups/${first.name}`;
      estate[1].resourceGroups.forEach((group) => { group.workspaces = []; });
      useConfigStore.getState().toggleSubscription(estate[0].subscriptionId);
      useConfigStore.getState().toggleSubscription(estate[1].subscriptionId);
      expect(isResourceGroupSelected(useConfigStore.getState().config!, other)).toBe(false);
      useConfigStore.getState().toggleSubscription(estate[0].subscriptionId);
      const { config, approvals } = useConfigStore.getState();
      expect(config!.azure.resourceGroupIds).toEqual([]);
      expect(config!.databricks.workspaces).toEqual([]);
      const report = validateConfiguration({ config: config!, estate, approvals, environmentChecks: [] });
      expect(report.canRun).toBe(false);
    });
  });

  afterEach(() => { setBackend(null); vi.useRealTimers(); vi.restoreAllMocks(); });

  describe('initial setup scope defaults', () => {
    let backend: MockAssessmentBackend;
    let template: AssessmentConfig;
    let estate: SubscriptionOption[];

    beforeEach(() => {
      backend = new MockAssessmentBackend();
      template = structuredClone(defaultConfig) as AssessmentConfig;
      estate = structuredClone(estateFixture) as SubscriptionOption[];
      vi.spyOn(backend, 'loadDefaultConfig').mockResolvedValue(template);
      vi.spyOn(backend, 'discoverEstate').mockResolvedValue(estate);
      setBackend(backend);
    });

    it.each(['legacy names', 'empty qualified IDs'])('selects workspace groups in preselected subscriptions on first load with %s', async (scopeFormat) => {
      if (scopeFormat === 'empty qualified IDs') template.azure.resourceGroupIds = [];
      const original = structuredClone(template);
      const validate = vi.spyOn(backend, 'validate');
      const start = vi.spyOn(backend, 'startRun');

      await useConfigStore.getState().bootstrap();

      const { config, approvals, scopeDefaultsInitialized } = useConfigStore.getState();
      const groups = estate[0].resourceGroups.filter((group) => group.workspaces.length);
      expect(config!.azure.subscriptions).toEqual(original.azure.subscriptions);
      expect(config!.azure.resourceGroupIds).toEqual(groups.map((group) => group.resourceGroupId));
      expect(config!.databricks.workspaces.map((workspace) => workspace.workspaceId))
        .toEqual(groups.flatMap((group) => group.workspaces.map((workspace) => workspace.workspaceId)));
      expect(config!.databricks.workspaces.every((workspace) => workspace.include)).toBe(true);
      expect(config!.databricks.workspaces.map((workspace) => workspace.sqlWarehouseId)).toEqual(['19dfff78c4e639c4', '77c0e41ab2d95f18']);
      expect(approvals.approveSqlWarehouseAutoStart).toBe(false);
      expect(scopeDefaultsInitialized).toBe(true);
      expect(template).toEqual(original);
      expect(validate).not.toHaveBeenCalled();
      expect(start).not.toHaveBeenCalled();
    });

    it('preserves manual exclusions, edits, warehouses and approvals through discovery and sign-in retries', async () => {
      await useConfigStore.getState().bootstrap();
      const store = useConfigStore.getState();
      store.toggleResourceGroup(estate[0].subscriptionId, estate[0].resourceGroups[0].name);
      const workspaceId = useConfigStore.getState().config!.databricks.workspaces[0].workspaceId;
      store.toggleWorkspace(workspaceId);
      store.setWarehouse(workspaceId, 'explicit-warehouse');
      store.setApproval('approveSqlWarehouseAutoStart', true);
      store.patch((config) => { config.customerId = 'edited-customer'; });
      const edited = structuredClone(useConfigStore.getState().config);
      const approvals = structuredClone(useConfigStore.getState().approvals);
      vi.spyOn(backend, 'signIn').mockResolvedValue();

      await store.bootstrap();
      await store.signIn();

      expect(useConfigStore.getState().config).toEqual(edited);
      expect(useConfigStore.getState().approvals).toEqual(approvals);
      expect(useConfigStore.getState().dirty).toBe(true);
      expect(backend.loadDefaultConfig).toHaveBeenCalledTimes(1);
      store.toggleSubscription(estate[0].subscriptionId);
      await store.bootstrap();
      expect(useConfigStore.getState().config!.azure.subscriptions).toEqual([]);
      expect(useConfigStore.getState().config!.databricks.workspaces).toEqual([]);
    });

    it('applies defaults after failed initial discovery recovers, without losing intervening edits', async () => {
      vi.mocked(backend.discoverEstate).mockRejectedValueOnce(new Error('Azure sign-in expired'));
      await useConfigStore.getState().bootstrap();
      expect(useConfigStore.getState().error).toBe('Azure sign-in expired');
      expect(useConfigStore.getState().scopeDefaultsInitialized).toBe(false);
      useConfigStore.getState().patch((config) => { config.assessmentId = 'edited-before-retry'; });

      await useConfigStore.getState().bootstrap();

      const { config, error, scopeDefaultsInitialized } = useConfigStore.getState();
      expect(error).toBeNull();
      expect(scopeDefaultsInitialized).toBe(true);
      expect(config!.assessmentId).toBe('edited-before-retry');
      expect(config!.azure.resourceGroupIds).toHaveLength(2);
      expect(config!.databricks.workspaces).toHaveLength(2);
      expect(backend.loadDefaultConfig).toHaveBeenCalledTimes(1);
    });

    it('does not discard existing group and workspace targets when discovery omits them', async () => {
      estate[0].resourceGroups.shift();
      const previous = structuredClone(template.databricks.workspaces[0]);
      await useConfigStore.getState().bootstrap();
      const { config } = useConfigStore.getState();
      expect(config!.azure.resourceGroups).toContain(previous.resourceGroup);
      expect(config!.databricks.workspaces).toContainEqual(previous);
      expect(config!.azure.resourceGroupIds).toHaveLength(2);
      expect(config!.databricks.workspaces).toHaveLength(2);
    });

    it('keeps a legacy warehouse limited to existing targets when new workspace groups are added', async () => {
      template.databricks.sqlWarehouseId = 'previous-warehouse';
      template.databricks.workspaces[0].include = false;
      await useConfigStore.getState().bootstrap();
      const { config } = useConfigStore.getState();
      expect(config!.databricks.sqlWarehouseId).toBeUndefined();
      expect(config!.databricks.workspaces[0]).toMatchObject({ include: false, sqlWarehouseId: 'previous-warehouse' });
      expect(config!.databricks.workspaces[1]).toMatchObject({ include: true });
      expect(config!.databricks.workspaces[1].sqlWarehouseId).toBe('77c0e41ab2d95f18');
      expect(template.databricks.workspaces[0].sqlWarehouseId).toBeUndefined();
    });
  });

  it('removes prior scenario configuration and approvals on reset', async () => {
    const store = useConfigStore.getState();
    await store.bootstrap();

    const workspaceId = useConfigStore.getState().config!.databricks.workspaces[0].workspaceId;
    useConfigStore.getState().setWarehouse(workspaceId, 'warehouse-from-prior-scenario');
    useConfigStore.getState().setApproval('approveSqlWarehouseAutoStart', true);

    useConfigStore.getState().reset();

    const reset = useConfigStore.getState();
    expect(reset.config).toBeNull();
    expect(reset.estate).toEqual([]);
    expect(reset.validation).toBeNull();
    expect(reset.approvals).toEqual({
      approveSqlWarehouseAutoStart: false,
      continueOnCollectorError: true,
      acknowledgedReadOnly: true,
    });

    await reset.bootstrap();
    const reloaded = useConfigStore.getState();
    expect(reloaded.config?.databricks.workspaces[0].sqlWarehouseId).toBe('19dfff78c4e639c4');
  });

  it('loads saved configuration when live estate discovery needs a new Azure sign-in', async () => {
    const backend = new MockAssessmentBackend();
    backend.discoverEstate = async () => {
      throw new Error("Your Azure sign-in has expired. Run 'az login' in PowerShell, then reload this page.");
    };
    setBackend(backend);

    await useConfigStore.getState().bootstrap();

    const state = useConfigStore.getState();
    expect(state.config).not.toBeNull();
    expect(state.estate).toEqual([]);
    expect(state.error).toContain('az login');
  });

  it('clears both workspace and global warehouse IDs when None is selected', async () => {
    await useConfigStore.getState().bootstrap();
    const workspace = useConfigStore.getState().config!.databricks.workspaces[0];
    useConfigStore.getState().patch((draft) => {
      draft.databricks.sqlWarehouseId = 'global-warehouse';
      draft.databricks.workspaces[0].sqlWarehouseId = 'workspace-warehouse';
    });

    useConfigStore.getState().setWarehouse(workspace.workspaceId, undefined);

    const databricks = useConfigStore.getState().config!.databricks;
    expect(databricks.sqlWarehouseId).toBeUndefined();
    expect(databricks.workspaces[0].sqlWarehouseId).toBe('');
    expect(databricks.allowSqlWarehouseAutoStart).toBe(false);
    expect(useConfigStore.getState().approvals.approveSqlWarehouseAutoStart).toBe(false);
  });

  it('generates editable engagement IDs and dates while clearing scope and approvals without changing the template', async () => {
    const backend = new MockAssessmentBackend();
    const template = await backend.loadDefaultConfig();
    template.databricks.sqlWarehouseId = 'previous-warehouse';
    template.azure.resourceGroupIds = ['/subscriptions/prior/resourceGroups/prior'];
    template.azure.costScopes = ['/subscriptions/prior'];
    template.databricks.allowSqlWarehouseAutoStart = true;
    template.databricks.deepDiveJobRunIds = ['prior-job'];
    template.databricks.deepDiveTableNames = ['prior.table'];
    template.databricks.includeIdentities = true;
    template.databricks.includeNotebookPaths = true;
    template.databricks.includeQueryText = true;
    template.redaction.hashIdentities = false;
    template.redaction.hashNotebookPaths = false;
    template.redaction.omitQueryText = false;
    const original = structuredClone(template);
    backend.loadDefaultConfig = async () => template;
    backend.discoverEstate = async () => [];
    setBackend(backend);

    await useConfigStore.getState().bootstrap(true);
    const state = useConfigStore.getState();
    expect(state.config).toMatchObject({
      customerId: expect.stringMatching(/^customer-[0-9a-f]{8}$/),
      assessmentId: expect.stringMatching(/^assessment-[0-9a-f]{8}$/),
      azure: { subscriptions: [], resourceGroups: [], resourceGroupIds: [], costScope: '', costScopes: [], includeManagementGroups: false },
      databricks: {
        workspaces: [], deepDiveJobRunIds: [], deepDiveTableNames: [],
        allowSqlWarehouseAutoStart: false, includeIdentities: false, includeNotebookPaths: false, includeQueryText: false,
      },
      redaction: { hashIdentities: true, hashNotebookPaths: true, omitQueryText: true },
    });
    expect(state.config?.databricks.sqlWarehouseId).toBeUndefined();
    expect(state.approvals.approveSqlWarehouseAutoStart).toBe(false);
    expect(state.config?.azure.tenantId).toBe(template.azure.tenantId);
    expect(state.config?.outputs).toEqual(template.outputs);
    expect(template).toEqual(original);
    const report = validateConfiguration({ config: state.config!, approvals: state.approvals, estate: [], environmentChecks: [] });
    expect(report.checks.filter((check) => ['customer-id', 'assessment-id', 'analysis-window'].includes(check.id)).map((check) => check.status))
      .toEqual(['pass', 'pass', 'pass']);
  });

  it('does not let an earlier configuration load overwrite a fresh reset', async () => {
    const backend = new MockAssessmentBackend();
    const template = await backend.loadDefaultConfig();
    let finish!: (value: typeof template) => void;
    vi.spyOn(backend, 'loadDefaultConfig')
      .mockImplementationOnce(() => new Promise((resolve) => { finish = resolve; }))
      .mockResolvedValue(template);
    backend.discoverEstate = async () => [];
    setBackend(backend);
    const pending = useConfigStore.getState().bootstrap();
    useConfigStore.getState().reset();
    await useConfigStore.getState().bootstrap(true);
    finish(template);
    await pending;
    expect(useConfigStore.getState().config?.customerId).toMatch(/^customer-[0-9a-f]{8}$/);
    expect(useConfigStore.getState().config?.azure.subscriptions).toEqual([]);
  });

  it('preserves fresh setup on explicit retry after a configuration load failure', async () => {
    const backend = new MockAssessmentBackend();
    const template = await backend.loadDefaultConfig();
    vi.spyOn(backend, 'loadDefaultConfig')
      .mockRejectedValueOnce(new Error('Config unavailable'))
      .mockResolvedValue(template);
    backend.discoverEstate = async () => [];
    setBackend(backend);
    await useConfigStore.getState().bootstrap(true);
    expect(useConfigStore.getState().error).toBe('Config unavailable');
    expect(useConfigStore.getState().config).toBeNull();
    await useConfigStore.getState().bootstrap();
    expect(useConfigStore.getState().error).toBeNull();
    expect(useConfigStore.getState().config?.customerId).toMatch(/^customer-[0-9a-f]{8}$/);
  });

  it.each([
    ['2026-09-28T05:02:50Z', '2026-08-29T00:00:00.000Z', '2026-09-28T00:00:00.000Z'],
    ['2026-01-01T00:00:01Z', '2025-12-02T00:00:00.000Z', '2026-01-01T00:00:00.000Z'],
    ['2024-03-01T23:59:59Z', '2024-01-31T00:00:00.000Z', '2024-03-01T00:00:00.000Z'],
  ])('defaults to exactly 30 complete UTC days at %s', async (now, start, end) => {
    const backend = new MockAssessmentBackend();
    const template = await backend.loadDefaultConfig();
    backend.loadDefaultConfig = async () => template;
    backend.discoverEstate = async () => [];
    setBackend(backend);
    vi.useFakeTimers();
    vi.setSystemTime(new Date(now));
    await useConfigStore.getState().bootstrap(true);
    expect(useConfigStore.getState().config?.analysis).toMatchObject({ startUtc: start, endUtc: end, timeZone: 'UTC' });
  });

  it('keeps edits during discovery retries and generates new IDs only for a new setup', async () => {
    const backend = new MockAssessmentBackend();
    const template = await backend.loadDefaultConfig();
    backend.loadDefaultConfig = async () => template;
    backend.discoverEstate = async () => [];
    setBackend(backend);
    await useConfigStore.getState().bootstrap(true);
    const first = useConfigStore.getState().config!;
    useConfigStore.getState().patch((config) => {
      config.customerId = 'my-customer';
      config.assessmentId = 'my-assessment';
      config.analysis.startUtc = '2026-07-01T00:00:00Z';
      config.analysis.endUtc = '2026-08-01T00:00:00Z';
    });
    await useConfigStore.getState().bootstrap();
    expect(useConfigStore.getState().config).toMatchObject({
      customerId: 'my-customer', assessmentId: 'my-assessment',
      analysis: { startUtc: '2026-07-01T00:00:00Z', endUtc: '2026-08-01T00:00:00Z' },
    });
    useConfigStore.getState().reset();
    await useConfigStore.getState().bootstrap(true);
    expect(useConfigStore.getState().config?.customerId).not.toBe(first.customerId);
    expect(useConfigStore.getState().config?.assessmentId).not.toBe(first.assessmentId);
  });
});
