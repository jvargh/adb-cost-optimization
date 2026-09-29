# Configuration and operations

## Scope configuration

Copy [`assessment-scope.example.json`](../config/assessment-scope.example.json) and review every value. The current parser requires:

- non-empty `customerId` and `assessmentId`;
- `analysis.startUtc` earlier than `analysis.endUtc`;
- at least one Azure subscription or included Databricks workspace;
- positive `maxPages`, `pageSize`, `requestTimeoutSeconds`, and `collectorTimeoutSeconds` when present;
- non-negative `retryCount` and `retryBaseSeconds` when present.

### Implemented fields

| Path | Current behavior |
| --- | --- |
| `azure.subscriptions` | Resource Graph, budget, quota, and default cost scope inputs. |
| `azure.resourceGroups` | Legacy group-name filter across selected subscriptions; prefer qualified IDs for multi-subscription scopes. |
| `azure.resourceGroupIds` | Full ARM resource-group IDs; when populated, take precedence over group names. The picker writes these to prevent same-name cross-subscription ambiguity. |
| `azure.costScopes` | ARM scopes for Cost Management queries across multiple subscriptions. The picker writes one scope per selected subscription. |
| `azure.costScope` | Legacy single Cost Management scope. Scope selection replaces it with `costScopes`. Without either field, all selected subscriptions are queried. |
| `azure.costBasis` | Supports only `ActualCost` and `AmortizedCost`; other values are skipped with a limitation. |
| `azure.currency` | Reporting fallback; no currency conversion occurs. |
| `azure.includedRegions` | Optional quota regions, combined with discovered workspace locations. |
| `azure.reportingCostBasis` | Optional reconciliation basis; defaults to `ActualCost`. |
| `databricks.workspaces[]` | `include: true` selects a workspace. `workspaceUrl` is required for live API calls; `workspaceId` is the preferred output key. |
| `databricks.accountId`, `accountHost` | Optional pair, editable in the UI. An account UUID and accounts hostname without scheme/path enable account workspace and budget inventory; live permissions are still required. |
| `databricks.sqlWarehouseId` | Default warehouse for all SQL sources. |
| `databricks.workspaces[].sqlWarehouseId` | Per-workspace override. In the UI, an absent choice receives the smallest running, otherwise smallest stopped, discovered warehouse. An explicit empty string preserves None; existing IDs are retained. |
| `databricks.includeIdentities` | Enables SCIM group collection. |
| `databricks.workspaces[].deepDiveJobRunIds` | Selects Jobs API records and related cluster events only in that workspace; IDs must be numeric. An empty array skips the optional deep dive. |
| `databricks.workspaces[].deepDiveTableNames` | Selects `DESCRIBE DETAIL` using validated, backtick-escaped identifier components and `DESCRIBE HISTORY` using a parameterized identifier, only in that workspace. Accepts one to three SQL name components, not SQL expressions or paths. |
| `databricks.deepDiveJobRunIds`, `deepDiveTableNames` | Legacy fallback only when one workspace is included and its corresponding field is absent. Explicit workspace arrays, including empty arrays, override the legacy list. Ambiguous global targets are rejected rather than queried across multiple workspaces. |
| `analysis.maxPages` | Bounds Azure, Databricks GET/POST, SCIM, and SQL chunk pagination. |
| `analysis.pageSize` | Page-size hint, capped where an endpoint imposes a smaller maximum. |
| `analysis.requestTimeoutSeconds` | Databricks HTTP request timeout. Azure CLI REST calls currently have no equivalent explicit timeout. |
| `analysis.collectorTimeoutSeconds` | Deadline for a pending Databricks SQL statement; not a whole-collector timeout. |
| `analysis.retryCount`, `retryBaseSeconds` | Bounded exponential retries, capped at 60 seconds per delay. |
| `thresholds.materialMonthlyCost` | Material-cost detector threshold. |
| `thresholds.interactiveAutoTerminationMinutes` | Interactive auto-termination detector boundary. |
| `redaction.*` | Controls identity, notebook-path, table-name hashing and query-text omission. |
| `outputs.root` | Parent for unique run directories; relative paths resolve from the current shell directory. |

