import type { ValidationProgress } from '@/types';

export function summarizeValidationProgress(progress: ValidationProgress, now: number) {
  const steps = progress.steps;
  const completed = steps.filter((step) => !['pending', 'running'].includes(step.status)).length;
  const active = steps.find((step) => step.status === 'running');
  const currentSeconds = active?.startedAtUtc
    ? Math.max(0, (now - Date.parse(active.startedAtUtc)) / 1000)
    : 0;
  const remaining = steps
    .filter((step) => ['pending', 'running'].includes(step.status))
    .reduce((sum, step) => sum + step.estimatedSeconds, 0);
  const overdue = Boolean(active && currentSeconds > active.estimatedSeconds * 1.5);
  const remainingSeconds = Math.max(1, remaining - currentSeconds);
  return {
    completed,
    total: steps.length,
    percent: steps.length ? Math.floor((completed / steps.length) * 100) : 0,
    active,
    currentSeconds,
    overdue,
    eta: overdue || steps.length === 0
      ? null
      : { min: Math.max(1, Math.ceil(remainingSeconds * 0.5 / 60)), max: Math.max(1, Math.ceil(remainingSeconds * 1.5 / 60)) },
  };
}
