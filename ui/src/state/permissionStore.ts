import { create } from 'zustand';
import { getBackend } from '@/api';
import type { PermissionSetup } from '@/api/backend';
import { BackendRequestError } from '@/api/backend';
import type { WorkspaceSelection } from '@/types';

const STORAGE_KEY = 'assessment-permission-setup-id';
const PHASE_KEY = 'assessment-permission-setup-phase';
const working = (job: PermissionSetup) => ['verifying', 'applying'].includes(job.status);
const blocking = (job: PermissionSetup) => working(job) || job.status === 'unknown';

interface PermissionState {
  job: PermissionSetup | null;
  busy: boolean;
  requesting: boolean;
  error: string | null;
  preview: (workspace: WorkspaceSelection, approved: boolean) => Promise<void>;
  apply: (approved: boolean) => Promise<void>;
  refresh: () => Promise<void>;
  clear: (acknowledgeUnknown?: boolean) => void;
}

export const usePermissionStore = create<PermissionState>((set, get) => {
  const track = async (initial: PermissionSetup) => {
    let job = initial;
    sessionStorage.setItem(STORAGE_KEY, job.setupId);
    set({ job, busy: blocking(job), error: job.error });
    while (working(job)) {
      await new Promise<void>((resolve) => setTimeout(resolve, 750));
      job = await getBackend().getPermissionSetup(job.setupId);
      set({ job, busy: blocking(job), error: job.error });
    }
  };
  const message = (error: unknown) => error instanceof Error ? error.message : String(error);
  const forget = () => {
    sessionStorage.removeItem(STORAGE_KEY);
    sessionStorage.removeItem(PHASE_KEY);
  };
  const stalePreview = (error: unknown) => {
    forget();
    set({ job: null, busy: false, error: `${message(error)} This request submitted no new grants. Verify the identity again to create a fresh preview.` });
  };
  return {
    job: null, busy: false, requesting: false, error: null,
    preview: async (workspace, approved) => {
      if (get().busy || get().requesting) return;
      forget();
      sessionStorage.setItem(PHASE_KEY, 'preview');
      set({ job: null, busy: true, requesting: true, error: null });
      try {
        await track(await getBackend().previewPermissionSetup(workspace, approved));
      } catch (error) {
        set({ busy: Boolean(get().job && working(get().job!)), error: message(error) });
      } finally {
        set({ requesting: false });
      }
    },
    apply: async (approved) => {
      const job = get().job;
      if (get().busy || get().requesting || !job?.principal || job.status !== 'awaiting_confirmation') {
        set({ error: 'Verify the identity and wait for the exact-grant preview before confirming.' });
        return;
      }
      set({ job: { ...job, status: 'applying' }, busy: true, requesting: true, error: null });
      sessionStorage.setItem(PHASE_KEY, 'apply');
      try {
        let response: PermissionSetup;
        try {
          response = await getBackend().applyPermissionSetup(job.setupId, job.principal, approved);
        } catch (error) {
          if (error instanceof BackendRequestError && error.status === 404) {
            stalePreview(error);
            return;
          }
          if (error instanceof BackendRequestError && error.status === 409) {
            await track(await getBackend().getPermissionSetup(job.setupId));
            if (!get().error) set({ error: message(error) });
            return;
          }
          throw error;
        }
        await track(response);
      } catch (error) {
        set({ error: `${message(error)} The application outcome is not verified. Check setup status before retrying.`, busy: true });
      } finally {
        set({ requesting: false });
      }
    },
    refresh: async () => {
      if (get().requesting) return;
      const id = get().job?.setupId ?? sessionStorage.getItem(STORAGE_KEY);
      if (!id) return;
      set({ requesting: true, busy: true, error: null });
      try {
        await track(await getBackend().getPermissionSetup(id));
      } catch (error) {
        if (error instanceof BackendRequestError && error.status === 404 && sessionStorage.getItem(PHASE_KEY) === 'preview') {
          stalePreview(error);
        } else {
          set({ error: `${message(error)} Status checking stopped. Inspect the local setup audit and actual permissions if the host restarted.`, busy: true });
        }
      } finally {
        set({ requesting: false });
      }
    },
    clear: (acknowledgeUnknown = false) => {
      if (get().requesting || (get().busy && !(acknowledgeUnknown && get().error))) {
        set({ error: 'Check the in-flight setup status before clearing it.' });
        return;
      }
      forget();
      set({ job: null, error: null, busy: false });
    },
  };
});
