/**
 * Status vocabulary. Mirrors the backend contract exactly — see
 * AzureDatabricksCostOptimizationEndToEndSpecification.md section 9/12.
 *
 * `pending telemetry` is NOT zero and NOT a failure: the source exists but the
 * evidence required to evaluate it was not available in the analysis window.
 * `skipped` alone does not degrade the run. Any partial/failed/pending source
 * makes the overall run manifest `partial`.
 */
export const COLLECTION_STATUSES = [
  'passed',
  'partial',
  'failed',
  'pending telemetry',
  'skipped',
] as const;

export type CollectionStatus = (typeof COLLECTION_STATUSES)[number];

export type RunStatus = 'passed' | 'partial' | 'failed';

/** Lifecycle of a UI-orchestrated run. Not persisted by the backend. */
export type RunPhase =
  | 'idle'
  | 'preflight'
  | 'collecting'
  | 'normalizing'
  | 'analyzing'
  | 'findings'
  | 'reporting'
  | 'completed'
  | 'failed'
  | 'canceled';

export interface AnalysisWindow {
  startUtc: string;
  endUtc: string;
  timeZone: string;
}

/** One collector entry, matching `collection-status.json` array elements. */
export interface CollectionSource {
  name: string;
  status: CollectionStatus;
  startedAtUtc: string | null;
  completedAtUtc: string | null;
  itemCount: number;
  outputs: string[];
  limitations: string[];
  error: string;
  /** UI-only grouping so the Monitor view can segment Azure vs Databricks. */
  domain: 'azure' | 'databricks';
  workspaceKey?: string;
}

/** Matches `assessment-manifest.json` (subset the UI binds to). */
export interface AssessmentManifest {
  schemaVersion: string;
  toolkitVersion: string;
  runId: string;
  customerId: string;
  assessmentId: string;
  startedAtUtc: string;
  completedAtUtc: string | null;
  status: RunStatus;
  analysisWindow: AnalysisWindow;
  outputRoot: string;
  scope: ManifestScope;
}

export interface ManifestScope {
  tenantId: string;
  subscriptionIds: string[];
  resourceGroups: string[];
  resourceGroupIds: string[];
  workspaces: ManifestWorkspace[];
}

export interface ManifestWorkspace {
  name: string;
  workspaceId: string;
  workspaceUrl: string;
  resourceGroup: string;
  subscriptionId: string;
}

/** Matches `scope-filter.json`. Proves no out-of-scope rows were retained. */
export interface ScopeFilter {
  schemaVersion: string;
  allowedResourceGroups: string[];
  allowedResourceGroupIds: string[];
  entities: Record<
    string,
    { inputRecords: number; includedRecords: number; excludedRecords: number }
  >;
  limitations: string[];
}

/** A persisted run as listed by the Open/Rerun experience. */
export interface RunSummary {
  runId: string;
  customerId: string;
  status: RunStatus;
  startedAtUtc: string;
  completedAtUtc: string | null;
  analysisWindow: AnalysisWindow;
  authoritativeCost: number;
  currency: string;
  findingCount: number;
  subscriptionIds: string[];
  workspaceNames: string[];
  scenarioId: string;
}
