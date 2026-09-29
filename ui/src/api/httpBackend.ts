import type {
  AssessmentConfig,
  AssessmentResults,
  RunSummary,
  SubscriptionOption,
  ValidationReport,
  ValidationProgress,
  WorkspaceSelection,
} from '@/types';
import type {
  ArtifactPayload,
  AssessmentBackend,
  RunApprovals,
  RunEvent,
  RunHandle,
  SnapshotDeletion,
  PermissionSetup,
} from './backend';
import { BackendRequestError } from './backend';

interface EventPage {
  events: RunEvent[];
  nextCursor: number;
  terminal: boolean;
}

interface ApiError {
  error?: string;
}

const POLL_INTERVAL_MS = 750;

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (init?.body) headers.set('Content-Type', 'application/json');
  const response = await fetch(path, { ...init, headers });
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      const payload = (await response.json()) as ApiError;
      if (payload.error) message = payload.error;
    } catch {
      // The status text remains the most useful available error.
    }
    throw new BackendRequestError(response.status, message);
  }
  return (await response.json()) as T;
}

class HttpRunHandle implements RunHandle {
  private listeners = new Set<(event: RunEvent) => void>();
  private cursor = 0;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private stopped = false;

  constructor(readonly runId: string) {}

  subscribe(listener: (event: RunEvent) => void): () => void {
    this.listeners.add(listener);
    if (!this.timer && !this.stopped) void this.poll();
    return () => {
      this.listeners.delete(listener);
      if (this.listeners.size === 0 && this.timer) {
        clearTimeout(this.timer);
        this.timer = null;
      }
    };
  }

  async cancel(): Promise<void> {
    await api<{ status: string }>(`/api/runs/${encodeURIComponent(this.runId)}`, {
      method: 'DELETE',
    });
  }

  private async poll(): Promise<void> {
    if (this.stopped || this.listeners.size === 0) return;
    try {
      const page = await api<EventPage>(
        `/api/runs/${encodeURIComponent(this.runId)}/events?after=${this.cursor}`,
      );
      this.cursor = page.nextCursor;
      for (const event of page.events) {
        for (const listener of this.listeners) listener(event);
      }
      this.stopped = page.terminal;
    } catch (error) {
      const event: RunEvent = {
        type: 'failed',
        message: error instanceof Error ? error.message : String(error),
        atUtc: new Date().toISOString(),
      };
      for (const listener of this.listeners) listener(event);
      this.stopped = true;
    }
    if (!this.stopped && this.listeners.size > 0) {
      this.timer = setTimeout(() => void this.poll(), POLL_INTERVAL_MS);
    }
  }
}

export class HttpAssessmentBackend implements AssessmentBackend {
  readonly id = 'local-assessment-api';
  readonly isMock = false;

  discoverEstate(): Promise<SubscriptionOption[]> {
    return api('/api/estate');
  }

  signIn(tenantId: string): Promise<void> {
    return api('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ tenantId }),
    });
  }

  loadDefaultConfig(): Promise<AssessmentConfig> {
    return api('/api/config/default');
  }

  previewPermissionSetup(workspace: WorkspaceSelection, approved: boolean): Promise<PermissionSetup> {
    return api('/api/permission-setups', {
      method: 'POST', signal: AbortSignal.timeout(15000),
      body: JSON.stringify({ workspace, approveSqlWarehouseAutoStart: approved }),
    });
  }

  getPermissionSetup(setupId: string): Promise<PermissionSetup> {
    return api(`/api/permission-setups/${encodeURIComponent(setupId)}`, { signal: AbortSignal.timeout(15000) });
  }

  applyPermissionSetup(setupId: string, principal: string, approved: boolean): Promise<PermissionSetup> {
    return api(`/api/permission-setups/${encodeURIComponent(setupId)}/apply`, {
      method: 'POST', signal: AbortSignal.timeout(15000),
      body: JSON.stringify({ principal, confirmed: true, approveSqlWarehouseAutoStart: approved }),
    });
  }

  async validate(
    config: AssessmentConfig,
    approvals: RunApprovals,
    onProgress?: (progress: ValidationProgress) => void,
  ): Promise<ValidationReport> {
    type ValidationPage = ValidationProgress & { report: ValidationReport | null; error: string | null };
    const request = async (path: string, init?: RequestInit) => {
      try {
        return await api<ValidationPage>(path, { ...init, signal: AbortSignal.timeout(15000) });
      } catch (error) {
        const detail = error instanceof Error ? error.message : String(error);
        throw new Error(
          `Cannot get validation status from the local server: ${detail}. ` +
          'Validation may still be running. Check the launcher window before retrying; do not assume the checks passed.',
        );
      }
    };
    let page = await request('/api/validations', {
      method: 'POST',
      body: JSON.stringify({ config, approvals }),
    });
    for (;;) {
      onProgress?.(page);
      if (page.status === 'failed') throw new Error(page.error ?? 'Validation stopped unexpectedly.');
      if (page.status === 'completed') {
        if (!page.report) throw new Error('Validation finished without a report. Run validation again.');
        return page.report;
      }
      await new Promise<void>((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
      page = await request(`/api/validations/${encodeURIComponent(page.validationId)}`);
    }
  }

  async startRun(config: AssessmentConfig, approvals: RunApprovals): Promise<RunHandle> {
    const result = await api<{ runId: string }>('/api/runs', {
      method: 'POST',
      body: JSON.stringify({ config, approvals }),
    });
    return new HttpRunHandle(result.runId);
  }

  listRuns(): Promise<RunSummary[]> {
    return api('/api/runs');
  }

  deleteSnapshots(runIds: string[]): Promise<SnapshotDeletion> {
    return api('/api/snapshots/delete', {
      method: 'POST',
      body: JSON.stringify({ runIds, confirmed: true }),
    });
  }

  loadResults(runId: string): Promise<AssessmentResults> {
    return api(`/api/runs/${encodeURIComponent(runId)}/results`);
  }

  saveReview(runId: string, entries: AssessmentResults['review']): Promise<void> {
    return api(`/api/runs/${encodeURIComponent(runId)}/review`, {
      method: 'PUT',
      body: JSON.stringify({ entries }),
    });
  }

  readArtifact(runId: string, relativePath: string): Promise<ArtifactPayload> {
    return api(
      `/api/runs/${encodeURIComponent(runId)}/artifacts/${encodeURIComponent(relativePath)}`,
    );
  }
}
