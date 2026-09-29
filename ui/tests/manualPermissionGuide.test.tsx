import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { PermissionSetupPanel } from '@/features/validate/PermissionSetupPanel';
import { manualPermissionCommands, VERIFY_PIPELINE_SQL } from '@/features/validate/manualPermissionCommands';
import { MockAssessmentBackend } from '@/api/mockBackend';
import { setBackend } from '@/api';
import type { PermissionSetup } from '@/api/backend';
import { useConfigStore, useRunStore } from '@/state';
import { usePermissionStore } from '@/state/permissionStore';

let job: PermissionSetup;
let backend: MockAssessmentBackend;
let copy: ReturnType<typeof vi.fn>;
const accountId = '11111111-2222-3333-4444-555555555555';
const report = { generatedAtUtc: '', checks: [], blockerCount: 0, warningCount: 0, canRun: true, requiresSqlWarehouseApproval: false };
const refresh = usePermissionStore.getState().refresh;

beforeEach(async () => {
  sessionStorage.clear();
  useConfigStore.getState().reset();
  useRunStore.getState().reset();
  usePermissionStore.setState({ job: null, error: null, busy: false, requesting: false, refresh: vi.fn().mockResolvedValue(undefined) });
  backend = new MockAssessmentBackend();
  setBackend(backend);
  await useConfigStore.getState().bootstrap();
  const config = useConfigStore.getState().config!;
  useConfigStore.setState({ config: { ...config, databricks: { ...config.databricks, accountId, accountHost: 'accounts.azuredatabricks.net' } } });
  const workspace = config.databricks.workspaces[0];
  job = {
    setupId: 'b'.repeat(32), status: 'completed', principal: 'verified@example.test',
    workspaceId: workspace.workspaceId, workspaceName: workspace.name, workspaceUrl: workspace.workspaceUrl,
    warehouseId: workspace.sqlWarehouseId!, accessVerified: true, grants: [], error: null,
    expiresAtUtc: null, createdAtUtc: '',
  };
  usePermissionStore.setState({ job });
  copy = vi.fn().mockResolvedValue(undefined);
  vi.stubGlobal('navigator', { clipboard: { writeText: copy } });
  vi.spyOn(backend, 'previewPermissionSetup');
  vi.spyOn(backend, 'applyPermissionSetup');
  vi.spyOn(backend, 'validate').mockResolvedValue(report);
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  sessionStorage.clear();
  usePermissionStore.setState({ job: null, error: null, busy: false, requesting: false, refresh });
  setBackend(null);
});

function openGuide() {
  fireEvent.click(screen.getByText('Manual permission repair commands'));
}

