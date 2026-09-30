import type {
  AssessmentConfig,
  SubscriptionOption,
  ValidationCheck,
  ValidationReport,
} from '@/types';
import type { RunApprovals } from '@/api/backend';
import { DEEP_DIVE_FIELDS, isResourceGroupSelected } from './scopeSelection';
import { DEFAULT_RULES, MODULES, ASSET_TYPES } from '@/types/capabilities';

/**
 * Pure, synchronously testable validation. Environment checks (CLI presence,
 * RBAC probes) are supplied by the backend adapter; everything derived from the
 * configuration itself is evaluated here so the Configure screen can show
 * feedback without a round trip.
 */
export interface ValidationInput {
  config: AssessmentConfig;
  approvals: RunApprovals;
  estate: SubscriptionOption[];
  /** Checks the adapter probed against the live environment. */
  environmentChecks: ValidationCheck[];
}

const ONE_DAY_MS = 24 * 60 * 60 * 1000;
const MAX_WINDOW_DAYS = 400;

export function validateConfiguration(input: ValidationInput): ValidationReport {
  const { config, approvals, estate, environmentChecks } = input;
  const checks: ValidationCheck[] = [...environmentChecks];

  checks.push(engagementIdCheck('customer-id', 'Customer ID', config.customerId));
  checks.push(engagementIdCheck('assessment-id', 'Assessment ID', config.assessmentId));
  checks.push(subscriptionCheck(config, estate));
  checks.push(resourceGroupCheck(config, estate));
  checks.push(workspaceCheck(config));
  checks.push(analysisWindowCheck(config));
  checks.push(outputCheck(config));
  checks.push(accountConfigurationCheck(config));
  checks.push(scopeConflictCheck(config, estate));
  checks.push(deepDiveTargetsCheck(config));
  if (config.capabilities) {
    const options = config.capabilities;
    const valid = Number.isInteger(options.concurrency) && options.concurrency >= 1 && options.concurrency <= 4
      && Object.entries(options.rules).every(([key, value]) => key in DEFAULT_RULES && Number.isFinite(value) && value > 0
        && value <= (key === 'minimumSamples' || key === 'slowQuerySeconds' ? 100000 : 100))
      && Object.keys(DEFAULT_RULES).every(key => key in options.rules)
      && Number.isInteger(options.rules.minimumSamples) && options.rules.idleCpuPercent < options.rules.busyCpuPercent
      && options.modules.every(m => MODULES.includes(m)) && options.assets.every(a => ASSET_TYPES.some(t => t === a));
    checks.push({ id: 'capability-plan', title: 'Capability rules and collector limits', severity: 'blocker',
      group: 'scope', status: valid ? 'pass' : 'fail', detail: valid ? 'Analysis modules, thresholds and bounded concurrency are configured.'
        : 'Correct rule ranges, minimum sample count and concurrency (1-4) before validation.' });
  }

  const warehouseCheck = sqlWarehouseCheck(config, approvals);
  checks.push(warehouseCheck);
  checks.push(readOnlyAcknowledgementCheck(approvals));

  const blockerCount = checks.filter((c) => c.status === 'fail' && c.severity === 'blocker').length;
  const warningCount = checks.filter((c) => c.status === 'warn' || (c.status === 'fail' && c.severity === 'warning')).length;

  return {
    generatedAtUtc: new Date().toISOString(),
    checks,
    blockerCount,
    warningCount,
    canRun: blockerCount === 0,
    requiresSqlWarehouseApproval: warehouseCheck.status === 'fail',
  };
}

export function hasValidDatabricksAccount(config: AssessmentConfig['databricks']): boolean {
  return /^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i.test(config.accountId ?? '')
    && /^accounts(?:-[a-z0-9]+)?\.azuredatabricks\.(net|us)$/i.test(config.accountHost ?? '');
}

