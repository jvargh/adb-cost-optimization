/**
 * Pre-flight validation contract. The UI must refuse to launch a run while any
 * `blocker` is unresolved, mirroring the guard clauses in
 * `assessment/Invoke-Assessment.ps1`.
 */

export type ValidationSeverity = 'blocker' | 'warning' | 'info';

export type ValidationCheckId =
  | 'capability-plan'
  | 'customer-id'
  | 'assessment-id'
  | 'auth-context'
  | 'azure-cli'
  | 'python-runtime'
  | 'powershell-version'
  | 'read-only-scanner'
  | 'subscription-selected'
  | 'resource-group-selected'
  | 'workspace-selected'
  | 'rbac-cost-management'
  | 'rbac-reader'
  | 'databricks-token'
  | 'databricks-account-config'
  | 'sql-warehouse-approval'
  | 'system-tables-access'
  | 'analysis-window'
  | 'output-writable'
  | 'scope-conflict'
  | 'deep-dive-targets'
  | `readiness-warning-${number}`
  | `readiness-source-${number}`
  | `readiness-incomplete-${string}`;

export interface ValidationCheck {
  id: ValidationCheckId;
  title: string;
  severity: ValidationSeverity;
  status: 'pass' | 'fail' | 'warn' | 'skipped' | 'running';
  detail: string;
  /** Remediation shown inline when status is fail/warn. */
  remediation?: string;
  /** Source-level responses supporting a grouped readiness issue. */
  evidence?: { source: string; detail: string }[];
  /** Set when the user can clear the check from the UI (e.g. approvals). */
  resolvableInUi?: boolean;
  group: 'environment' | 'scope' | 'permissions' | 'safety';
}

export interface ValidationReport {
  generatedAtUtc: string;
  checks: ValidationCheck[];
  blockerCount: number;
  warningCount: number;
  canRun: boolean;
  /** True when the scope contains a warehouse id and approval is still missing. */
  requiresSqlWarehouseApproval: boolean;
}

export interface ValidationProgressStep {
  id: string;
  title: string;
  status: ValidationCheck['status'] | 'pending' | 'not-applicable';
  detail: string;
  issues?: Pick<ValidationCheck, 'title' | 'detail' | 'remediation' | 'evidence'>[];
  startedAtUtc: string | null;
  finishedAtUtc: string | null;
  estimatedSeconds: number;
}

export interface ValidationProgress {
  validationId: string;
  status: 'running' | 'completed' | 'failed';
  startedAtUtc: string;
  finishedAtUtc: string | null;
  lastActivityAtUtc: string;
  message: string;
  steps: ValidationProgressStep[];
}
