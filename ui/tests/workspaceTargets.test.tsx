import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ConfigurePage } from '@/features/configure/ConfigurePage';
import { MockAssessmentBackend } from '@/api/mockBackend';
import { setBackend } from '@/api';
import { useConfigStore } from '@/state/configStore';
import { validateConfiguration } from '@/lib/validation';
import type { AssessmentConfig, SubscriptionOption } from '@/types';
import defaultConfig from '../mock/fixtures/default-config.json';
import estateFixture from '../mock/fixtures/estate.json';

describe('workspace-specific deep dives and warehouse guidance', () => {
  let backend: MockAssessmentBackend;
  let template: AssessmentConfig;
  let estate: SubscriptionOption[];

  beforeEach(() => {
    useConfigStore.getState().reset();
    backend = new MockAssessmentBackend();
    template = structuredClone(defaultConfig) as AssessmentConfig;
    estate = structuredClone(estateFixture) as SubscriptionOption[];
    template.databricks.deepDiveJobRunIds = ['101'];
    template.databricks.deepDiveTableNames = ['catalog.schema.table'];
    vi.spyOn(backend, 'loadDefaultConfig').mockResolvedValue(template);
    vi.spyOn(backend, 'discoverEstate').mockResolvedValue(estate);
    setBackend(backend);
  });
  afterEach(() => { setBackend(null); vi.restoreAllMocks(); });

  it('migrates single-workspace legacy targets before expanding scope and preserves edits on retry', async () => {
    const original = structuredClone(template);
    const validate = vi.spyOn(backend, 'validate');
    await useConfigStore.getState().bootstrap();
    render(<ConfigurePage onValidate={vi.fn()} />);
    expect(screen.getByRole('textbox', { name: /^Job run IDs - dbw-platform-prod\b/ })).toHaveValue('101');
    expect(screen.getByRole('textbox', { name: /^Table names - dbw-platform-prod\b/ })).toHaveValue('catalog.schema.table');
    expect(screen.getByRole('textbox', { name: /^Job run IDs - dbw-platform-nonprod\b/ })).toHaveValue('');
    expect(screen.getByRole('textbox', { name: /^Table names - dbw-platform-nonprod\b/ })).toHaveValue('');
    fireEvent.change(screen.getByRole('textbox', { name: /^Job run IDs - dbw-platform-nonprod\b/ }), { target: { value: '202\n 203 ' } });
    expect(useConfigStore.getState().config!.databricks.workspaces[1].deepDiveJobRunIds).toEqual(['202', '203']);
    fireEvent.change(screen.getByRole('textbox', { name: /^Job run IDs - dbw-platform-prod\b/ }), { target: { value: '' } });
    const edited = structuredClone(useConfigStore.getState().config);
    await act(async () => { await useConfigStore.getState().bootstrap(); });
    expect(useConfigStore.getState().config).toEqual(edited);
    expect(useConfigStore.getState().config!.databricks.deepDiveJobRunIds).toEqual([]);
    expect(useConfigStore.getState().config!.databricks.deepDiveTableNames).toEqual([]);
    expect(template).toEqual(original);
    expect(validate).not.toHaveBeenCalled();
  });

  it('requires explicit assignment of ambiguous imported targets instead of fanning them out', async () => {
    const other = estate[0].resourceGroups.find((group) => group.name.endsWith('nonprod'))!.workspaces[0];
    template.databricks.workspaces.push({ ...other, include: true });
    await useConfigStore.getState().bootstrap();
    render(<ConfigurePage onValidate={vi.fn()} />);
    expect(screen.getByText('Legacy deep-dive targets need a workspace')).toBeVisible();
    const before = useConfigStore.getState();
    expect(validateConfiguration({ config: before.config!, estate, approvals: before.approvals, environmentChecks: [] }).canRun).toBe(false);
    fireEvent.change(screen.getByRole('combobox', { name: 'Workspace for legacy targets' }), { target: { value: other.workspaceId } });
    expect(screen.queryByText('Legacy deep-dive targets need a workspace')).not.toBeInTheDocument();
    expect(screen.getByRole('textbox', { name: /^Job run IDs - dbw-platform-prod\b/ })).toHaveValue('');
    expect(screen.getByRole('textbox', { name: /^Job run IDs - dbw-platform-nonprod\b/ })).toHaveValue('101');
    const after = useConfigStore.getState();
    expect(validateConfiguration({ config: after.config!, estate, approvals: after.approvals, environmentChecks: [] }).checks
      .find((check) => check.id === 'deep-dive-targets')?.status).toBe('pass');
  });

  it('can explicitly clear ambiguous targets without dropping workspace scope', async () => {
    template.databricks.workspaces.push({ ...template.databricks.workspaces[0], workspaceId: 'other' });
    await useConfigStore.getState().bootstrap();
    render(<ConfigurePage onValidate={vi.fn()} />);
    const count = useConfigStore.getState().config!.databricks.workspaces.length;
    fireEvent.click(screen.getByRole('button', { name: 'Clear unassigned targets' }));
    expect(useConfigStore.getState().config!.databricks.deepDiveJobRunIds).toEqual([]);
    expect(useConfigStore.getState().config!.databricks.deepDiveTableNames).toEqual([]);
    expect(useConfigStore.getState().config!.databricks.workspaces).toHaveLength(count);
  });

  it('names missing warehouse selections without selecting or approving a warehouse', async () => {
    template.databricks.workspaces[0].sqlWarehouseId = 'existing-warehouse';
    estate[0].resourceGroups[2].workspaces[0].sqlWarehouses = [];
    await useConfigStore.getState().bootstrap();
    render(<ConfigurePage onValidate={vi.fn()} />);
    expect(screen.getByText('Not configured: dbw-platform-nonprod.')).toBeVisible();
    expect(screen.getAllByRole('combobox', { name: /^SQL Warehouse for system-table queries/ })[1]).toHaveValue('');
    expect(useConfigStore.getState().approvals.approveSqlWarehouseAutoStart).toBe(false);
  });
});