function accountConfigurationCheck(config: AssessmentConfig): ValidationCheck {
  const { accountId = '', accountHost = '' } = config.databricks;
  const configured = Boolean(accountId || accountHost);
  const valid = hasValidDatabricksAccount(config.databricks);
  return {
    id: 'databricks-account-config', title: 'Databricks account settings are valid',
    severity: 'blocker', group: 'scope',
    status: !configured ? 'skipped' : valid ? 'pass' : 'fail',
    detail: !configured ? 'Optional account-level evidence is not configured.'
      : valid ? 'Account settings are configured; live readiness still verifies access.'
        : 'Account ID must be a UUID and Account host must be an Azure Databricks account hostname without a scheme or path.',
    remediation: configured && !valid ? 'Correct both fields in Databricks account settings, or clear both to omit account-level coverage.' : undefined,
  };
}

function engagementIdCheck(id: 'customer-id' | 'assessment-id', label: string, value: string): ValidationCheck {
  const provided = value.trim().length > 0;
  return {
    id,
    title: `${label} is required`,
    severity: 'blocker',
    status: provided ? 'pass' : 'fail',
    group: 'scope',
    detail: provided ? `${label} is configured.` : `${label} is blank.`,
    remediation: provided ? undefined : `Enter ${label} in the Engagement section of Step 1: Configure.`,
  };
}

function subscriptionCheck(config: AssessmentConfig, estate: SubscriptionOption[]): ValidationCheck {
  const selected = config.azure.subscriptions;
  if (selected.length === 0) {
    return {
      id: 'subscription-selected',
      title: 'At least one subscription is selected',
      severity: 'blocker',
      status: 'fail',
      group: 'scope',
      detail: 'No subscription is selected, so there is nothing to assess.',
      remediation: 'Select one or more subscriptions on the Configure screen.',
    };
  }
  const known = new Set(estate.map((s) => s.subscriptionId));
  const unknown = selected.filter((id) => !known.has(id));
  if (unknown.length > 0) {
    return {
      id: 'subscription-selected',
      title: 'Selected subscriptions are visible to the signed-in principal',
      severity: 'blocker',
      status: 'fail',
      group: 'scope',
      detail: `${unknown.length} selected subscription id(s) were not returned by discovery: ${unknown.join(', ')}.`,
      remediation: 'Remove the unknown subscription, or sign in with a principal that can see it.',
    };
  }
  return {
    id: 'subscription-selected',
    title: 'At least one subscription is selected',
    severity: 'blocker',
    status: 'pass',
    group: 'scope',
    detail: `${selected.length} subscription(s) selected.`,
  };
}

function resourceGroupCheck(config: AssessmentConfig, estate: SubscriptionOption[]): ValidationCheck {
  const selected = config.azure.resourceGroupIds ?? config.azure.resourceGroups;
  if (selected.length === 0) {
    return {
      id: 'resource-group-selected',
      title: 'At least one resource group is selected',
      severity: 'blocker',
      status: 'fail',
      group: 'scope',
      detail:
        'No resource group is selected. The assessment never broadens to subscription-wide scope on an empty selection.',
      remediation: 'Select the resource groups that contain your Azure Databricks workspaces.',
    };
  }
  const blocked = estate
    .flatMap((s) => s.resourceGroups)
    .filter((g) => isResourceGroupSelected(config, g) && g.permissionIssue);
  if (blocked.length > 0) {
    return {
      id: 'resource-group-selected',
      title: 'Selected resource groups are readable',
      severity: 'warning',
      status: 'warn',
      group: 'permissions',
      detail: `${blocked.length} selected group(s) report a permission issue: ${blocked
        .map((g) => g.name)
        .join(', ')}. Those groups will be reported as failed sources rather than silently omitted.`,
      remediation: 'Assign Reader on the affected groups, or deselect them to keep the run clean.',
    };
  }
  return {
    id: 'resource-group-selected',
    title: 'At least one resource group is selected',
    severity: 'blocker',
    status: 'pass',
    group: 'scope',
    detail: `${selected.length} resource group(s) selected. Databricks managed resource groups are included automatically.`,
  };
}

