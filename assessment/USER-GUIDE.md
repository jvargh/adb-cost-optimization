# Azure Databricks Assessment Toolkit User Guide

For the full workshop, lab, toolkit, output, validation, and remaining-work requirements, see the [consolidated end-to-end specification](../docs/AzureDatabricksCostOptimizationEndToEndSpecification.md). This guide remains the concise operator reference.

## Using the browser UI and new analyses

Start `.\ui\Start-AssessmentUi.ps1` from the workspace root, then follow the
[UI user guide](../ui/USER-GUIDE.md). It documents all CAP-01 through CAP-13 entry points,
profiles, utilization/sizing/jobs/queries/network, the supported posture subset, assets,
offline CSV/JSON import, child re-analysis, commitment-input requirements and XLSX.
The [recorded acceptance plan](../ui/docs/capabilities-test-plan.md) includes test results
and screenshots. Local import/re-analysis do not contact Azure or Databricks.
The optional UI dashboard publisher is separately approved and is not part of this
read-only CLI collector. No scanner notebook/wheel deployment is required.

## Pick the customer scope and run

With Azure CLI signed in (`az login`), run this from the repository root:

```powershell
.\assessment\Invoke-Assessment.ps1 -SelectScope
```

Or, from the `assessment` directory:

```powershell
.\Invoke-Assessment.ps1 -SelectScope
```

1. Select one or more subscriptions by entering their numbers, such as `1,3`.
2. Select one or more resource groups. Each group shows its subscription ID so same-named groups are unambiguous.
3. The command discovers Databricks workspaces, collects evidence, generates **one consolidated report**, and opens it.

Use `*` for all displayed choices, or `q` to cancel before collection. Empty or invalid input stops without starting an assessment. Only enabled subscriptions in the active Azure CLI tenant are offered; use a separate login/run for another tenant. Listing groups and workspaces requires Azure Reader access in the selected subscriptions. A discovery failure stops the run rather than falling back to broader scope.

Selection replaces the base config's Azure/workspace targets for **this run only**. It does not overwrite your local/workshop scope. Analysis dates, customer ID, redaction, thresholds, and other settings still come from the base config; use `-ConfigPath` for a customer-specific base. Review the printed analysis window.

Workspace resource groups, associated managed resource groups, and explicitly selected supporting groups define the report boundary. Unrelated subscription resources and costs remain excluded. If no Databricks workspace is found, the command stops without broadening the scope.

Filtering is at resource-group level, not individual-resource classification within a shared group. Select supporting groups deliberately; mixed-use groups can contain shared or non-Databricks costs that require human allocation review.

**SQL evidence:** existing SQL Warehouse settings are retained only for matching previously configured workspaces, never copied to newly discovered workspaces. New workspaces without a configured Warehouse report SQL-backed sources as unavailable. This does not mean their cost is zero. Existing auto-start approval rules still apply. Global deep-dive IDs are cleared during reselection to prevent querying the wrong workspace.

## Run a saved scope

Open PowerShell in the repository and run one command:

```powershell
Set-Location C:\Users\varghesejoji\Desktop\squad-test\adb-cost-optimization\assessment
.\Invoke-Assessment.ps1
```

That command:

1. Uses `config\assessment-scope.local.json` when present; otherwise it uses `config\workshop-scope.json`.
2. Runs the read-only safety check.
3. Collects Azure and Databricks evidence.
4. Continues through sources that are partial, throttled, unavailable, or permission restricted.
5. Normalizes and correlates evidence.
6. Reconciles Azure and Databricks cost.
7. Runs cost-optimization detectors.
8. Generates one consolidated Markdown report.
9. Opens that report automatically.

No arguments preserves the existing saved-config workflow; it does not silently switch subscriptions.

## Supply scope without prompts

Single subscription and group (replace the example ID/name):

```powershell
.\Invoke-Assessment.ps1 -SubscriptionIds '<subscription-id>' -ResourceGroups 'rg-databricks'
```

Multiple subscriptions and groups:

```powershell
.\Invoke-Assessment.ps1 `
  -SubscriptionIds '<subscription-a>', '<subscription-b>' `
  -ResourceGroups '/subscriptions/<subscription-a>/resourceGroups/rg-data', `
                  '/subscriptions/<subscription-b>/resourceGroups/rg-data'
