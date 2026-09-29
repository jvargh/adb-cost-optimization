/**
 * Configuration contract. Mirrors `assessment/config/assessment-scope.example.json`
 * so the Configure screen can round-trip a scope file without a translation layer.
 */

export interface WorkspaceSelection {
  subscriptionId?: string;
  name: string;
  resourceGroup: string;
  workspaceUrl: string;
  workspaceId: string;
  include: boolean;
  /** Presence of a warehouse id triggers the auto-start approval gate. */
  sqlWarehouseId?: string;
  deepDiveJobRunIds?: string[];
  deepDiveTableNames?: string[];
}

export type CostBasis = 'ActualCost' | 'AmortizedCost';

export interface AzureScopeConfig {
  tenantId: string;
  subscriptions: string[];
  resourceGroups: string[];
  resourceGroupIds?: string[];
  includeManagementGroups: boolean;
  costScope: string;
  costScopes?: string[];
  costBasis: CostBasis[];
  currency: string;
}

export interface DatabricksScopeConfig {
  accountId?: string;
  accountHost?: string;
  workspaces: WorkspaceSelection[];
  /** Legacy/global warehouse selection supported by the assessment config. */
  sqlWarehouseId?: string;
  includeQueryText: boolean;
  includeNotebookPaths: boolean;
  includeIdentities: boolean;
  /** Legacy targets, only unambiguous when a single workspace is included. */
  deepDiveJobRunIds: string[];
  deepDiveTableNames: string[];
  /** Persisted approval equivalent of -ApproveSqlWarehouseAutoStart. */
  allowSqlWarehouseAutoStart?: boolean;
}

export interface AnalysisConfig {
  startUtc: string;
  endUtc: string;
  timeZone: string;
  maxPages: number;
  pageSize: number;
  requestTimeoutSeconds: number;
  collectorTimeoutSeconds: number;
  retryCount: number;
  retryBaseSeconds: number;
}

export interface ThresholdConfig {
  materialMonthlyCost: number;
  unattributedCostPercent: number;
  idleComputePercent: number;
  interactiveAutoTerminationMinutes: number;
  legacyRuntimeMajorVersionsBehind: number;
  smallFileBytes: number;
  smallFilePercent: number;
  sqlQueueP95Seconds: number;
  jobFailureRatePercent: number;
  continuousStreamingIdlePercent: number;
  poolIdleHours: number;
}

export interface RedactionConfig {
  hashIdentities: boolean;
  hashTableNames: boolean;
  hashNotebookPaths: boolean;
  omitQueryText: boolean;
  saltEnvironmentVariable: string;
}

export interface OutputConfig {
  root: string;
  retainRaw: boolean;
  writeCsv: boolean;
  writeJson: boolean;
  writeMarkdown: boolean;
}

export interface AssessmentConfig {
  customerId: string;
  assessmentId: string;
  azure: AzureScopeConfig;
  databricks: DatabricksScopeConfig;
  analysis: AnalysisConfig;
  thresholds: ThresholdConfig;
  redaction: RedactionConfig;
  outputs: OutputConfig;
}

/** Discoverable estate used to populate the Configure pickers. */
export interface SubscriptionOption {
  subscriptionId: string;
  displayName: string;
  tenantId: string;
  state: string;
  resourceGroups: ResourceGroupOption[];
}

export interface ResourceGroupOption {
  name: string;
  resourceGroupId: string;
  location: string;
  subscriptionId: string;
  /** Databricks workspaces discovered inside this group. */
  workspaces: DiscoveredWorkspace[];
  /** True when this group is a Databricks-managed resource group. */
  isManagedResourceGroup: boolean;
  /** Set when the signed-in principal lacks Reader on the group. */
  permissionIssue?: string;
}

export interface DiscoveredWorkspace {
  name: string;
  workspaceId: string;
  workspaceUrl: string;
  resourceGroup: string;
  subscriptionId: string;
  managedResourceGroup: string;
  sku: string;
  location: string;
  sqlWarehouses: DiscoveredWarehouse[];
  warehouseDiscoveryError?: string;
}

export interface DiscoveredWarehouse {
  id: string;
  name: string;
  size: string;
  state: 'RUNNING' | 'STOPPED' | 'STARTING' | 'DELETED';
  serverless: boolean;
}
