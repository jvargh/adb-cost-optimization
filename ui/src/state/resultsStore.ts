import { create } from 'zustand';
import type { AssessmentResults, Finding, ReviewEntry } from '@/types';
import { getBackend } from '@/api';

export interface ResultsFilters {
  subscriptionIds: string[];
  resourceGroups: string[];
  workspaces: string[];
  workloads: string[];
  categories: string[];
  confidence: string[];
  status: string[];
  search: string;
}

export const EMPTY_FILTERS: ResultsFilters = {
  subscriptionIds: [],
  resourceGroups: [],
  workspaces: [],
  workloads: [],
  categories: [],
  confidence: [],
  status: [],
  search: '',
};

interface ResultsState {
  runId: string | null;
  results: AssessmentResults | null;
  loading: boolean;
  error: string | null;
  filters: ResultsFilters;
  selectedFinding: Finding | null;
  exportedArtifactPaths: string[];

  load: (runId: string) => Promise<void>;
  clear: () => void;
  setFilter: <K extends keyof ResultsFilters>(key: K, value: ResultsFilters[K]) => void;
  toggleFilter: (key: Exclude<keyof ResultsFilters, 'search'>, value: string) => void;
  clearFilters: () => void;
  selectFinding: (finding: Finding | null) => void;
  saveReview: (entries: ReviewEntry[]) => Promise<void>;
  markArtifactExported: (relativePath: string) => void;
}

let loadRequest = 0;

export const useResultsStore = create<ResultsState>((set, get) => ({
  runId: null,
  results: null,
  loading: false,
  error: null,
  filters: { ...EMPTY_FILTERS },
  selectedFinding: null,
  exportedArtifactPaths: [],

  load: async (runId) => {
    const request = ++loadRequest;
    set({ loading: true, error: null, runId, results: null, selectedFinding: null, exportedArtifactPaths: [] });
    try {
      const results = await getBackend().loadResults(runId);
      if (request !== loadRequest) return;
      set({
        results,
        loading: false,
        filters: { ...EMPTY_FILTERS },
        exportedArtifactPaths: [],
      });
    } catch (error) {
      if (request !== loadRequest) return;
      set({
        loading: false,
        results: null,
        error: error instanceof Error ? error.message : String(error),
      });
    }
  },

  clear: () => {
    loadRequest++;
    set({
      runId: null,
      results: null,
      loading: false,
      error: null,
      filters: { ...EMPTY_FILTERS },
      selectedFinding: null,
      exportedArtifactPaths: [],
    });
  },

  setFilter: (key, value) => set({ filters: { ...get().filters, [key]: value } }),

  toggleFilter: (key, value) => {
    const filters = get().filters;
    const current = filters[key];
    const next = current.includes(value)
      ? current.filter((v) => v !== value)
      : [...current, value];
    set({ filters: { ...filters, [key]: next } });
  },

  clearFilters: () => set({ filters: { ...EMPTY_FILTERS } }),

  selectFinding: (finding) => set({ selectedFinding: finding }),

  saveReview: async (entries) => {
    const { runId, results } = get();
    if (!runId || !results) return;
    await getBackend().saveReview(runId, entries);
    if (get().runId !== runId || get().results !== results) return;
    set({ results: { ...results, review: entries } });
  },

  markArtifactExported: (relativePath) => {
    const current = get().exportedArtifactPaths;
    if (!current.includes(relativePath)) {
      set({ exportedArtifactPaths: [...current, relativePath] });
    }
  },
}));

export function isReviewComplete(results: AssessmentResults | null): boolean {
  if (!results) return false;
  const findingIds = new Set(results.candidates.findings.map((finding) => finding.detectorId));
  if (findingIds.size === 0) return true;
  const completed = new Set(
    results.review
      .filter((entry) => entry.decision !== 'pending' && entry.reviewer.trim().length > 0)
      .map((entry) => entry.findingId),
  );
  return [...findingIds].every((findingId) => completed.has(findingId));
}

function matches(selected: string[], value: string | null | undefined): boolean {
  if (selected.length === 0) return true;
  if (!value) return false;
  return selected.includes(value);
}

export function filterFindings(findings: Finding[], filters: ResultsFilters): Finding[] {
  const search = filters.search.trim().toLowerCase();
  return findings.filter((finding) => {
    if (!matches(filters.subscriptionIds, finding.scope.subscriptionId)) return false;
    if (!matches(filters.resourceGroups, finding.scope.resourceGroup)) return false;
    if (!matches(filters.workspaces, finding.scope.workspaceName)) return false;
    if (!matches(filters.workloads, finding.scope.workload)) return false;
    if (!matches(filters.categories, finding.category)) return false;
    if (!matches(filters.confidence, finding.confidence.level)) return false;
    if (!matches(filters.status, finding.status)) return false;
    if (search) {
      const haystack = `${finding.title} ${finding.detectorId} ${finding.explanation}`.toLowerCase();
      if (!haystack.includes(search)) return false;
    }
    return true;
  });
}

export function filterByScope<T extends { subscriptionId?: string; resourceGroup?: string; workspaceName?: string | null }>(
  rows: T[],
  filters: ResultsFilters,
): T[] {
  return rows.filter((row) => {
    if (!matches(filters.subscriptionIds, row.subscriptionId ?? null)) return false;
    if (!matches(filters.resourceGroups, row.resourceGroup ?? null)) return false;
    if (filters.workspaces.length > 0 && row.workspaceName !== undefined) {
      if (!matches(filters.workspaces, row.workspaceName)) return false;
    }
    return true;
  });
}

export function activeFilterCount(filters: ResultsFilters): number {
  return (
    filters.subscriptionIds.length +
    filters.resourceGroups.length +
    filters.workspaces.length +
    filters.workloads.length +
    filters.categories.length +
    filters.confidence.length +
    filters.status.length +
    (filters.search.trim() ? 1 : 0)
  );
}