```

- Use full resource-group IDs when a name exists in multiple selected subscriptions. Ambiguous bare names are rejected.
- Omit `-ResourceGroups` to discover all Databricks workspaces in the selected subscriptions. Only their workspace/managed groups enter the default boundary, not every group in those subscriptions.
- `-ResourceGroups` alone uses the subscriptions from the base config.
- `-SelectScope` cannot be combined with the explicit scope parameters.
- Both forms work with `-Action Readiness`; readiness omits SQL Warehouse IDs unless `-ApproveSqlWarehouseAutoStart` is explicitly supplied.
- Add `-NoOpenReport` for automation. Add `-OutputRoot <directory>` to choose where new runs are written.

## Report location

Each run creates:

```text
assessment\output\<run-id>\reports\assessment-report.md
```

The consolidated report contains:

- Executive summary
- Estate topology and scope
- Current cost baseline and reconciliation
- Top cost drivers
- Unattributed cost
- Compute and right-sizing assessment
- SQL Warehouse and query assessment
- Jobs and pipelines
- Spark deep-dive evidence
- Delta and data-layout assessment
- Governance, policies, budgets, and FinOps
- Commitment readiness
- Telemetry quality and limitations
- Prioritized backlog
- 30/60/90-day roadmap
- Benefits realization
- Human validation and sign-off

Three optional CSV exports remain beside the report:

- `top-cost-drivers.csv`
- `prioritized-backlog.csv`
- `human-validation-sign-off.csv`

Machine-readable evidence remains in the run root for traceability. Each new run also saves `assessment-config.json`, containing its resolved scope/settings, and `assessment-manifest.json`, containing the selected subscription and qualified resource-group IDs. Protect these customer-specific files with the raw evidence.

## First-time customer configuration

Create a customer scope:

```powershell
.\Invoke-Assessment.ps1 -Action Initialize
```

Edit:

```text
config\assessment-scope.local.json
```

The picker replaces manual subscription, resource-group, and workspace entry. Still review:

- Azure subscriptions and resource groups
- Cost scope and date range
- Databricks workspaces
- SQL Warehouse ID, when system-table collection is required
- Deep-dive run and table IDs
- Redaction settings

If a SQL Warehouse ID is configured, record approval once:

```json
"databricks": {
  "allowSqlWarehouseAutoStart": true,
  "sqlWarehouseId": "<warehouse-id>"
}
```

Read-only SQL collection may auto-start that Warehouse and incur DBUs. Configure autostop before running. The toolkit does not stop compute because it is read-only.

## Recreate the latest report without recollecting

```powershell
.\Invoke-Assessment.ps1 -Action Reports
```

This uses the newest run and opens the regenerated consolidated report. New runs use their saved `assessment-config.json`, not a potentially changed local scope. An explicit `-ConfigPath` overrides that snapshot. Older runs without a snapshot retain the existing config precedence.

For a run outside the default output directory:

```powershell
.\Invoke-Assessment.ps1 -Action Reports -RunRoot 'C:\assessments\<run-id>'
```

## Open the latest report

```powershell
.\Invoke-Assessment.ps1 -Action Open
```

## Validate the toolkit

```powershell
.\Invoke-Assessment.ps1 -Action Validate
```

## Optional switches

| Switch | Purpose |
|---|---|
| `-SelectScope` | Interactively select subscriptions and groups, discover workspaces, and run |
| `-SubscriptionIds <id[]>` | Select one or more subscriptions without prompts |
| `-ResourceGroups <name-or-id[]>` | Select groups; full IDs disambiguate identical names |
| `-ConfigPath <path>` | Use a specific scope file |
| `-OutputRoot <path>` | New-run output directory; for Reports/Open, where to look for the latest run |
| `-NoOpenReport` | Do not open the generated report |
| `-FailOnCollectorError` | Stop instead of producing a partial assessment |
| `-ApproveSqlWarehouseAutoStart` | One-run approval when it is not stored in the scope |

## Status interpretation

| Status | Meaning |
|---|---|
| `completed` | Configured collection and analysis completed |
| `partial` | Some sources were throttled, unavailable, permission restricted, or intentionally omitted |
| `pending telemetry` | The source is valid, but records have not arrived |
| `skipped` | The source or deep dive was not selected |
| `failed` | A collector failed and preserved an explicit error |

Never interpret missing, partial, pending, or skipped evidence as zero cost or proof of healthy behavior.

Intentional skips do not make the aggregate run partial. Spark deep dive is skipped
when no per-workspace job run IDs are selected; optional assets are skipped when no
asset types are selected. Enable these only when their evidence is needed.

Governance audit collection automatically splits a time window when Databricks
rejects its INLINE result for exceeding 25 MiB. Sub-windows keep the original
inclusive start/exclusive end boundaries, so boundary events are not duplicated.
`analysis.maxPages` bounds SQL-window attempts (including rejected attempts) and
continues to bound chunk pages within each query. A remaining window or truncated
result is explicitly partial; a non-size error is not suppressed. The configured SQL
timeout remains per statement, not a whole-assessment deadline. Splitting can add SQL
work and duration within the approved warehouse scope.

Empty JSON job-notification objects are supported without weakening identity
redaction. These collector fixes apply to new collection, not existing snapshots.

## Safety

- Azure and Databricks collection is read-only.
- SQL statements are checked for mutations.
- Access tokens are not persisted.
- Query text and identities follow scope redaction settings.
- The user-facing report preserves evidence links and confidence.
- The SQL Warehouse used by the workshop has five-minute autostop.
