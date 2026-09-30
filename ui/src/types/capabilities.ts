export const MODULES = ['utilization', 'sizing', 'jobs', 'queries', 'network', 'posture', 'assets', 'commitments'] as const;
export type CapabilityModule = typeof MODULES[number];
export const ASSET_TYPES = ['repos', 'notebooks', 'experiments', 'serving-endpoints', 'sql-alerts', 'genie-spaces', 'uc-volumes'] as const;
export const DEFAULT_RULES = { idleCpuPercent: 10, busyCpuPercent: 80, highMemoryPercent: 80, minimumSamples: 30, slowQuerySeconds: 60, failureRatePercent: 10 };
export interface CapabilityOptions {
  profile: 'standard' | 'extended' | 'custom';
  concurrency: number;
  modules: CapabilityModule[];
  assets: string[];
  rules: typeof DEFAULT_RULES;
}
export const defaultOptions = (): CapabilityOptions => ({ profile: 'standard', concurrency: 1, modules: [...MODULES], assets: [], rules: { ...DEFAULT_RULES } });
export type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue };
export interface CapabilityRow {
  key: string;
  name: string;
  workspaceId: string;
  workspaceName: string;
  resourceId: string;
  status: string;
  detail: { [key: string]: JsonValue };
  [key: string]: JsonValue;
}
export interface CapabilityCoverage { rows: number; status: string; completeWindow: boolean }
export interface CapabilitySummary {
  schemaVersion: string;
  origin: string;
  ruleVersion: string;
  options: CapabilityOptions;
  limitations: string[];
  coverage: Record<CapabilityModule, CapabilityCoverage>;
  workspaceCoverage?: { workspaceId: string; workspaceName: string; modules: Record<CapabilityModule, CapabilityCoverage> }[];
}
export interface CapabilityPage {
  rows: CapabilityRow[];
  total: number;
  offset: number;
  limit: number;
  coverage: CapabilityCoverage;
  ruleVersion: string;
}
