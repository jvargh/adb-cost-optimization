import { describe, expect, it } from 'vitest';
import {
  formatMoney,
  formatNumber,
  formatPercent,
  formatDuration,
  collectionStatusTone,
  runStatusTone,
  confidenceTone,
  STATUS_MEANING,
} from '@/lib/format';

describe('absent versus zero', () => {
  it('renders absent money as unavailable, never as zero', () => {
    expect(formatMoney(null, 'USD')).toBe('Not available');
    expect(formatMoney(undefined, 'USD')).toBe('Not available');
  });

  it('renders a measured zero as zero', () => {
    expect(formatMoney(0, 'USD')).toContain('0');
    expect(formatMoney(0, 'USD')).not.toBe('Not available');
  });

  it('treats absent numbers and percentages the same way', () => {
    expect(formatNumber(null)).toBe('\u2014');
    expect(formatNumber(null)).not.toBe('0');
    expect(formatNumber(0)).toBe('0');
    expect(formatPercent(null)).toBe('\u2014');
    expect(formatPercent(0)).toBe('0.0%');
    expect(formatPercent(0.9817)).toBe('98.2%');
  });

  it('formats durations without inventing a value', () => {
    expect(formatDuration(null)).toBe('\u2014');
    expect(formatDuration(0)).toBe('0s');
  });
});

describe('status tone mapping', () => {
  it('never maps pending telemetry to a failure tone', () => {
    expect(collectionStatusTone('pending telemetry')).toBe('pending');
    expect(collectionStatusTone('failed')).toBe('danger');
    expect(collectionStatusTone('passed')).toBe('ok');
    expect(collectionStatusTone('partial')).toBe('warn');
    expect(collectionStatusTone('skipped')).toBe('neutral');
  });

  it('explains every status in the legend', () => {
    for (const status of [
      'passed',
      'partial',
      'failed',
      'pending telemetry',
      'skipped',
    ] as const) {
      expect(STATUS_MEANING[status]).toBeTruthy();
    }
    expect(STATUS_MEANING['pending telemetry'].toLowerCase()).toContain('not');
  });

  it('maps run status and confidence to sensible tones', () => {
    expect(runStatusTone('passed')).toBe('ok');
    expect(runStatusTone('partial')).toBe('warn');
    expect(runStatusTone('failed')).toBe('danger');
    expect(confidenceTone('high')).toBe('ok');
    expect(confidenceTone('low')).toBe('danger');
  });
});
