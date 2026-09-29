# Azure Databricks Cost Optimization Workshop Environment

This directory contains the reproducible infrastructure, Databricks configuration, sample workloads, tests, and operational scripts for the L300 Azure Databricks Cost Optimization Workshop.

## Safety boundary

- Expected subscription: `463a82d4-1896-4332-aeeb-618ee5a5aa93`
- Region: East US
- New resource group pattern: `rg-adb-cost-workshop-<suffix>`
- Existing workspaces `databricks-serverless-ws` and `dbx-lab-test` are out of scope and must remain unchanged.
- Azure deployment is incremental.
- Preview does not authorize deployment.
- Deployment requires both `-Deploy` and `-AcknowledgeCostRisk`.
- Teardown requires the exact resource-group name, expected deployment ID, workshop tags, `-AcknowledgePermanentDeletion`, and PowerShell confirmation.

## Architecture

Bicep creates:

- A dedicated tagged resource group.
- A Premium Azure Databricks workspace with secure cluster connectivity.
- ADLS Gen2 workshop storage with shared-key and anonymous access disabled.
- A system-assigned Azure Databricks Access Connector.
- Storage-scoped `Storage Blob Data Contributor` RBAC.
- A dedicated Log Analytics workspace and Azure Databricks diagnostic setting.
- An optional resource-group budget when approved notification recipients are supplied.

PowerShell configures Databricks workspace objects through short-lived Azure CLI tokens:

- Unity Catalog workshop catalog and schema.
- Managed-identity storage credential and external location.
- Cost-control cluster policy.
- Bounded Classic interactive compute.
- Classic job compute workload.
- Serverless job workload.
- Small serverless SQL Warehouse with five-minute autostop.
- Workshop notebooks, data, and evidence-generating scenarios.

## Prerequisites

- PowerShell 7.
- Azure CLI authenticated to the expected subscription.
- Bicep available through Azure CLI.
- Permission to deploy subscription-scope resource groups and the resources in this template.
- Permission to create role assignments on workshop storage.
- Azure Databricks workspace and account permissions sufficient for Unity Catalog, compute policies, jobs, SQL Warehouses, and serverless compute.
- East US serverless eligibility and an East US Unity Catalog metastore or automatic Unity Catalog enablement.
- Pester 5+ for local tests.
- Checkov for the security scan.

The scripts do not store tokens. Azure Databricks REST calls obtain short-lived tokens from the active Azure CLI identity.

## Parameters

Review [main.bicepparam](./main.bicepparam) before preview:

- Use a unique lowercase `deploymentSuffix`.
- Set the actual owner and cost center.
- Set `reviewAfter`.
- Leave the budget disabled unless approved recipients and an amount are supplied.

Storage account names are globally unique. If the proposed name is unavailable, change only `deploymentSuffix`.

## Local validation

```powershell
az account show --output table
az bicep build --file .\infra\main.bicep
checkov -d .\infra --config-file .\infra\.checkov.yml
Invoke-Pester -Path .\infra\tests
```

The Checkov configuration records six approved non-production exceptions: platform-managed Databricks encryption, public Databricks administration, public storage routing with Entra-only authentication, parameterized storage naming, and LRS sample data. All other findings must be resolved before preview.

## Preview

The deploy script runs Bicep validation and Azure `what-if` but does not deploy unless explicitly instructed:

```powershell
.\infra\scripts\Deploy-WorkshopEnvironment.ps1
```

Review the generated `infra/reports/what-if-*.json`. It must show only additive changes to the dedicated workshop scope. Stop if it modifies or deletes an existing resource.

## Deploy

Deployment creates billable Azure and Databricks resources. Only after reviewing the preview:

```powershell
.\infra\scripts\Deploy-WorkshopEnvironment.ps1 `
  -Deploy `
  -AcknowledgeCostRisk
```

The script writes sanitized outputs to `infra/reports/deployment-outputs.json`.

## Configure Databricks

```powershell
.\infra\scripts\Configure-DatabricksWorkspace.ps1
```

This operation is idempotent. It updates the dedicated workshop objects by name and does not start compute.

The script stops with an explicit error if:

- The `samples` catalog is unavailable.
- Unity Catalog is not ready.
- A bounded Classic node type is unavailable.
- The caller cannot create required workspace objects.
- Serverless object creation is rejected.

## Initialize sample data

```powershell
.\infra\scripts\Initialize-SampleData.ps1
```

