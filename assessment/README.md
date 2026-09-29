# Azure Databricks Cost Optimization Assessment Toolkit

The assessment toolkit is a customer-controlled, read-only collector and analysis pipeline for Azure Databricks cost evidence. It inventories configured Azure and Databricks scope, preserves raw evidence, normalizes supported datasets, reconciles cost, runs a conservative detector catalog, and renders deterministic workshop reports.

The toolkit does **not** change Azure or Databricks resources, start stopped compute intentionally, implement recommendations, or claim realized savings. Findings are advisory and require human validation.

## Documentation

- [User guide and simplified commands](USER-GUIDE.md)
- [Architecture](docs/architecture.md)
- [Permissions and authentication](docs/permissions-and-authentication.md)
- [Configuration and operations](docs/configuration-and-operations.md)
- [Collector inventory and outputs](docs/collectors-and-outputs.md)
- [Security, reliability, limitations, and troubleshooting](docs/security-reliability-troubleshooting.md)
- [Validation and requirement traceability](docs/validation-and-traceability.md)
- [Mandatory human handoff validation gate](docs/human-handoff-gate.md)
- [Toolkit requirements](../AzureDatabricksAssessmentToolkitRequirements.md)
- [Validated test and live-run evidence](test-results.md)

## Prerequisites

- Windows PowerShell 7 or later.
- Python 3.
- Azure CLI (`az`) signed in to the intended tenant and subscription.
- Network access to `management.azure.com` and every configured Databricks host.
- The least-privilege access in the [permission matrix](docs/permissions-and-authentication.md).
- A reviewed scope JSON based on [assessment-scope.example.json](config/assessment-scope.example.json).

Pester is needed only to run the PowerShell tests.

## Quick start

Run from the repository root:

```powershell
.\assessment\Invoke-Assessment.ps1
```

To pick subscriptions and resource groups, discover Databricks workspaces, and collect/open the report in one command:

```powershell
.\assessment\Invoke-Assessment.ps1 -SelectScope
```

For automation, use `-SubscriptionIds` and `-ResourceGroups` arrays. Full resource-group IDs distinguish same-named groups across subscriptions. `-ConfigPath` supplies customer-specific analysis dates, SQL Warehouse settings, and redaction. Selection is saved with the run, not written over the base config. See the [user guide](USER-GUIDE.md).

The run command prints the unique run root. Start with:

1. `reports/assessment-report.md`
2. `assessment-manifest.json`
3. `collection-status.json`
4. `errors.json`

Do not interpret a `partial`, `pending telemetry`, or empty source as evidence that usage or cost is zero. See [status semantics](docs/security-reliability-troubleshooting.md#status-and-partial-failure-semantics).

## Common commands

### Configuration and static read-only readiness

This validates the scope shape and performs the repository's static mutation-pattern scan. It does not prove live permissions.

```powershell
. .\assessment\scripts\Assessment.Common.ps1
$config = Read-AssessmentConfig -Path .\assessment\config\assessment-scope.example.json
Assert-ReadOnlyAssessment -Config $config
.\assessment\scripts\Test-AssessmentReadOnly.ps1 -Path .\assessment
```

### Live access/readiness collection without analysis

The simplified readiness action performs read-only collection and skips Python analysis:

```powershell
.\assessment\Invoke-Assessment.ps1 -Action Readiness
```

By default, the wrapper temporarily omits SQL Warehouse IDs, so SQL-backed sources are reported unavailable and no Warehouse auto-start is requested. Add `-ApproveSqlWarehouseAutoStart` only when SQL-backed readiness is required. Review `collection-status.json` and each `*.source-status.json`.

### Standard collection and analysis

```powershell
.\assessment\Collect-CostOptimizationAssessment.ps1 `
  -ConfigPath .\assessment\config\assessment-scope.example.json `
  -ContinueOnCollectorError
```

### Azure-only or Databricks-only

```powershell
# Azure only
.\assessment\Collect-CostOptimizationAssessment.ps1 -ConfigPath .\scope.json -SkipDatabricks -ContinueOnCollectorError

# Databricks only
.\assessment\Collect-CostOptimizationAssessment.ps1 -ConfigPath .\scope.json -SkipAzure -ContinueOnCollectorError
```

### Offline analysis of an exported run

Copy an existing run root, including its `raw/` directory and preferably its manifest and collection status, into the customer-controlled analysis environment. Then run:

```powershell
python .\assessment\pipeline\run_assessment.py `
  --config .\scope.json `
  --run-root C:\approved\assessment-export
```

Use the Python pipeline directly for offline analysis. Do not combine `-ExistingRunRoot`, `-SkipAzure`, and `-SkipDatabricks` as an offline shortcut: the PowerShell orchestrator rewrites `collection-status.json` and final manifest status from the collectors executed in that invocation.

### Repeated assessment

```powershell
.\assessment\Collect-CostOptimizationAssessment.ps1 -ConfigPath .\scope-before.json -ContinueOnCollectorError
.\assessment\Collect-CostOptimizationAssessment.ps1 -ConfigPath .\scope-after.json -ContinueOnCollectorError
```

Every new invocation creates a collision-safe run ID using milliseconds and a random suffix. Keep both run roots immutable. The toolkit creates `benefits-baseline.json`, but it does not yet calculate a before/after delta automatically.

### Benefits realization

1. Approve a baseline run and retain its complete run root.
2. Use an equivalent post-change scope, cost basis, currency, and representative window.
3. Run a new standard assessment.
4. Compare the two `benefits-baseline.json`, `cost-reconciliation.json`, and relevant normalized workload datasets.
5. Record workload normalization and human approval outside the generated files.

Never write a realized-savings value solely from list price, a synthetic run, or incomparable windows.

## Validation

```powershell
Invoke-Pester -Path .\assessment\tests -PassThru -Output Normal
python -m unittest -v `
  assessment.tests.test_assessment_contracts `
  assessment.tests.model.test_model_pipeline `
  assessment.tests.reports.test_reports
.\assessment\scripts\Test-AssessmentReadOnly.ps1 -Path .\assessment
```

The validated 2026-09-26 evidence records **58 Pester tests + 28 Python tests = 86 passed**, plus a successful read-only safety scan, live zero-SQL readiness, live SQL-approved readiness, exact no-argument workflow, and Databricks-only Azure scope validation. See [validation and traceability](docs/validation-and-traceability.md) and the [human handoff gate](docs/human-handoff-gate.md).
