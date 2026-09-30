import type { AnalysisWindow, CollectionSource, AssessmentManifest, ScopeFilter } from './assessment';
import type { Finding, OptimizationCandidates, ReviewEntry, Confidence } from './findings';

/** Matches `cost-reconciliation.json`. */
export interface CostReconciliation {
  schemaVersion: string;
  reportingBasis: string;
  currency: string;
  authoritativeTotal: number | null;
  authoritativeTotals: Record<string, number>;
  collectedTotal: number | null;
  matchedCost: number | null;
  unmatchedCost: number | null;
  excludedCost: number | null;
  allocatedSharedCost: number | null;
  varianceAmount: number | null;
  variancePercent: number | null;
  withinTolerance: boolean | null;
  currencyAggregationAllowed: boolean;
  databricksListPriceEstimate: number | null;
  databricksListPriceAddedToAzure: number;
  unmatchedDatabricksUsageRecords: number;
  taxIncluded: boolean | null;
  duplicatePrevention: {
    rule: string;
    azureContainsDatabricksServiceCost: boolean;
    serverlessDbuCost: number;
    serverlessVmCostNotAdded: number;
  };
  limitations: string[];
}

/** Matches `attribution-coverage.json`. */
export interface AttributionCoverage {
  schemaVersion: string;
  resourceCount: number;
  attributedResourceCount: number;
  resourceCoveragePercent: number;
  totalSpend: number;
  attributedSpend: number;
  spendCoveragePercent: number;
}

/** Matches `telemetry-quality.json`. */
export interface TelemetryQuality {
  schemaVersion: string;
  generatedAtUtc: string;
  overall: Confidence;
  sources: (Confidence & { source: string })[];
}

/** Matches `benefits-baseline.json`. `realizedSavings` is always null at baseline. */
export interface BenefitsBaseline {
  schemaVersion: string;
  baselineId: string;
  createdAtUtc: string;
  analysisWindow: AnalysisWindow;
  reportingBasis: string;
  currency: string;
  authoritativeCost: number | null;
  realizedSavings: number | null;
  workloadNormalization: { method: string; reason: string };
}

export interface CostDriver {
  rank: number;
  driver: string;
  displayName: string;
  resourceType: string;
  subscriptionId: string;
  resourceGroup: string;
  workspaceName: string | null;
  observedCost: number;
  currency: string;
}

export interface CostTrendPoint {
  date: string;
  actualCost: number;
  amortizedCost: number;
  dbuCost: number;
  infrastructureCost: number;
}

export interface CostBreakdownSlice {
  key: string;
  label: string;
  cost: number;
  currency: string;
  /** Dimension this slice belongs to, used for drill-down. */
  dimension: 'service' | 'meterCategory' | 'sku' | 'resourceGroup' | 'workspace' | 'tagOwner';
}

export interface ComputeRecord {
  workspaceId?: string;
  clusterId: string;
  clusterName: string;
  workspaceName: string;
  source: 'JOB' | 'UI' | 'API' | 'PIPELINE';
  state: string;
  nodeTypeId: string;
  driverNodeTypeId: string;
  runtime: string;
  photon: boolean;
  autoterminationMinutes: number;
  minWorkers: number | null;
  maxWorkers: number | null;
  spotDriver: boolean;
  observedUptimeHours: number;
  idlePercent: number | null;
  owner: string | null;
  policyName: string | null;
}

export interface WarehouseRecord {
  workspaceId?: string;
  id: string;
  name: string;
  workspaceName: string;
  size: string;
  state: string;
  serverless: boolean;
  photon: boolean;
  autoStopMinutes: number;
  minClusters: number;
  maxClusters: number;
  queryCount: number | null;
  p95QueueSeconds: number | null;
  p95DurationSeconds: number | null;
  spillGb: number | null;
}

export interface WorkloadRecord {
  workspaceId?: string;
  jobId: string;
  jobName: string;
  workspaceName: string;
  computeType: 'serverless' | 'job-cluster' | 'all-purpose' | 'pipeline';
  runCount: number;
  failureRatePercent: number | null;
  p50DurationSeconds: number | null;
  p95DurationSeconds: number | null;
  owner: string | null;
  observedCost: number | null;
  currency: string;
}

export interface RoadmapItem {
  horizon: '0-30' | '31-60' | '61-90';
  title: string;
  detail: string;
  owner: string;
  dependsOnFindingIds: string[];
}

export interface EvidenceGap {
  source: string;
  status: string;
  impact: string;
  requiredToUnlock: string[];
}

/** Everything the Visualize Results area binds to for one run. */
export interface AssessmentResults {
  capabilities?: import('./capabilities').CapabilitySummary | null;
  costAvailable?: boolean;
  parentRunId?: string | null;
  manifest: AssessmentManifest;
  scopeFilter: ScopeFilter;
  collection: CollectionSource[];
  reconciliation: CostReconciliation;
  attribution: AttributionCoverage;
  telemetry: TelemetryQuality;
  benefits: BenefitsBaseline;
  candidates: OptimizationCandidates;
  costDrivers: CostDriver[];
  costTrend: CostTrendPoint[];
  costBreakdown: CostBreakdownSlice[];
  compute: ComputeRecord[];
  warehouses: WarehouseRecord[];
  workloads: WorkloadRecord[];
  roadmap: RoadmapItem[];
  evidenceGaps: EvidenceGap[];
  review: ReviewEntry[];
  reportMarkdown: string;
  exports: ExportArtifact[];
}

export interface ExportArtifact {
  name: string;
  relativePath: string;
  kind: 'markdown' | 'csv' | 'json' | 'ndjson' | 'xlsx';
  description: string;
  sizeBytes: number;
  sensitivity: 'sensitive' | 'redacted';
}

export type { Finding, ReviewEntry };