describe('manual permission guide', () => {
  it('copies the three exact read grants and verification without executing anything', async () => {
    render(<PermissionSetupPanel />);
    openGuide();
    expect(screen.getByText('Reference only - access already works')).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: 'Copy SQL grants' }));
    await screen.findByText('Copied SQL grants. Nothing was executed.');
    expect(copy).toHaveBeenLastCalledWith([
      'GRANT USE CATALOG ON CATALOG system TO `verified@example.test`;',
      'GRANT USE SCHEMA ON SCHEMA system.lakeflow TO `verified@example.test`;',
      'GRANT SELECT ON TABLE system.lakeflow.pipeline_update_timeline TO `verified@example.test`;',
    ].join('\n'));
    fireEvent.click(screen.getByRole('button', { name: 'Copy verification SQL' }));
    await screen.findByText('Copied verification SQL. Nothing was executed.');
    expect(copy).toHaveBeenLastCalledWith(VERIFY_PIPELINE_SQL);
    expect(backend.previewPermissionSetup).not.toHaveBeenCalled();
    expect(backend.applyPermissionSetup).not.toHaveBeenCalled();
    expect(backend.validate).not.toHaveBeenCalled();
  });

  it('offers guarded account-level setup after MANAGE denial, including the nested REST body', async () => {
    usePermissionStore.setState({ job: { ...job, status: 'failed', accessVerified: false, error: "PERMISSION_DENIED: User does not have MANAGE on Catalog 'system'." } });
    render(<PermissionSetupPanel />);
    openGuide();
    fireEvent.click(screen.getByText('Optional: resolve missing MANAGE with an Account Admin'));
    expect(screen.getByText('Broad, persistent administrator assignment')).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: 'Copy administrator PowerShell' }));
    await screen.findByText('Copied administrator PowerShell. Nothing was executed.');
    const command = copy.mock.calls[0][0] as string;
    expect(command).toContain(`$workspaceHost = '${job.workspaceUrl}'`);
    expect(command).toContain(`$expectedWorkspaceId = '${job.workspaceId}'`);
    expect(command).toContain(`$accountId = '${accountId}'`);
    expect(command).toContain('/current-metastore-assignment');
    expect(command).toContain("'account_admin' -notin");
    expect(command).toContain("$metastore.owner -ne 'System user'");
    expect(command).toContain('$latest.owner -ne $metastore.owner');
    expect(command).toContain('Read-Host');
    expect(command).toContain('@{ metastore_info = @{ owner = $principal } }');
    expect(command.match(/-Method Put/g)).toHaveLength(1);
    expect(command).not.toContain('-Method Patch');
    expect(command).toContain('$headers.Clear()');
    expect(backend.applyPermissionSetup).not.toHaveBeenCalled();
  });

  it('hides targeted commands until the current workspace and warehouse have a verified result', () => {
    render(<PermissionSetupPanel />);
    openGuide();
    act(() => useConfigStore.getState().setWarehouse(job.workspaceId, 'changed'));
    openGuide();
    expect(screen.getByText('Verify the selected target first')).toBeVisible();
    expect(screen.queryByRole('button', { name: 'Copy SQL grants' })).not.toBeInTheDocument();
  });

  it('requires account settings for administrator commands but still provides SQL grants', () => {
    const config = useConfigStore.getState().config!;
    useConfigStore.setState({ config: { ...config, databricks: { ...config.databricks, accountId: '', accountHost: '' } } });
    render(<PermissionSetupPanel />);
    openGuide();
    fireEvent.click(screen.getByText('Optional: resolve missing MANAGE with an Account Admin'));
    expect(screen.getByText('Account settings required')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Copy SQL grants' })).toBeEnabled();
    expect(screen.queryByRole('button', { name: 'Copy administrator PowerShell' })).not.toBeInTheDocument();
  });

  it.each([
    { status: 'unknown' as const, error: 'Transport lost', busy: true },
    { status: 'failed' as const, error: 'TABLE_OR_VIEW_NOT_FOUND', busy: false },
  ])('does not recommend changes for $status: $error', ({ status, error, busy }) => {
    usePermissionStore.setState({ job: { ...job, status, error, accessVerified: false }, busy });
    render(<PermissionSetupPanel />);
    openGuide();
    expect(screen.queryByRole('button', { name: 'Copy SQL grants' })).not.toBeInTheDocument();
  });

  it('surfaces clipboard failure and keeps selectable commands visible', async () => {
    copy.mockRejectedValue(new Error('Clipboard denied'));
    render(<PermissionSetupPanel />);
    openGuide();
    fireEvent.click(screen.getByRole('button', { name: 'Copy SQL grants' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Clipboard denied');
    expect(screen.getByLabelText('SQL grants')).toBeVisible();
    expect(screen.queryByText('Copied SQL grants. Nothing was executed.')).not.toBeInTheDocument();
  });

  it('escapes principal delimiters and rejects target or account injection', () => {
    const account = useConfigStore.getState().config!.databricks;
    const escaped = manualPermissionCommands({ ...job, principal: "o'neil`$admin@example.test" }, account);
    if ('error' in escaped) throw new Error(escaped.error);
    expect(escaped.sql).toContain("`o'neil``$admin@example.test`");
    expect(escaped.powershell).toContain("$principal = 'o''neil`$admin@example.test'");
    expect(manualPermissionCommands({ ...job, principal: 'bad\nname' }, account)).toHaveProperty('error');
    expect(manualPermissionCommands({ ...job, workspaceUrl: "evil.example'; attack" }, account)).toHaveProperty('error');
    expect(manualPermissionCommands(job, { ...account, accountHost: 'evil.example' })).toHaveProperty('adminIssue');
    expect(manualPermissionCommands(job, { ...account, accountId: "'; attack" })).toHaveProperty('adminIssue');
  });
});

describe('next step after green access checks', () => {
  it('requires full validation and does not run it on render', async () => {
    useConfigStore.getState().setApproval('approveSqlWarehouseAutoStart', true);
    const onRun = vi.fn();
    render(<PermissionSetupPanel onRun={onRun} />);
    const next = within(screen.getByRole('region', { name: 'Next steps after permission setup' }));
    expect(next.getByRole('button', { name: 'Continue to run' })).toBeDisabled();
    expect(backend.validate).not.toHaveBeenCalled();
    fireEvent.click(next.getByRole('button', { name: 'Run validation' }));
    await waitFor(() => expect(backend.validate).toHaveBeenCalledOnce());
    await waitFor(() => expect(next.getByRole('button', { name: 'Continue to run' })).toBeEnabled());
    fireEvent.click(next.getByRole('button', { name: 'Continue to run' }));
    expect(onRun).toHaveBeenCalledOnce();
    expect(backend.applyPermissionSetup).not.toHaveBeenCalled();
  });

  it('continues without revalidating, and canceling a rerun preserves the report', () => {
    useConfigStore.setState({ validation: report });
    const onRun = vi.fn();
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false);
    render(<PermissionSetupPanel onRun={onRun} />);
    fireEvent.click(screen.getByRole('button', { name: 'Re-run validation' }));
    expect(confirm).toHaveBeenCalledOnce();
    expect(useConfigStore.getState().validation).toBe(report);
    fireEvent.click(screen.getByRole('button', { name: 'Continue to run' }));
    expect(onRun).toHaveBeenCalledOnce();
    expect(backend.validate).not.toHaveBeenCalled();
  });

  it('explains running validation and prevents duplicate validation or continuation', () => {
    useConfigStore.setState({ validation: report, validating: true });
    render(<PermissionSetupPanel onRun={vi.fn()} />);
    expect(screen.getByText(/Full validation is already running/)).toBeVisible();
    expect(screen.getByRole('button', { name: 'Validation running...' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Continue to run' })).toBeDisabled();
    expect(backend.validate).not.toHaveBeenCalled();
  });

  it('does not enable continuation with blockers, failed validation, or active assessment', () => {
    useConfigStore.setState({ validation: { ...report, blockerCount: 1, canRun: false } });
    render(<PermissionSetupPanel onRun={vi.fn()} />);
    expect(screen.getByRole('button', { name: 'Continue to run' })).toBeDisabled();
    act(() => useConfigStore.setState({ validation: report, validationError: 'Status lost' }));
    expect(screen.getByRole('button', { name: 'Continue to run' })).toBeDisabled();
    act(() => {
      useConfigStore.setState({ validationError: null });
      useRunStore.setState({ phase: 'collecting' });
    });
    expect(screen.getByRole('button', { name: 'Continue to run' })).toBeDisabled();
  });
});