function workspaceCheck(config: AssessmentConfig): ValidationCheck {
  const included = config.databricks.workspaces.filter((w) => w.include);
  if (included.length === 0) {
    return {
      id: 'workspace-selected',
      title: 'At least one Databricks workspace is included',
      severity: 'warning',
      status: 'warn',
      group: 'scope',
      detail:
        'No workspace is included. Azure cost evidence will still be collected, but no workspace-level compute, job, SQL, or governance evidence will be available.',
      remediation: 'Include at least one workspace to produce workload-level findings.',
    };
  }
  return {
    id: 'workspace-selected',
    title: 'At least one Databricks workspace is included',
    severity: 'blocker',
    status: 'pass',
    group: 'scope',
    detail: `${included.length} workspace(s) included.`,
  };
}

function analysisWindowCheck(config: AssessmentConfig): ValidationCheck {
  const start = Date.parse(config.analysis.startUtc);
  const end = Date.parse(config.analysis.endUtc);
  const base = {
    id: 'analysis-window' as const,
    title: 'Analysis window is valid',
    severity: 'blocker' as const,
    group: 'scope' as const,
  };
  if (Number.isNaN(start) || Number.isNaN(end)) {
    return {
      ...base, title: 'Valid start and end dates are required', status: 'fail',
      detail: 'Start (UTC) and End (UTC) must both contain valid dates.',
      remediation: 'Set both analysis dates in Step 1: Configure. The end date must be later than the start date.',
    };
  }
  if (end <= start) {
    return { ...base, status: 'fail', detail: 'The analysis window end must be after its start.', remediation: 'Pick an end date later than the start date.' };
  }
  const days = Math.round((end - start) / ONE_DAY_MS);
  if (days > MAX_WINDOW_DAYS) {
    return {
      ...base,
      severity: 'warning',
      status: 'warn',
      detail: `The window spans ${days} days. Cost Management retention and API paging limits make very long windows slow and often incomplete.`,
      remediation: 'Consider 30 to 90 days for a first assessment.',
    };
  }
  if (days < 7) {
    return {
      ...base,
      severity: 'warning',
      status: 'warn',
      detail: `The window spans ${days} day(s). Short windows rarely contain a representative schedule cycle, which lowers sample adequacy and confidence.`,
      remediation: 'Use at least one full weekly cycle so weekday and weekend patterns are both represented.',
    };
  }
  return { ...base, status: 'pass', detail: `The window spans ${days} days.` };
}

function outputCheck(config: AssessmentConfig): ValidationCheck {
  const writesSomething =
    config.outputs.writeMarkdown || config.outputs.writeCsv || config.outputs.writeJson;
  return {
    id: 'output-writable',
    title: 'Output location is configured',
    severity: writesSomething ? 'blocker' : 'blocker',
    status: config.outputs.root.trim() && writesSomething ? 'pass' : 'fail',
    group: 'environment',
    detail: writesSomething
      ? `Run artifacts will be written under ${config.outputs.root}.`
      : 'All output formats are disabled, so the run would produce nothing to review.',
    remediation: writesSomething ? undefined : 'Enable at least one output format.',
  };
}

function scopeConflictCheck(config: AssessmentConfig, estate: SubscriptionOption[]): ValidationCheck {
  const selectedSubs = new Set(config.azure.subscriptions);
  const orphaned = config.azure.resourceGroupIds !== undefined ? config.azure.resourceGroupIds.filter((id) => {
    const match = /^\/subscriptions\/([^/]+)\/resourcegroups\/[^/]+$/i.exec(id);
    return !match || ![...selectedSubs].some((sub) => sub.toLowerCase() === match[1].toLowerCase());
  }) : config.azure.resourceGroups.filter((name) => {
    const owners = estate
      .filter((s) => s.resourceGroups.some((g) => g.name === name))
      .map((s) => s.subscriptionId);
    return owners.length > 0 && !owners.some((id) => selectedSubs.has(id));
  });
  if (orphaned.length > 0) {
    return {
      id: 'scope-conflict',
      title: 'Resource groups belong to selected subscriptions',
      severity: 'blocker',
      status: 'fail',
      group: 'scope',
      detail: `${orphaned.join(', ')} belong(s) to a subscription that is not selected.`,
      remediation: 'Select the owning subscription, or remove the resource group.',
    };
  }
  return {
    id: 'scope-conflict',
    title: 'Resource groups belong to selected subscriptions',
    severity: 'blocker',
    status: 'pass',
    group: 'scope',
    detail: 'Every selected resource group resolves inside a selected subscription.',
  };
}

