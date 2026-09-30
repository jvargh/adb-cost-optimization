# Architecture

## Data flow

```text
scope JSON
   |
   v
PowerShell orchestrator
   |-- static read-only scan
   |-- Azure collectors -----> raw/azure/*
   `-- Databricks collectors -> raw/databricks/<workspace-key>/*
                                  |
                                  v
Python pipeline
   |-- parse JSON/NDJSON and inventory sources
   |-- normalize into schema 1.0 envelopes
   |-- correlate Azure resources, workspaces, and cost
   |-- reconcile Actual/Amortized cost and DBU list-price evidence
   |-- score telemetry quality and attribution
   |-- run conservative detectors
   `-- render JSON, NDJSON, Markdown, and CSV outputs
```

The entry point is [`Collect-CostOptimizationAssessment.ps1`](../Collect-CostOptimizationAssessment.ps1). Shared safety, retry, run creation, hashing, JSON/NDJSON writing, and status logic live in [`Assessment.Common.ps1`](../scripts/Assessment.Common.ps1). Azure collectors are in [`Azure.AssessmentCollectors.ps1`](../collectors/Azure.AssessmentCollectors.ps1); Databricks domain collectors share [`Databricks.Common.ps1`](../collectors/Databricks.Common.ps1).

The dependency-free Python analysis path is:

- [`run_assessment.py`](../pipeline/run_assessment.py): orchestration and machine outputs.
- [`core.py`](../model/core.py): mapping, normalization, correlation, quality, attribution, and reconciliation.
- [`catalog.py`](../detectors/catalog.py): explainable detector contracts.
- [`render.py`](../reports/render.py): deterministic reports and CSV exports.

## Read-only boundary

Azure calls are restricted to:

- `POST` to Azure Resource Graph.
- `POST` to Azure Cost Management query/forecast endpoints.
- `GET` to approved ARM list/read endpoints.

Databricks calls are restricted to:

- `GET`.
- `POST /api/2.0/sql/statements` for guarded read-only SQL.
- `POST /api/2.0/clusters/events` for historical event queries.
- `POST /api/2.0/mlflow/experiments/search` for optional experiment metadata search,
  using bounded page-token pagination. This does not create or modify experiments.

SQL is rejected when it contains a guarded mutation keyword such as `CREATE`, `ALTER`, `DROP`, `INSERT`, `UPDATE`, `DELETE`, `MERGE`, `OPTIMIZE`, `VACUUM`, `RESTORE`, `TRUNCATE`, `GRANT`, `REVOKE`, `COPY INTO`, or `CALL`. The static scanner adds a repository-level check before every PowerShell-orchestrated run.

This is defense in depth, not a substitute for least-privilege identity assignment. The SQL Statements API may auto-start a configured warehouse; omit `sqlWarehouseId` when compute start is not approved.

## Run lifecycle

1. Parse and validate the scope.
2. reject explicit mutation opt-ins.
3. Run the static read-only scan.
4. Create `assessment-<UTC milliseconds>-<random suffix>` and its `raw`, `normalized`, `reports`, and `logs` directories.
5. Run selected Azure and Databricks domains sequentially.
6. Persist collector results to `collection-status.json`.
7. Unless skipped, run normalization, analysis, detection, and report rendering.
8. Finalize manifest status and transcript.

`partial`, `failed`, and `pending telemetry` collector results make the manifest `partial`. `skipped` alone does not.

## Normalized model

Each mapped record is emitted as NDJSON using this schema 1.0 envelope:

| Field | Meaning |
| --- | --- |
| `schemaVersion` | Current model version, `1.0`. |
| `entityType` | Normalized entity selected by the source-file map. |
| `assessmentRunId` | Manifest run ID or assessment ID fallback. |
| `sourceSystem` | `azure` or `databricks`, derived from source path. |
| `sourceIdentifier` | Preferred entity identifier or deterministic row ordinal fallback. |
| `sourceExtractionTimestamp` | Source timestamp or raw-file modified time fallback. |
| `effectiveStartUtc`, `effectiveEndUtc` | Applicable usage, price, or window times. |
| `customerScope` | Customer ID, assessment ID, and workspace key. |
| `collectionStatus` | Currently `passed` for successfully parsed raw records. |
| `qualityFlags` | Reserved list; currently empty at record level. |
| `sensitivityClassification` | Currently `customer-approved-metadata`. |
| `normalized` | Source record plus canonical fields such as Azure resource ID. |
| `provenance` | Relative source file, record ordinal, and preserved raw record. |

The implementation currently maps 20 entity types: `azure_resource`, `workspace`, `owner`, `azure_cost`, `databricks_usage`, `list_price`, `compute`, `compute_event`, `node_timeline`, `pool`, `job`, `job_run`, `pipeline`, `warehouse`, `query`, `table`, `table_file_summary`, `table_operation`, `policy`, and `budget`.

## Correlation and cost rules

- Azure IDs are slash-normalized, lower-cased, and stripped of a trailing slash.
- Workspaces correlate by workspace name plus resource group; zero matches remain unmatched and multiple matches remain ambiguous.
- Azure costs correlate by canonical resource ID.
- Actual and amortized totals stay separate.
- Effective list-price joins use SKU and half-open price date ranges.
- Multiple currencies are not aggregated.
- Explicit serverless infrastructure cost is excluded from additive totals.
- DBU list-price estimates are not added when Azure cost already contains Databricks service/DBU cost.
- Tax treatment remains unknown unless supplied elsewhere.

## Detector boundary

The implemented detector catalog is intentionally smaller than the requirements catalog:

- Interactive compute auto-termination.
- Fixed-size compute/autoscaling evidence gate.
- Material unowned Azure cost.
- Scheduled job on an existing all-purpose cluster.
- Missing budget evidence.
- Driver on spot capacity.

Every result has evidence, confidence, limitations, no inferred savings by default, and `humanValidationRequired: true`. Missing minimum evidence yields `insufficient_evidence`, not a positive recommendation.
