import { describe, expect, it } from 'vitest';
import { filterFindings, activeFilterCount, EMPTY_FILTERS } from '@/state/resultsStore';
import type { Finding } from '@/types';
import results from '../mock/fixtures/contoso-partial.results.json';

const FINDINGS = (results as unknown as { candidates: { findings: Finding[] } }).candidates.findings;

describe('results filtering', () => {
  it('returns everything when no filter is applied', () => {
    expect(filterFindings(FINDINGS, EMPTY_FILTERS)).toHaveLength(FINDINGS.length);
    expect(activeFilterCount(EMPTY_FILTERS)).toBe(0);
  });

  it('narrows by workspace', () => {
    const workspace = FINDINGS.find((f) => f.scope.workspaceName)?.scope.workspaceName!;
    const filtered = filterFindings(FINDINGS, { ...EMPTY_FILTERS, workspaces: [workspace] });
    expect(filtered.length).toBeGreaterThan(0);
    expect(filtered.every((f) => f.scope.workspaceName === workspace)).toBe(true);
  });

  it('excludes estate-wide findings when a workspace filter is active', () => {
    const estateWide = FINDINGS.filter((f) => f.scope.workspaceName === null);
    expect(estateWide.length).toBeGreaterThan(0);
    const workspace = FINDINGS.find((f) => f.scope.workspaceName)?.scope.workspaceName!;
    const filtered = filterFindings(FINDINGS, { ...EMPTY_FILTERS, workspaces: [workspace] });
    expect(filtered.some((f) => f.scope.workspaceName === null)).toBe(false);
  });

  it('keeps insufficient evidence findings visible as a first-class status', () => {
    const filtered = filterFindings(FINDINGS, {
      ...EMPTY_FILTERS,
      status: ['insufficient_evidence'],
    });
    expect(filtered.length).toBeGreaterThan(0);
    expect(filtered.every((f) => f.status === 'insufficient_evidence')).toBe(true);
  });

  it('combines filters conjunctively', () => {
    const target = FINDINGS.find((f) => f.scope.workspaceName && f.status === 'candidate')!;
    const filtered = filterFindings(FINDINGS, {
      ...EMPTY_FILTERS,
      workspaces: [target.scope.workspaceName!],
      categories: [target.category],
      status: ['candidate'],
    });
    expect(filtered).toContain(target);
    expect(
      filtered.every(
        (f) =>
          f.scope.workspaceName === target.scope.workspaceName &&
          f.category === target.category &&
          f.status === 'candidate',
      ),
    ).toBe(true);
  });

  it('searches across title, detector id, and explanation', () => {
    const target = FINDINGS[0];
    expect(
      filterFindings(FINDINGS, { ...EMPTY_FILTERS, search: target.detectorId.toLowerCase() }),
    ).toContain(target);
    expect(filterFindings(FINDINGS, { ...EMPTY_FILTERS, search: 'zzz-no-match-zzz' })).toHaveLength(0);
  });

  it('counts active filters for the UI badge', () => {
    expect(
      activeFilterCount({ ...EMPTY_FILTERS, workspaces: ['a', 'b'], search: 'x' }),
    ).toBe(3);
  });
});
