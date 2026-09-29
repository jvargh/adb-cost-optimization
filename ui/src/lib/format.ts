import type { CollectionStatus, ConfidenceLevel, RunStatus } from '@/types';

/**
 * Formats money. Returns an explicit "absent" marker rather than "0" when no
 * value exists — the backend distinguishes absent evidence from zero cost and
 * the UI must not collapse that distinction.
 */
export function formatMoney(
  value: number | null | undefined,
  currency = 'USD',
  options: { compact?: boolean; absentLabel?: string } = {},
): string {
  const { compact = false, absentLabel = 'Not available' } = options;
  if (value === null || value === undefined || Number.isNaN(value)) return absentLabel;
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
    notation: compact ? 'compact' : 'standard',
    maximumFractionDigits: compact ? 1 : value < 100 ? 2 : 0,
    minimumFractionDigits: compact ? 0 : value < 100 ? 2 : 0,
  }).format(value);
}

export function formatNumber(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  return new Intl.NumberFormat('en-US', {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  }).format(value);
}

/** Accepts a 0..1 fraction and renders it as a percentage. */
export function formatPercent(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  return `${(value * 100).toFixed(digits)}%`;
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toISOString().slice(0, 10);
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '—';
  return `${date.toISOString().slice(0, 10)} ${date.toISOString().slice(11, 19)} UTC`;
}

export function formatDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined || Number.isNaN(seconds)) return '—';
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ${Math.round(seconds % 60)}s`;
  return `${Math.floor(minutes / 60)}h ${minutes % 60}m`;
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function elapsedBetween(start: string, end: string | null): string {
  if (!end) return '—';
  const ms = new Date(end).getTime() - new Date(start).getTime();
  if (Number.isNaN(ms) || ms < 0) return '—';
  return formatDuration(ms / 1000);
}

export type Tone = 'ok' | 'warn' | 'danger' | 'pending' | 'neutral' | 'accent';

export function collectionStatusTone(status: CollectionStatus): Tone {
  switch (status) {
    case 'passed':
      return 'ok';
    case 'partial':
      return 'warn';
    case 'failed':
      return 'danger';
    case 'pending telemetry':
      return 'pending';
    case 'skipped':
      return 'neutral';
    default:
      return 'neutral';
  }
}

export function runStatusTone(status: RunStatus): Tone {
  if (status === 'passed') return 'ok';
  if (status === 'partial') return 'warn';
  return 'danger';
}

export function confidenceTone(level: ConfidenceLevel): Tone {
  if (level === 'high') return 'ok';
  if (level === 'medium') return 'warn';
  return 'danger';
}

/**
 * Human-readable meaning of each status. Shown as tooltips and legends so the
 * vocabulary is never ambiguous to a reader.
 */
export const STATUS_MEANING: Record<CollectionStatus, string> = {
  passed: 'The source returned the evidence the assessment expected.',
  partial: 'The source returned some evidence, but at least one dataset was incomplete.',
  failed: 'The source returned no usable evidence. Dependent analysis was not attempted.',
  'pending telemetry':
    'The source exists but the evidence required to evaluate it was not available in the window. This is not zero and not a failure.',
  skipped: 'The source was intentionally not collected. This does not degrade the run.',
};

export const RUN_STATUS_MEANING: Record<RunStatus, string> = {
  passed: 'Every source returned the evidence the assessment expected.',
  partial:
    'At least one source reported partial, failed, or pending telemetry. Findings are limited by the evidence that was collected.',
  failed: 'The run could not produce a usable evidence base.',
};

export function shortResourceId(id: string): string {
  const segments = id.split('/').filter(Boolean);
  return segments[segments.length - 1] ?? id;
}

export function humanizeKey(key: string): string {
  const spaced = key.replace(/[_-]+/g, ' ').replace(/([a-z0-9])([A-Z])/g, '$1 $2');
  return spaced.charAt(0).toUpperCase() + spaced.slice(1).toLowerCase();
}

export const CHART_COLORS = [
  'var(--chart-1)',
  'var(--chart-2)',
  'var(--chart-3)',
  'var(--chart-4)',
  'var(--chart-5)',
  'var(--chart-6)',
  'var(--chart-7)',
  'var(--chart-8)',
];

export function chartColor(index: number): string {
  return CHART_COLORS[index % CHART_COLORS.length];
}
