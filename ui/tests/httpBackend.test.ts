import { HttpAssessmentBackend } from '@/api/httpBackend';
import type { AssessmentConfig } from '@/types';
import defaultConfig from '../mock/fixtures/default-config.json';

const config = defaultConfig as AssessmentConfig;

function response(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

describe('HTTP assessment backend', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('keeps permission preview and confirmed application separate from assessment routes', async () => {
    const fetchMock = vi.fn().mockImplementation(async () => response({ setupId: 'setup', status: 'awaiting_confirmation' }));
    vi.stubGlobal('fetch', fetchMock);
    const backend = new HttpAssessmentBackend();
    await backend.previewPermissionSetup(config.databricks.workspaces[0], true);
    expect(fetchMock).toHaveBeenLastCalledWith('/api/permission-setups', expect.objectContaining({
      method: 'POST', body: JSON.stringify({ workspace: config.databricks.workspaces[0], approveSqlWarehouseAutoStart: true }),
    }));
    await backend.applyPermissionSetup('setup', 'verified@example.test', true);
    expect(fetchMock).toHaveBeenLastCalledWith('/api/permission-setups/setup/apply', expect.objectContaining({
      method: 'POST', body: JSON.stringify({ principal: 'verified@example.test', confirmed: true, approveSqlWarehouseAutoStart: true }),
    }));
    await backend.getPermissionSetup('setup');
    expect(fetchMock).toHaveBeenLastCalledWith('/api/permission-setups/setup', expect.objectContaining({ signal: expect.any(AbortSignal) }));
  });

  it('loads the default configuration from the local API', async () => {
    const fetchMock = vi.fn().mockResolvedValue(response(config));
    vi.stubGlobal('fetch', fetchMock);

    const loaded = await new HttpAssessmentBackend().loadDefaultConfig();

    expect(loaded.customerId).toBe(config.customerId);
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/config/default',
      expect.objectContaining({ headers: expect.any(Headers) }),
    );
  });

  it('starts and cancels a run through the local API', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response({ runId: 'run-123' }))
      .mockResolvedValueOnce(response({ status: 'canceling' }));
    vi.stubGlobal('fetch', fetchMock);
    const backend = new HttpAssessmentBackend();

    const handle = await backend.startRun(config, {
      acknowledgedReadOnly: true,
      approveSqlWarehouseAutoStart: false,
      continueOnCollectorError: true,
    });
    await handle.cancel();

    expect(handle.runId).toBe('run-123');
    expect(fetchMock).toHaveBeenLastCalledWith(
      '/api/runs/run-123',
      expect.objectContaining({ method: 'DELETE' }),
    );
  });

  it('surfaces the server error message', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response({ error: 'Run not found.' }, 404)));

    await expect(new HttpAssessmentBackend().loadResults('missing')).rejects.toThrow(
      'Run not found.',
    );
  });

  it('preserves the HTTP status so rejected setup requests differ from lost connections', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response({ error: 'Preview is unavailable.' }, 404)));
    await expect(new HttpAssessmentBackend().applyPermissionSetup('missing', 'verified@example.test', true))
      .rejects.toMatchObject({ name: 'BackendRequestError', status: 404, message: 'Preview is unavailable.' });
  });

  it('deletes only the confirmed snapshot IDs without calling the run cancellation route', async () => {
    const result = { deletedRunIds: ['one'], failures: [{ runId: 'two', message: 'Active run' }] };
    const fetchMock = vi.fn().mockResolvedValue(response(result));
    vi.stubGlobal('fetch', fetchMock);
    expect(await new HttpAssessmentBackend().deleteSnapshots(['one', 'two'])).toEqual(result);
    expect(fetchMock).toHaveBeenCalledWith('/api/snapshots/delete', expect.objectContaining({
      method: 'POST', body: JSON.stringify({ runIds: ['one', 'two'], confirmed: true }),
    }));
  });

  it('polls real progress and returns only the terminal report', async () => {
    const report = { checks: [], canRun: true };
    const page = { validationId: 'abc', status: 'running', steps: [] };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(response(page))
      .mockResolvedValueOnce(response({ ...page, status: 'completed', report }));
    vi.stubGlobal('fetch', fetchMock);
    const onProgress = vi.fn();
    const actual = await new HttpAssessmentBackend().validate(config, {
      acknowledgedReadOnly: true, approveSqlWarehouseAutoStart: false, continueOnCollectorError: true,
    }, onProgress);
    expect(actual).toEqual(report);
    expect(onProgress).toHaveBeenCalledTimes(2);
    expect(fetchMock).toHaveBeenLastCalledWith('/api/validations/abc', expect.objectContaining({ signal: expect.any(AbortSignal) }));
  });

  it('surfaces a lost connection instead of silently restarting validation', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(response({ validationId: 'abc', status: 'running', steps: [] }))
      .mockRejectedValueOnce(new TypeError('Failed to fetch'));
    vi.stubGlobal('fetch', fetchMock);
    await expect(new HttpAssessmentBackend().validate(config, {
      acknowledgedReadOnly: true, approveSqlWarehouseAutoStart: false, continueOnCollectorError: true,
    })).rejects.toThrow('Validation may still be running');
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it('rejects a terminal response that is missing the validation report', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response({ status: 'completed', report: null })));
    await expect(new HttpAssessmentBackend().validate(config, {
      acknowledgedReadOnly: true, approveSqlWarehouseAutoStart: false, continueOnCollectorError: true,
    })).rejects.toThrow('without a report');
  });
});
