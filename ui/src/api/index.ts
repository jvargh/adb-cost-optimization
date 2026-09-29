import type { AssessmentBackend } from './backend';
import { HttpAssessmentBackend } from './httpBackend';
import { MockAssessmentBackend } from './mockBackend';

/**
 * Development and tests keep the approved mock. Production builds use the
 * loopback API unless `?mock=1` is supplied for an offline demonstration.
 */
let backend: AssessmentBackend | null = null;

export function getBackend(): AssessmentBackend {
  if (!backend) {
    const queryRequestsMock =
      typeof window !== 'undefined' &&
      new URLSearchParams(window.location.search).get('mock') === '1';
    backend =
      import.meta.env.DEV || import.meta.env.MODE === 'test' || queryRequestsMock
        ? new MockAssessmentBackend()
        : new HttpAssessmentBackend();
  }
  return backend;
}

/** Test seam. */
export function setBackend(next: AssessmentBackend | null): void {
  backend = next;
}

export type { AssessmentBackend, RunHandle, RunEvent, RunApprovals } from './backend';
export {
  setActiveScenario,
  setPlaybackSpeed,
  listScenarioIds,
  activeScenarioId,
} from './mockBackend';
