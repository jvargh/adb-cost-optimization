import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { defaultWarehouse } from '@/lib/scopeSelection';
import { MockAssessmentBackend } from '@/api/mockBackend';
import { setBackend } from '@/api';
import { useConfigStore } from '@/state/configStore';
import type { DiscoveredWarehouse } from '@/types';

const warehouse = (id: string, size: string, state: DiscoveredWarehouse['state']): DiscoveredWarehouse =>
  ({ id, name: id, size, state, serverless: true });

describe('warehouse defaults', () => {
  beforeEach(() => useConfigStore.getState().reset());
  afterEach(() => setBackend(null));

  it('prefers the smallest running warehouse even when a smaller stopped one exists', () => {
    const choices = [warehouse('stopped', '2X-Small', 'STOPPED'), warehouse('large', 'Large', 'RUNNING'), warehouse('small', 'Small', 'RUNNING')];
    expect(defaultWarehouse(choices)?.id).toBe('small');
    expect(choices.map((item) => item.id)).toEqual(['stopped', 'large', 'small']);
  });

  it('falls back to the smallest stopped warehouse with deterministic name and ID ties', () => {
    expect(defaultWarehouse([warehouse('z', 'Small', 'STOPPED'), warehouse('b', '2X-Small', 'STOPPED'), warehouse('a', '2X-Small', 'STOPPED')])?.id).toBe('a');
  });

  it('does not choose starting, deleted, or unrecognized-size warehouses', () => {
    expect(defaultWarehouse([warehouse('starting', '2X-Small', 'STARTING'), warehouse('deleted', '2X-Small', 'DELETED'), warehouse('unknown', 'Unknown', 'RUNNING')])).toBeUndefined();
    expect(defaultWarehouse([])).toBeUndefined();
  });

  it('preserves explicit None and chosen IDs on retry and clears consent when warehouse scope changes', async () => {
    const backend = new MockAssessmentBackend();
    setBackend(backend);
    await useConfigStore.getState().bootstrap();
    const store = useConfigStore.getState();
    const [first, second] = store.config!.databricks.workspaces;
    expect(store.approvals.approveSqlWarehouseAutoStart).toBe(false);
    store.setApproval('approveSqlWarehouseAutoStart', true);
    store.setWarehouse(first.workspaceId, undefined);
    expect(useConfigStore.getState().approvals.approveSqlWarehouseAutoStart).toBe(false);
    store.setWarehouse(second.workspaceId, 'manual-choice');
    await store.bootstrap();
    expect(useConfigStore.getState().config!.databricks.workspaces.map((item) => item.sqlWarehouseId)).toEqual(['', 'manual-choice']);
  });

  it('does not inherit a disk template approval when automatic defaults add warehouses', async () => {
    const backend = new MockAssessmentBackend();
    const template = await backend.loadDefaultConfig();
    template.databricks.allowSqlWarehouseAutoStart = true;
    backend.loadDefaultConfig = async () => template;
    setBackend(backend);
    await useConfigStore.getState().bootstrap();
    const state = useConfigStore.getState();
    expect(state.approvals.approveSqlWarehouseAutoStart).toBe(false);
    expect(state.config!.databricks.allowSqlWarehouseAutoStart).toBe(false);
    expect(state.config!.databricks.workspaces.every((workspace) => Boolean(workspace.sqlWarehouseId))).toBe(true);
  });
});
