import { create } from 'zustand';
import type { AssessmentConfig, SubscriptionOption, ValidationReport, ValidationProgress } from '@/types';
import type { RunApprovals } from '@/api/backend';
import { getBackend } from '@/api';
import { usePermissionStore } from './permissionStore';
import { validateConfiguration } from '@/lib/validation';
import { migrateLegacyDeepDiveTargets, selectedResourceGroupIds, setSelectedResourceGroups, warehouseScopeKey, workspaceResourceGroupIds } from '@/lib/scopeSelection';

interface ConfigState {
  config: AssessmentConfig | null;
  estate: SubscriptionOption[];
  approvals: RunApprovals;
  loading: boolean;
  error: string | null;
  dirty: boolean;
  validation: ValidationReport | null;
  validating: boolean;
  validationProgress: ValidationProgress | null;
  validationError: string | null;
  validationStartedAtUtc: string | null;
  validationLastResponseAtUtc: string | null;
  validationRequestId: number;
  signingIn: boolean;
  fresh: boolean;
  scopeDefaultsInitialized: boolean;

  bootstrap: (fresh?: boolean) => Promise<void>;
  signIn: () => Promise<void>;
  patch: (mutate: (draft: AssessmentConfig) => void) => void;
  setApproval: <K extends keyof RunApprovals>(key: K, value: RunApprovals[K]) => void;
  toggleSubscription: (subscriptionId: string) => void;
  toggleResourceGroup: (subscriptionId: string, name: string) => void;
  toggleWorkspace: (workspaceId: string) => void;
  setWarehouse: (workspaceId: string, warehouseId: string | undefined) => void;
  validate: () => Promise<ValidationReport>;
  reset: () => void;
  resetValidation: () => void;
}

const DEFAULT_APPROVALS: RunApprovals = {
  approveSqlWarehouseAutoStart: false,
  continueOnCollectorError: true,
  acknowledgedReadOnly: true,
};

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

function freshConfig(template: AssessmentConfig): AssessmentConfig {
  const config = clone(template);
  config.customerId = `customer-${crypto.randomUUID().slice(0, 8)}`;
  config.assessmentId = `assessment-${crypto.randomUUID().slice(0, 8)}`;
  config.azure.subscriptions = [];
  config.azure.resourceGroups = [];
  config.azure.resourceGroupIds = [];
  config.azure.costScope = '';
  config.azure.costScopes = [];
  config.azure.includeManagementGroups = false;
  config.databricks.workspaces = [];
  delete config.databricks.sqlWarehouseId;
  config.databricks.allowSqlWarehouseAutoStart = false;
  config.databricks.deepDiveJobRunIds = [];
  config.databricks.deepDiveTableNames = [];
  config.databricks.includeIdentities = false;
  config.databricks.includeNotebookPaths = false;
  config.databricks.includeQueryText = false;
  config.redaction.hashIdentities = true;
  config.redaction.hashNotebookPaths = true;
  config.redaction.omitQueryText = true;
  const end = new Date();
  end.setUTCHours(0, 0, 0, 0);
  const start = new Date(end);
  start.setUTCDate(start.getUTCDate() - 30);
  config.analysis.startUtc = start.toISOString();
  config.analysis.endUtc = end.toISOString();
  config.analysis.timeZone = 'UTC';
  return config;
}

let bootstrapRequest = 0;

