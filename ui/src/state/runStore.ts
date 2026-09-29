import { create } from 'zustand';
import type { CollectionSource, RunPhase, RunSummary } from '@/types';
import type { RunEvent, RunHandle } from '@/api/backend';
import { getBackend } from '@/api';
import { useConfigStore } from './configStore';
import { usePermissionStore } from './permissionStore';

export interface ConsoleLine {
  level: 'info' | 'warn' | 'error' | 'phase';
  message: string;
  atUtc: string;
}

export const PHASE_ORDER: RunPhase[] = [
  'preflight',
  'collecting',
  'normalizing',
  'analyzing',
  'findings',
  'reporting',
  'completed',
];

interface RunState {
  phase: RunPhase;
  runId: string | null;
  startedAtUtc: string | null;
  finishedAtUtc: string | null;
  sources: CollectionSource[];
  console: ConsoleLine[];
  error: string | null;
  handle: RunHandle | null;
  unsubscribe: (() => void) | null;
  runs: RunSummary[];
  loadingRuns: boolean;
  runsError: string | null;

  start: () => Promise<void>;
  cancel: () => Promise<void>;
  reset: () => void;
  refreshRuns: () => Promise<void>;
  adoptRun: (runId: string) => void;
}

const MAX_CONSOLE_LINES = 400;

export const useRunStore = create<RunState>((set, get) => ({
  phase: 'idle',
  runId: null,
  startedAtUtc: null,
  finishedAtUtc: null,
  sources: [],
  console: [],
  error: null,
  handle: null,
  unsubscribe: null,
  runs: [],
  loadingRuns: false,
  runsError: null,

  start: async () => {
    if (usePermissionStore.getState().busy) {
      set({ error: 'Check the permission setup outcome before starting assessment collection.' });
      return;
    }
    const { config, approvals, validating, validation } = useConfigStore.getState();
    if (!config) throw new Error('Configuration has not been loaded yet.');
    if (validating || !validation?.canRun) {
      set({ error: 'Wait for validation to finish and resolve blocking items before starting.' });
      return;
    }
    get().reset();
    set({ phase: 'preflight', startedAtUtc: new Date().toISOString() });
    try {
      const handle = await getBackend().startRun(config, approvals);
      const unsubscribe = handle.subscribe((event) => applyEvent(set, get, event));
      set({ handle, unsubscribe, runId: handle.runId });
    } catch (error) {
      set({ phase: 'failed', finishedAtUtc: new Date().toISOString(), error: error instanceof Error ? error.message : String(error) });
    }
  },

  cancel: async () => {
    const handle = get().handle;
    if (!handle) return;
    await handle.cancel();
  },

  reset: () => {
    get().unsubscribe?.();
    set({
      phase: 'idle',
      runId: null,
      startedAtUtc: null,
      finishedAtUtc: null,
      sources: [],
      console: [],
      error: null,
      handle: null,
      unsubscribe: null,
    });
  },

  refreshRuns: async () => {
    if (get().loadingRuns) return;
    set({ loadingRuns: true, runsError: null });
    try {
      const runs = await getBackend().listRuns();
      set({ runs, loadingRuns: false });
    } catch (error) {
      set({ loadingRuns: false, runsError: error instanceof Error ? error.message : String(error) });
    }
  },

  adoptRun: (runId) => set({ runId, phase: 'completed' }),
}));

type SetState = (partial: Partial<RunState>) => void;
type GetState = () => RunState;

function applyEvent(set: SetState, get: GetState, event: RunEvent): void {
  const state = get();
  const nextConsole = [...state.console];
  const push = (line: ConsoleLine) => {
    nextConsole.push(line);
    if (nextConsole.length > MAX_CONSOLE_LINES) nextConsole.splice(0, nextConsole.length - MAX_CONSOLE_LINES);
  };

  switch (event.type) {
    case 'phase':
      push({ level: 'phase', message: event.message, atUtc: event.atUtc });
      set({ phase: event.phase, console: nextConsole });
      break;
    case 'log':
      push({ level: event.level, message: event.message, atUtc: event.atUtc });
      set({ console: nextConsole });
      break;
    case 'source': {
      const sources = [...state.sources];
      const index = sources.findIndex((s) => s.name === event.source.name);
      if (index >= 0) sources[index] = event.source;
      else sources.push(event.source);
      push({
        level:
          event.source.status === 'failed'
            ? 'error'
            : event.source.status === 'passed'
              ? 'info'
              : 'warn',
        message: `${event.source.name}: ${event.source.status} (${event.source.itemCount} items)`,
        atUtc: event.atUtc,
      });
      set({ sources, console: nextConsole });
      break;
    }
    case 'completed':
      push({ level: 'phase', message: `Run ${event.runId} complete.`, atUtc: event.atUtc });
      set({
        phase: 'completed',
        runId: event.runId,
        finishedAtUtc: event.atUtc,
        console: nextConsole,
      });
      void get().refreshRuns();
      break;
    case 'failed':
      push({ level: 'error', message: event.message, atUtc: event.atUtc });
      set({
        phase: 'failed',
        error: event.message,
        finishedAtUtc: event.atUtc,
        console: nextConsole,
      });
      break;
    case 'canceled':
      push({
        level: 'warn',
        message:
          'Cancellation requested. The backend has no whole-run cancellation checkpoint, so the child process is terminated and the run is marked partial.',
        atUtc: event.atUtc,
      });
      set({ phase: 'canceled', finishedAtUtc: event.atUtc, console: nextConsole });
      break;
  }
}

export function phaseIndex(phase: RunPhase): number {
  const index = PHASE_ORDER.indexOf(phase);
  if (index >= 0) return index;
  return phase === 'failed' || phase === 'canceled' ? PHASE_ORDER.length : -1;
}
