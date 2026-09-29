import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { PermissionSetupPanel } from '@/features/validate/PermissionSetupPanel';
import { ValidatePage } from '@/features/validate/ValidatePage';
import { MockAssessmentBackend } from '@/api/mockBackend';
import { setBackend } from '@/api';
import type { PermissionSetup } from '@/api/backend';
import { BackendRequestError } from '@/api/backend';
import { useConfigStore, useRunStore } from '@/state';
import { usePermissionStore } from '@/state/permissionStore';

describe('confirmed permission setup', () => {
  let backend: MockAssessmentBackend;
  let preview: PermissionSetup;

  beforeEach(async () => {
    sessionStorage.clear();
    useConfigStore.getState().reset();
    useRunStore.getState().reset();
    usePermissionStore.setState({ job: null, error: null, busy: false, requesting: false });
    backend = new MockAssessmentBackend();
    setBackend(backend);
    await useConfigStore.getState().bootstrap();
    const workspace = useConfigStore.getState().config!.databricks.workspaces[0];
    preview = {
      setupId: 'a'.repeat(32), status: 'awaiting_confirmation', principal: 'verified@example.test',
      workspaceId: workspace.workspaceId, workspaceName: workspace.name,
      workspaceUrl: workspace.workspaceUrl, warehouseId: workspace.sqlWarehouseId!,
      grants: [
        'GRANT USE CATALOG ON CATALOG system TO `verified@example.test`',
        'GRANT USE SCHEMA ON SCHEMA system.lakeflow TO `verified@example.test`',
        'GRANT SELECT ON TABLE system.lakeflow.pipeline_update_timeline TO `verified@example.test`',
      ].map((statement) => ({ statement, status: 'not_attempted' })),
      error: null, accessVerified: false, expiresAtUtc: '2099-01-01T00:00:00Z', createdAtUtc: '2026-09-28T00:00:00Z',
    };
    vi.spyOn(backend, 'previewPermissionSetup').mockResolvedValue(preview);
    vi.spyOn(backend, 'getPermissionSetup').mockResolvedValue(preview);
    vi.spyOn(backend, 'applyPermissionSetup').mockResolvedValue({
      ...preview, status: 'completed', accessVerified: true,
      grants: preview.grants.map((grant) => ({ ...grant, status: 'applied' })),
    });
    vi.spyOn(backend, 'validate');
  });
  afterEach(() => {
    cleanup();
    sessionStorage.clear();
    usePermissionStore.setState({ job: null, error: null, busy: false, requesting: false });
    setBackend(null);
    vi.restoreAllMocks();
  });

  async function showPreview() {
    render(<><ValidatePage onRun={vi.fn()} /><PermissionSetupPanel /></>);
    expect(screen.getByRole('button', { name: 'Check access and preview grants' })).toBeDisabled();
    expect(screen.getByRole('checkbox', { name: /^Approve SQL Warehouse/ })).not.toBeChecked();
    fireEvent.click(screen.getByRole('checkbox', { name: /^Approve SQL Warehouse/ }));
    expect(backend.previewPermissionSetup).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Check access and preview grants' }));
    await screen.findByText('Verified assessment identity: verified@example.test');
    expect(screen.getByRole('button', { name: 'Apply these three grants' })).toBeDisabled();
    expect(backend.applyPermissionSetup).not.toHaveBeenCalled();
    expect(backend.validate).not.toHaveBeenCalled();
  }

  it('requires separate warehouse and exact-grant consent, and cancel makes no permission changes', async () => {
    await showPreview();
    for (const grant of preview.grants) expect(screen.getByText(`${grant.statement};`)).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: 'Cancel without granting' }));
    expect(backend.applyPermissionSetup).not.toHaveBeenCalled();
    expect(usePermissionStore.getState().job).toBeNull();
  });

  it('applies only after exact confirmation and never automatically revalidates', async () => {
    await showPreview();
    fireEvent.click(screen.getByRole('checkbox', { name: /^I confirm these exact three grants/ }));
    fireEvent.click(screen.getByRole('button', { name: 'Apply these three grants' }));
    await screen.findByText('Pipeline timeline SELECT access verified');
    expect(backend.applyPermissionSetup).toHaveBeenCalledExactlyOnceWith(preview.setupId, preview.principal, true);
    expect(backend.validate).not.toHaveBeenCalled();
    expect(useConfigStore.getState().validation).toBeNull();
  });

  it('invalidates confirmation when warehouse selection changes', async () => {
    await showPreview();
    fireEvent.click(screen.getByRole('checkbox', { name: /^I confirm these exact three grants/ }));
    act(() => useConfigStore.getState().setWarehouse(preview.workspaceId, 'another-warehouse'));
    expect(screen.getByText('Selection changed')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Apply these three grants' })).toBeDisabled();
    expect(useConfigStore.getState().approvals.approveSqlWarehouseAutoStart).toBe(false);
  });

  it('shows partial failure instead of marking access verified', async () => {
    vi.mocked(backend.applyPermissionSetup).mockResolvedValue({
      ...preview, status: 'failed', error: 'SELECT grant denied; earlier grants remain applied.',
      grants: preview.grants.map((grant, index) => ({ ...grant, status: index === 0 ? 'applied' : 'not_attempted' })),
    });
    await showPreview();
    fireEvent.click(screen.getByRole('checkbox', { name: /^I confirm these exact three grants/ }));
    fireEvent.click(screen.getByRole('button', { name: 'Apply these three grants' }));
    await screen.findByText('SELECT grant denied; earlier grants remain applied.');
    expect(screen.queryByText('Pipeline timeline SELECT access verified')).not.toBeInTheDocument();
  });

  it('does not resubmit after a lost response and recovers only by reading status', async () => {
    vi.mocked(backend.applyPermissionSetup).mockRejectedValue(new Error('Connection lost'));
    await showPreview();
    fireEvent.click(screen.getByRole('checkbox', { name: /^I confirm these exact three grants/ }));
    fireEvent.click(screen.getByRole('button', { name: 'Apply these three grants' }));
    await screen.findByText(/application outcome is not verified/);
    expect(usePermissionStore.getState().busy).toBe(true);
    expect(screen.queryByText('Checking identity, read access, and setup status...')).not.toBeInTheDocument();
    expect(screen.queryByText('Applying only the confirmed grants and verifying SELECT access...')).not.toBeInTheDocument();
    expect(screen.getByText(/Status checking has stopped/)).toBeVisible();
    vi.mocked(backend.getPermissionSetup).mockResolvedValue({ ...preview, status: 'completed', accessVerified: true });
    fireEvent.click(screen.getByRole('button', { name: 'Check setup status' }));
    await screen.findByText('Pipeline timeline SELECT access verified');
    expect(backend.applyPermissionSetup).toHaveBeenCalledTimes(1);
    await waitFor(() => expect(usePermissionStore.getState().busy).toBe(false));
  });

  it('recovers a rejected stale apply with a fresh preview and no endless spinner', async () => {
    vi.mocked(backend.applyPermissionSetup).mockRejectedValue(new BackendRequestError(404, 'Permission setup is unavailable.'));
    await showPreview();
    fireEvent.click(screen.getByRole('checkbox', { name: /^I confirm these exact three grants/ }));
    fireEvent.click(screen.getByRole('button', { name: 'Apply these three grants' }));
    await screen.findByText(/This request submitted no new grants/);
    expect(usePermissionStore.getState()).toMatchObject({ busy: false, requesting: false, job: null });
    expect(sessionStorage.getItem('assessment-permission-setup-id')).toBeNull();
    expect(screen.getByRole('button', { name: 'Check access and preview grants' })).toBeEnabled();
    expect(screen.queryByRole('button', { name: 'Check setup status' })).not.toBeInTheDocument();
    expect(screen.queryByText('Checking identity, read access, and setup status...')).not.toBeInTheDocument();
    expect(backend.previewPermissionSetup).toHaveBeenCalledOnce();
    expect(backend.applyPermissionSetup).toHaveBeenCalledOnce();
  });

  it('never treats a lost polling response as a rejected apply', async () => {
    vi.mocked(backend.applyPermissionSetup).mockResolvedValue({ ...preview, status: 'applying' });
    vi.mocked(backend.getPermissionSetup).mockRejectedValue(new BackendRequestError(404, 'Host restarted.'));
    await showPreview();
    fireEvent.click(screen.getByRole('checkbox', { name: /^I confirm these exact three grants/ }));
    fireEvent.click(screen.getByRole('button', { name: 'Apply these three grants' }));
    await screen.findByText(/application outcome is not verified/);
    expect(usePermissionStore.getState()).toMatchObject({ busy: true, requesting: false });
    expect(screen.queryByText(/This request submitted no new grants/)).not.toBeInTheDocument();
    expect(screen.queryByText('Applying only the confirmed grants and verifying SELECT access...')).not.toBeInTheDocument();
    expect(backend.applyPermissionSetup).toHaveBeenCalledOnce();
  });

  it('reads the explicit expiry rejection and allows a new preview without spinning', async () => {
    vi.mocked(backend.applyPermissionSetup).mockRejectedValue(new BackendRequestError(409, 'The identity preview expired.'));
    vi.mocked(backend.getPermissionSetup).mockResolvedValue({
      ...preview, status: 'failed', error: 'The identity preview expired. No grants were submitted.',
    });
    await showPreview();
    fireEvent.click(screen.getByRole('checkbox', { name: /^I confirm these exact three grants/ }));
    fireEvent.click(screen.getByRole('button', { name: 'Apply these three grants' }));
    await screen.findByText('The identity preview expired. No grants were submitted.');
    expect(usePermissionStore.getState()).toMatchObject({ busy: false, requesting: false });
    expect(screen.getByRole('button', { name: 'Check access and preview grants' })).toBeEnabled();
    expect(backend.applyPermissionSetup).toHaveBeenCalledOnce();
    expect(backend.getPermissionSetup).toHaveBeenCalledOnce();
  });

  it('restores an unknown outcome as paused rather than showing permanent progress', async () => {
    sessionStorage.setItem('assessment-permission-setup-id', preview.setupId);
    sessionStorage.setItem('assessment-permission-setup-phase', 'apply');
    vi.mocked(backend.getPermissionSetup).mockResolvedValue({
      ...preview, status: 'unknown', error: 'The host restarted during permission setup.',
    });
    render(<PermissionSetupPanel />);
    await screen.findByText('The host restarted during permission setup.');
    expect(usePermissionStore.getState()).toMatchObject({ busy: true, requesting: false });
    expect(screen.queryByText('Checking identity, read access, and setup status...')).not.toBeInTheDocument();
    expect(backend.applyPermissionSetup).not.toHaveBeenCalled();
  });

  it('recovers a missing preview after refresh but preserves an unknown apply outcome', async () => {
    sessionStorage.setItem('assessment-permission-setup-id', preview.setupId);
    sessionStorage.setItem('assessment-permission-setup-phase', 'preview');
    vi.mocked(backend.getPermissionSetup).mockRejectedValue(new BackendRequestError(404, 'Host restarted.'));
    render(<PermissionSetupPanel />);
    await screen.findByText(/This request submitted no new grants/);
    expect(usePermissionStore.getState().busy).toBe(false);
    expect(backend.applyPermissionSetup).not.toHaveBeenCalled();
    sessionStorage.setItem('assessment-permission-setup-id', preview.setupId);
    sessionStorage.setItem('assessment-permission-setup-phase', 'apply');
    await act(() => usePermissionStore.getState().refresh());
    expect(usePermissionStore.getState()).toMatchObject({ busy: true, requesting: false });
    expect(screen.getByText(/Status checking stopped/)).toBeVisible();
  });

  it('preserves completed validation when only previewing or canceling grants', async () => {
    const report = { generatedAtUtc: '', checks: [], blockerCount: 0, warningCount: 0, canRun: true, requiresSqlWarehouseApproval: false };
    render(<><ValidatePage onRun={vi.fn()} /><PermissionSetupPanel /></>);
    fireEvent.click(screen.getByRole('checkbox', { name: /^Approve SQL Warehouse/ }));
    act(() => useConfigStore.setState({ validation: report }));
    fireEvent.click(screen.getByRole('button', { name: 'Check access and preview grants' }));
    await screen.findByText('Verified assessment identity: verified@example.test');
    fireEvent.click(screen.getByRole('button', { name: 'Cancel without granting' }));
    expect(useConfigStore.getState().validation).toBe(report);
  });

  it('reports a denied grant as failed with administrator guidance, not unknown progress', async () => {
    vi.mocked(backend.applyPermissionSetup).mockResolvedValue({
      ...preview, status: 'failed',
      error: "PERMISSION_DENIED: User does not have MANAGE on Catalog 'system'. No grants were confirmed applied.",
      grants: preview.grants.map((grant, index) => ({ ...grant, status: index === 0 ? 'failed' : 'not_attempted' })),
    });
    await showPreview();
    fireEvent.click(screen.getByRole('checkbox', { name: /^I confirm these exact three grants/ }));
    fireEvent.click(screen.getByRole('button', { name: 'Apply these three grants' }));
    await screen.findByText('An authorized Unity Catalog administrator is required');
    expect(screen.getByText('Status: failed; Databricks rejected this grant')).toBeVisible();
    expect(screen.queryByText(/outcome not yet verified/)).not.toBeInTheDocument();
    expect(usePermissionStore.getState()).toMatchObject({ busy: false, requesting: false });
  });

  it('shows already accessible without grant controls or invalidating the completed validation', async () => {
    vi.mocked(backend.previewPermissionSetup).mockResolvedValue({
      ...preview, status: 'completed', grants: [], accessVerified: true, expiresAtUtc: null,
    });
    useConfigStore.getState().setApproval('approveSqlWarehouseAutoStart', true);
    const report = { generatedAtUtc: '', checks: [], blockerCount: 0, warningCount: 0, canRun: true, requiresSqlWarehouseApproval: false };
    useConfigStore.setState({ validation: report });
    render(<><ValidatePage onRun={vi.fn()} /><PermissionSetupPanel /></>);
    fireEvent.click(screen.getByRole('button', { name: 'Check access and preview grants' }));
    await screen.findByText('Already accessible - no grants needed');
    expect(screen.queryByRole('button', { name: 'Apply these three grants' })).not.toBeInTheDocument();
    expect(screen.queryByRole('checkbox', { name: /^I confirm these exact three grants/ })).not.toBeInTheDocument();
    expect(backend.applyPermissionSetup).not.toHaveBeenCalled();
    expect(backend.validate).not.toHaveBeenCalled();
    expect(useConfigStore.getState().validation).toBe(report);
    expect(usePermissionStore.getState()).toMatchObject({ busy: false, requesting: false });
  });

  it('retains denied access evidence in the separately confirmed grant preview', async () => {
    vi.mocked(backend.previewPermissionSetup).mockResolvedValue({
      ...preview, accessCheckError: 'INSUFFICIENT_PERMISSIONS: SELECT on pipeline_update_timeline',
    });
    await showPreview();
    expect(screen.getByText('Pipeline timeline read access is missing')).toBeVisible();
    fireEvent.click(screen.getByText('Access check details'));
    expect(screen.getByText('INSUFFICIENT_PERMISSIONS: SELECT on pipeline_update_timeline')).toBeVisible();
    expect(backend.applyPermissionSetup).not.toHaveBeenCalled();
  });

  it('does not offer grants when read access is unverified for a non-permission failure', async () => {
    vi.mocked(backend.previewPermissionSetup).mockResolvedValue({
      ...preview, status: 'failed', grants: [], error: 'TABLE_OR_VIEW_NOT_FOUND',
    });
    useConfigStore.getState().setApproval('approveSqlWarehouseAutoStart', true);
    render(<PermissionSetupPanel />);
    fireEvent.click(screen.getByRole('button', { name: 'Check access and preview grants' }));
    await screen.findByText('TABLE_OR_VIEW_NOT_FOUND');
    expect(screen.queryByRole('button', { name: 'Apply these three grants' })).not.toBeInTheDocument();
    expect(screen.queryByText('Already accessible - no grants needed')).not.toBeInTheDocument();
    expect(usePermissionStore.getState()).toMatchObject({ busy: false, requesting: false });
  });
});