The setup workload uses bounded serverless compute and creates objects only in the dedicated `adb_cost_workshop` schema inside the workspace-managed catalog recorded in `infra/reports/databricks-state.json`.

## Run workloads

```powershell
# Run both compute modes
.\infra\scripts\Invoke-WorkshopWorkloads.ps1 -Mode All

# Or run one mode
.\infra\scripts\Invoke-WorkshopWorkloads.ps1 -Mode Classic
.\infra\scripts\Invoke-WorkshopWorkloads.ps1 -Mode Serverless
```

The workload script prints the run ID, clickable run URL, state changes, task states, and elapsed time while polling. If a Classic run reported an Azure capacity stockout in the last six hours, the script fails immediately without starting another billable run. Use `-ForceClassicRetry` only when you intentionally want to retry:

```powershell
.\infra\scripts\Invoke-WorkshopWorkloads.ps1 `
  -Mode Classic `
  -TimeoutSeconds 7200 `
  -PollSeconds 15 `
  -ClassicStartupTimeoutSeconds 600 `
  -ForceClassicRetry
```

Classic runs are automatically canceled if no task starts within ten minutes by default, even when the overall execution timeout is longer. Adjust `-ClassicStartupTimeoutSeconds` if an approved environment routinely needs more startup time. Pressing `Ctrl+C` triggers a best-effort cancellation request for the active Databricks run.

SQL scenario files are under `infra/sql`. They are intended for the dedicated serverless SQL Warehouse recorded in `infra/reports/databricks-state.json`.

## Validate

```powershell
.\infra\scripts\Test-WorkshopEnvironment.ps1
```

Validation outputs:

- Human review and sign-off: [validation-report.md](./reports/validation-report.md)
- Machine-readable status: [validation-summary.json](./reports/validation-summary.json)
- Serverless SQL run evidence: [sql-workload-runs.json](./reports/sql-workload-runs.json)

Complete the manual checklist and sign-off in `validation-report.md` before declaring the environment workshop-ready.

Statuses:

- `passed`: evidence met the requirement.
- `failed`: an actionable validation failure occurred.
- `blocked`: a prerequisite or required artifact is missing.
- `pending telemetry`: operational validation passed, but delayed billing/system-table evidence is not yet visible.

Rerun the same command later for pending billing telemetry.

The validation script requests termination of Classic interactive compute and stops the SQL Warehouse in a `finally` block. Automated validation does not replace the human checks for portal state, Spark UI, query profiles, attribution, workshop usability, and reviewer approval.

## Workshop refresh

Before each workshop:

1. Confirm the expected Azure subscription.
2. Run local validation.
3. Run deployment preview.
4. Re-run the deployment only if infrastructure drift requires it.
5. Re-run workspace configuration.
6. Re-run sample-data initialization.
7. Execute representative workloads far enough in advance for billing telemetry to arrive.
8. Run validation.
9. Confirm no compute remains running.
10. Review and sanitize evidence packs before delivery.

## Cost controls

- Classic interactive auto-termination: 15 minutes.
- Classic job retries: zero.
- Classic worker range: one to two.
- Classic worker and driver use Databricks flexible node types with up to five officially compatible fallback VM SKUs.
- Job timeout: 20 minutes per task.
- SQL Warehouse: `2X-Small`, one cluster maximum, five-minute autostop.
- Sample datasets and concurrency are bounded.
- No infinite loops or uncontrolled retry scenarios.
- Required cost-attribution tags are added to supported compute and jobs.

## Teardown

Preview the exact resource group and tags first:

```powershell
$rg = 'rg-adb-cost-workshop-l300c01'
az group show --name $rg --output json
az resource list --resource-group $rg --output table
```

Then request deletion:

```powershell
.\infra\scripts\Remove-WorkshopEnvironment.ps1 `
  -ResourceGroupName 'rg-adb-cost-workshop-l300c01' `
  -ExpectedDeploymentId 'adb-cost-l300c01' `
  -AcknowledgePermanentDeletion
```

PowerShell requests an additional high-impact confirmation unless `-Confirm:$false` is explicitly supplied. Never use this script for a resource group that lacks the expected workshop tags.

## Generated files

Files under `infra/reports` are runtime artifacts and may contain tenant-specific identifiers. Do not commit reports, tokens, API responses, or customer telemetry. `.gitkeep` exists only to preserve the directory.