export const useConfigStore = create<ConfigState>((set, get) => ({
  config: null,
  estate: [],
  approvals: { ...DEFAULT_APPROVALS },
  loading: false,
  error: null,
  dirty: false,
  validation: null,
  validating: false,
  validationProgress: null,
  validationError: null,
  validationStartedAtUtc: null,
  validationLastResponseAtUtc: null,
  validationRequestId: 0,
  signingIn: false,
  fresh: false,
  scopeDefaultsInitialized: false,

  bootstrap: async (fresh = get().fresh) => {
    if (get().loading) return;
    const request = ++bootstrapRequest;
    set({ loading: true, error: null, fresh });
    try {
      const backend = getBackend();
      const existingConfig = get().config;
      const [estateResult, configResult] = await Promise.allSettled([
        backend.discoverEstate(),
        existingConfig ? Promise.resolve(existingConfig) : backend.loadDefaultConfig(),
      ]);
      if (request !== bootstrapRequest) return;
      if (configResult.status === 'rejected') throw configResult.reason;
      const currentConfig = get().config;
      let loadedConfig = currentConfig ?? (fresh ? freshConfig(configResult.value) : configResult.value);
      if (!currentConfig) {
        loadedConfig = clone(loadedConfig);
        migrateLegacyDeepDiveTargets(loadedConfig);
        loadedConfig.databricks.allowSqlWarehouseAutoStart = false;
      }
      const estate = estateResult.status === 'fulfilled' ? estateResult.value : [];
      const applyScopeDefaults = !get().scopeDefaultsInitialized && !fresh && estateResult.status === 'fulfilled';
      if (applyScopeDefaults) {
        loadedConfig = clone(loadedConfig);
        const previousWorkspaces = loadedConfig.databricks.workspaces;
        const existingGroupIds = loadedConfig.azure.resourceGroupIds ?? loadedConfig.azure.subscriptions.flatMap(
          (subscriptionId) => loadedConfig.azure.resourceGroups.map((name) => `/subscriptions/${subscriptionId}/resourceGroups/${name}`),
        );
        setSelectedResourceGroups(loadedConfig, estate, [
          ...existingGroupIds,
          ...workspaceResourceGroupIds(estate.filter((sub) => loadedConfig.azure.subscriptions.includes(sub.subscriptionId))),
        ]);
        // Incomplete discovery must not discard existing workspace targets.
        const workspaceIds = new Set(loadedConfig.databricks.workspaces.map((workspace) => workspace.workspaceId));
        loadedConfig.databricks.workspaces.push(...previousWorkspaces.filter((workspace) => !workspaceIds.has(workspace.workspaceId)));
      }
      set({
        estate,
        config: loadedConfig,
        scopeDefaultsInitialized: get().scopeDefaultsInitialized || estateResult.status === 'fulfilled',
        approvals: currentConfig && warehouseScopeKey(currentConfig) === warehouseScopeKey(loadedConfig) ? get().approvals : {
          ...get().approvals,
          approveSqlWarehouseAutoStart: false,
        },
        loading: false,
        dirty: get().dirty || applyScopeDefaults,
        validation: applyScopeDefaults ? null : get().validation,
        validationError: applyScopeDefaults ? null : get().validationError,
        error:
          estateResult.status === 'rejected'
            ? estateResult.reason instanceof Error
              ? estateResult.reason.message
              : String(estateResult.reason)
            : null,
      });
    } catch (error) {
      if (request !== bootstrapRequest) return;
      set({ loading: false, error: error instanceof Error ? error.message : String(error) });
    }
  },

  signIn: async () => {
    const tenantId = get().config?.azure.tenantId;
    if (!tenantId) {
      set({ error: 'A tenant ID is required before Azure sign-in can start.' });
      return;
    }
    set({ signingIn: true, error: null });
    try {
      await getBackend().signIn(tenantId);
      set({ signingIn: false });
      await get().bootstrap();
    } catch (error) {
      set({
        signingIn: false,
        error: error instanceof Error ? error.message : String(error),
      });
    }
  },

  patch: (mutate) => {
    const current = get().config;
    if (!current) return;
    const draft = clone(current);
    mutate(draft);
    const warehousesChanged = warehouseScopeKey(current) !== warehouseScopeKey(draft);
    if (warehousesChanged) draft.databricks.allowSqlWarehouseAutoStart = false;
    set({
      config: draft, dirty: true, validation: null, validationError: null,
      approvals: warehousesChanged ? { ...get().approvals, approveSqlWarehouseAutoStart: false } : get().approvals,
    });
  },

  setApproval: (key, value) => {
    set({ approvals: { ...get().approvals, [key]: value }, validation: null, validationError: null });
  },

  toggleSubscription: (subscriptionId) => {
    const estate = get().estate;
    const subscription = estate.find((sub) => sub.subscriptionId === subscriptionId);
    if (!subscription) {
      set({ error: 'The selected subscription is no longer in discovery. Retry discovery before changing scope.' });
      return;
    }
    get().patch((draft) => {
      const selected = new Set(draft.azure.subscriptions);
      let groupIds = selectedResourceGroupIds(draft, estate);
      if (selected.has(subscriptionId)) {
        selected.delete(subscriptionId);
        const prefix = `/subscriptions/${subscriptionId}/`.toLowerCase();
        groupIds = groupIds.filter((id) => !id.toLowerCase().startsWith(prefix));
      } else {
        selected.add(subscriptionId);
        groupIds.push(...workspaceResourceGroupIds([subscription]));
      }
      draft.azure.subscriptions = [...selected];
      draft.azure.costScopes = draft.azure.subscriptions.map((id) => `/subscriptions/${id}`);
      draft.azure.costScope = draft.azure.costScopes.length === 1 ? draft.azure.costScopes[0] : '';
      setSelectedResourceGroups(draft, estate, groupIds);
    });
  },

  toggleResourceGroup: (subscriptionId, name) => {
    const estate = get().estate;
    const group = estate.find((sub) => sub.subscriptionId === subscriptionId)?.resourceGroups.find((item) => item.name === name);
    if (!group || !get().config?.azure.subscriptions.includes(subscriptionId)) {
      set({ error: 'The resource group must belong to a selected, discovered subscription.' });
      return;
    }
    get().patch((draft) => {
      const selected = new Set(selectedResourceGroupIds(draft, estate).map((id) => id.toLowerCase()));
      const groupId = group.resourceGroupId.toLowerCase();
      if (selected.has(groupId)) {
        selected.delete(groupId);
      } else {
        selected.add(groupId);
      }
      setSelectedResourceGroups(draft, estate, [...selected]);
    });
  },

  toggleWorkspace: (workspaceId) => {
    get().patch((draft) => {
      const workspace = draft.databricks.workspaces.find((w) => w.workspaceId === workspaceId);
      if (workspace) workspace.include = !workspace.include;
    });
  },

  setWarehouse: (workspaceId, warehouseId) => {
    get().patch((draft) => {
      const workspace = draft.databricks.workspaces.find((w) => w.workspaceId === workspaceId);
      if (!workspace) return;
      delete draft.databricks.sqlWarehouseId;
      if (warehouseId) workspace.sqlWarehouseId = warehouseId;
      else {
        workspace.sqlWarehouseId = '';
        if (!draft.databricks.workspaces.some((item) => item.sqlWarehouseId)) {
          draft.databricks.allowSqlWarehouseAutoStart = false;
        }
      }
    });
    if (!warehouseId && !get().config?.databricks.workspaces.some((item) => item.sqlWarehouseId)) {
      set({
        approvals: {
          ...get().approvals,
          approveSqlWarehouseAutoStart: false,
        },
      });
    }
  },

  validate: async () => {
    const { config, approvals } = get();
    if (usePermissionStore.getState().busy) {
      const message = 'Permission setup is still active or its outcome is unknown. Check its status before validation.';
      set({ validationError: message });
      throw new Error(message);
    }
    if (!config) throw new Error('Configuration has not been loaded yet.');
    if (get().validating) throw new Error('Validation is already running.');
    const requestId = get().validationRequestId + 1;
    set({
      validating: true, validation: null, validationError: null, validationProgress: null,
      validationStartedAtUtc: new Date().toISOString(), validationLastResponseAtUtc: null,
      validationRequestId: requestId,
    });
    try {
      const localReport = validateConfiguration({ config, approvals, estate: get().estate, environmentChecks: [] });
      if (!localReport.canRun) {
        set({ validation: localReport, validating: false, validationStartedAtUtc: null });
        return localReport;
      }
      const report = await getBackend().validate(config, approvals, (progress) => {
        if (get().validationRequestId === requestId) {
          set({ validationProgress: progress, validationLastResponseAtUtc: new Date().toISOString() });
        }
      });
      if (get().validationRequestId !== requestId) return report;
      if (get().config !== config || get().approvals !== approvals) {
        throw new Error('Configuration changed while checks were running. Run validation again for the new selection.');
      }
      set({ validation: report, validating: false, validationError: null });
      return report;
    } catch (error) {
      if (get().validationRequestId === requestId) {
        set({ validating: false, validationError: error instanceof Error ? error.message : String(error) });
      }
      throw error;
    }
  },

  reset: () => {
    bootstrapRequest++;
    set({
      config: null,
      estate: [],
      approvals: { ...DEFAULT_APPROVALS },
      loading: false,
      error: null,
      dirty: false,
      validation: null,
      validating: false,
      validationProgress: null,
      validationError: null,
      validationStartedAtUtc: null,
      validationLastResponseAtUtc: null,
      validationRequestId: get().validationRequestId + 1,
      signingIn: false,
      fresh: false,
      scopeDefaultsInitialized: false,
    });
  },

  resetValidation: () => set({ validation: null, validationError: null, validationProgress: null }),
}));

/** Workspaces in the current selection, joined with discovery metadata. */
export function selectIncludedWorkspaces(state: ConfigState) {
  return state.config?.databricks.workspaces.filter((w) => w.include) ?? [];
}