Several example fields are recorded for future compatibility but are not consumed by current collectors or detectors, including `includeManagementGroups`, `includeQueryText`, `includeNotebookPaths`, most threshold fields, and output format/retention booleans. Do not assume those values disable file creation or collector surfaces.

The UI's warehouse defaults do not start compute or approve SQL charges. Approve warehouse
use explicitly in Validate; initial live load and included workspace/warehouse changes clear
previous approval. Historical snapshots retain their recorded scope. CLI scope configuration
does not run the UI's warehouse selection policy.

Optional **Pipeline timeline permission setup** in Validate is separate from collection.
It verifies the signed-in assessment identity and checks pipeline timeline read access.
Accessible tables, including empty ones, need no grants. An explicit permission denial
previews exactly three grants and requires a second confirmation. Other query failures
do not produce a grant preview. It cannot grant authority the caller does not already have. See
[permissions and authentication](permissions-and-authentication.md#separate-confirmed-pipeline-timeline-setup)
for the procedure, shared-metastore impact, and partial/unknown-outcome handling.

Table-detail/history filenames include a hash of the selected table; normalization maps
these files into table evidence while retaining their original provenance. Azure budget
inventory is unwrapped separately from reservations and savings plans. Billing list prices
may be JSON strings; effective list prices take precedence over default prices. Invalid
prices remain explicit evidence gaps. Reconciliation keeps Actual and Amortized bases
separate and does not exclude a Databricks service charge merely because its meter includes
the word "Compute".

SQL result rows retain their column alignment, including single-row responses and result
chunks. A row whose cell count differs from the declared schema is rejected explicitly;
malformed result shapes do not become successful records padded with nulls.

The UI migrates legacy targets from a single included workspace before selecting additional
workspace groups. For an ambiguous imported multi-workspace configuration, choose the
workspace for the legacy targets or clear the unassigned lists in Configure. No workspace
ownership is inferred from a numeric run ID. Scope-picker reselection retains explicitly
workspace-scoped targets for matching workspaces and clears old global lists as before.

The separate [`allocation-rules.example.json`](../config/allocation-rules.example.json) and [`tag-taxonomy.example.json`](../config/tag-taxonomy.example.json) are documented examples. The current entry point does not load them automatically.

## Safe scope template

```json
{
  "customerId": "customer-code",
  "assessmentId": "adb-cost-assessment",
  "azure": {
    "subscriptions": ["00000000-0000-0000-0000-000000000000"],
    "resourceGroups": ["approved-rg"],
    "costScope": "/subscriptions/00000000-0000-0000-0000-000000000000",
    "costBasis": ["ActualCost"],
    "currency": "USD"
  },
  "databricks": {
    "workspaces": [
      {
        "name": "approved-workspace",
        "workspaceUrl": "adb-example.azuredatabricks.net",
        "workspaceId": "123456789",
        "include": true,
        "deepDiveJobRunIds": [],
        "deepDiveTableNames": []
      }
    ],
    "includeIdentities": false,
    "deepDiveJobRunIds": [],
    "deepDiveTableNames": []
  },
  "analysis": {
    "startUtc": "2026-08-01T00:00:00Z",
    "endUtc": "2026-09-01T00:00:00Z",
    "timeZone": "UTC",
    "maxPages": 100,
    "pageSize": 1000,
    "requestTimeoutSeconds": 120,
    "collectorTimeoutSeconds": 1800,
    "retryCount": 3,
    "retryBaseSeconds": 2
  },
  "redaction": {
    "hashIdentities": true,
    "hashTableNames": true,
    "hashNotebookPaths": true,
    "omitQueryText": true,
    "saltEnvironmentVariable": "ADB_ASSESSMENT_HASH_SALT"
  },
  "outputs": {
    "root": "./assessment/output"
  }
}
```

## Operating workflows

### Interactive or explicit scope selection

From the repository root:

```powershell
.\assessment\Invoke-Assessment.ps1 -SelectScope
```

The picker lists enabled subscriptions in the current Azure CLI tenant, then resource groups with subscription IDs. Enter comma-separated indexes, `*` for all displayed choices, or `q` to cancel. Invalid, inaccessible, ambiguous, or empty-workspace scopes stop before collection. Cross-tenant selection is not supported in one run because Databricks authentication uses the active CLI tenant.

For unattended use, pass `-SubscriptionIds <id[]> -ResourceGroups <name-or-full-id[]>`. Without group inputs, discover all Databricks workspaces in the selected subscriptions and derive their workspace groups. With group inputs alone, use the base config's subscriptions. These inputs are valid for `Run` and `Readiness` only, and cannot be combined with `-SelectScope`.

The base config supplies non-scope settings. Old global SQL Warehouse IDs are retained only as per-workspace settings for matching configured workspaces; no Warehouse is chosen for newly discovered targets. Global job/table deep-dive selections are cleared. Customer configuration files are not overwritten.

Every new run persists `assessment-config.json`; `-Action Reports` uses this snapshot unless explicitly overridden with `-ConfigPath`. The manifest records qualified `resourceGroupIds`. `-OutputRoot` is resolved relative to the invocation directory, and relative `-ConfigPath` works from either the repository or assessment directory. See the [user guide](../USER-GUIDE.md) for examples and approval behavior.

### Readiness

Run configuration and static validation first:

```powershell
. .\assessment\scripts\Assessment.Common.ps1
$config = Read-AssessmentConfig -Path .\scope.json
Assert-ReadOnlyAssessment -Config $config
.\assessment\scripts\Test-AssessmentReadOnly.ps1 -Path .\assessment
```

For real permission/source readiness, run collection without analysis:

```powershell
.\assessment\Collect-CostOptimizationAssessment.ps1 `
  -ConfigPath .\scope.json `
  -SkipAnalysis `
  -ContinueOnCollectorError
```

This is a real collection, not a zero-cost probe. If `sqlWarehouseId` is present, SQL statements can auto-start the warehouse.

### Standard collection

```powershell
.\assessment\Collect-CostOptimizationAssessment.ps1 `
  -ConfigPath .\scope.json `
  -ContinueOnCollectorError
```

Without `-ContinueOnCollectorError`, an unhandled domain error results in a final throw. Individual source failures are normally captured as `partial`, `failed`, or `pending telemetry` results.

### Analysis-only/offline

```powershell
python .\assessment\pipeline\run_assessment.py `
  --config .\scope.json `
  --run-root C:\approved\exported-run
```

Required input is a `raw/` tree. For faithful provenance and limitations, include `assessment-manifest.json`, `collection-status.json`, and source-status JSON files. If the manifest is absent, the pipeline uses the assessment ID and analysis settings from the supplied config.

### Repeat or resume

- Run the main entry point again without `-ExistingRunRoot` for an independent repeated assessment.
- Use `-ExistingRunRoot` only when deliberately recollecting or reanalyzing that exact run directory.
- The orchestrator rewrites `collection-status.json` from collectors executed in the current invocation and recalculates final manifest status. Preserve a copy before any resume operation.

### Benefits realization

The current implementation produces a versioned baseline artifact but no automated cross-run comparator. A valid benefits review must:

- retain the approved baseline;
- use the same reporting basis and currency;
- select comparable windows;
- supply a workload-normalization factor where business volume changed;
- confirm technical and service outcomes;
- obtain human sign-off.

## Progress and time limits

- Console output identifies run ID, root, analysis window, active domain, and each completed collector result.
- `logs/assessment.log` captures a PowerShell transcript.
- Collector/source JSON records start/end times, counts, outputs, limitations, and errors.
- Azure and Databricks pagination stops at `maxPages`; Azure list/query helpers fail when a continuation remains, while Databricks helpers mark results `partial`.
- Retries are bounded by `retryCount` with exponential delays.
- Databricks HTTP calls use `requestTimeoutSeconds`.
- Pending SQL statements poll every two seconds until `collectorTimeoutSeconds`.
- No global cancellation checkpoint, incremental collection checkpoint, or whole-run timeout is currently implemented.