function sqlWarehouseCheck(config: AssessmentConfig, approvals: RunApprovals): ValidationCheck {
  const warehouses = config.databricks.workspaces.filter(
    (w) => w.include && w.sqlWarehouseId && w.sqlWarehouseId.trim().length > 0,
  );
  const base = {
    id: 'sql-warehouse-approval' as const,
    title: 'SQL Warehouse auto-start is approved',
    group: 'safety' as const,
    resolvableInUi: true,
  };
  if (warehouses.length === 0) {
    return {
      ...base,
      severity: 'info',
      status: 'skipped',
      detail:
        'No SQL Warehouse is configured, so SQL-backed evidence will not be checked. This is a configuration gap, not proof of missing telemetry.',
    };
  }
  const approved = approvals.approveSqlWarehouseAutoStart || config.databricks.allowSqlWarehouseAutoStart;
  if (!approved) {
    return {
      ...base,
      severity: 'blocker',
      status: 'fail',
      detail: `${warehouses.length} included workspace(s) specify a SQL Warehouse. Read-only system-table collection can auto-start that warehouse and incur DBU charges.`,
      remediation:
        'Approve auto-start explicitly below, or remove the SQL Warehouse ID to run without system-table collection.',
    };
  }
  return {
    ...base,
    severity: 'warning',
    status: 'warn',
    detail: `Auto-start is approved for ${warehouses.length} warehouse(s). Starting a warehouse incurs DBU charges even though every statement is read-only.`,
  };
}

function deepDiveTargetsCheck(config: AssessmentConfig): ValidationCheck {
  const included = config.databricks.workspaces.filter((workspace) => workspace.include);
  const ambiguous = included.length > 1 && DEEP_DIVE_FIELDS.some(
    (field) => config.databricks[field].length > 0 && included.some((workspace) => workspace[field] === undefined),
  );
  const invalidRuns = included.flatMap((workspace) =>
    (workspace.deepDiveJobRunIds ?? config.databricks.deepDiveJobRunIds)
      .filter((id) => !/^\d+$/.test(String(id)))
      .map((id) => `${workspace.name}: ${id}`),
  );
  return {
    id: 'deep-dive-targets', title: 'Deep-dive targets are scoped to workspaces',
    severity: 'blocker', group: 'scope',
    status: ambiguous || invalidRuns.length ? 'fail' : 'pass',
    detail: ambiguous
      ? 'Legacy global deep-dive targets cannot be applied to multiple workspaces. Run IDs are workspace-specific.'
      : invalidRuns.length ? `Job run IDs must be numeric: ${invalidRuns.join(', ')}.`
        : 'Optional targets are scoped to their selected workspace; blank lists skip that optional deep dive.',
    remediation: ambiguous
      ? 'In Configure > Deep-dive targets, assign the legacy targets to their workspace or clear them, then edit each workspace separately.'
      : invalidRuns.length ? 'Enter numeric job run IDs in the corresponding workspace, or clear its optional run list.' : undefined,
  };
}

function readOnlyAcknowledgementCheck(approvals: RunApprovals): ValidationCheck {
  void approvals;
  return {
    id: 'read-only-scanner',
    title: 'Assessment is restricted to read-only operations',
    severity: 'info',
    status: 'pass',
    group: 'safety',
    detail:
      'Assessment collection uses read-only APIs and SQL and never changes resources or permissions. Permission setup is a separate action requiring exact-grant confirmation.',
  };
}
