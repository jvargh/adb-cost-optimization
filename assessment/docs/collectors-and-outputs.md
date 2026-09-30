# Collector inventory and outputs

## Azure collectors

| Collector | Source and operation | Raw outputs | Normalized mapping |
| --- | --- | --- | --- |
| Azure inventory | Azure Resource Graph resource/resource-container union; ARM GET for each Databricks workspace; managed-resource-group correlation; selected ownership tags | `resource-inventory.ndjson`, `databricks-workspaces.json`, `managed-resource-inventory.ndjson`, `tags-ownership-inputs.ndjson` | `azure_resource`, `workspace`, `owner` |
| Azure policy and diagnostics | Resource Graph `policyresources`; ARM diagnostic-settings GET per observed resource | `policy-inventory.ndjson`, `diagnostic-settings.ndjson` | `policy`; diagnostics remain raw-only |
| Azure Cost Management | Daily Cost Management query grouped by resource ID and meter, split into windows of at most 31 days, for Actual and/or Amortized cost | `cost-management.ndjson` | `azure_cost` |
| Azure budgets and commitments | Subscription budgets, reservation orders, Savings Plans | `budgets-commitments.json` | Budget rows map to `budget`; reservations and Savings Plans remain raw-only |
| Azure compute quotas | Regional Compute usage/quota ARM list | `compute-quotas.ndjson` | Raw-only |

All Azure source results are summarized in `raw/azure/source-status.json`.

### Cost Management request handling

Cost query/forecast calls use PowerShell HTTP requests with an Azure CLI access token
so response headers remain available. Other ARM collectors retain their Azure CLI
transport. The Cost Management client sends a stable toolkit `ClientType`, spaces
requests by at least 20 seconds within the process, and honors the largest `Retry-After`
or `x-ms-ratelimit-microsoft.costmanagement-*-retry-after` value.
For 429 responses without a usable header, waits start at 60 seconds and double up to
240 seconds, with 1-5 seconds of jitter. The configured retry count still bounds attempts.
Permanent authorization errors are not retried. Cooldowns over 600 seconds end collection
rather than being shortened; exhausted throttling prevents requests for remaining cost
windows, bases, and scopes. Complete windows already collected remain available, with
the missing coverage recorded explicitly. This is not a tenant-wide quota guarantee.

`Readiness` passes `-CostReadinessOnly -SkipAnalysis`: one one-day aggregate cost access
probe per scope replaces full cost pagination and writes `cost-readiness.json`. Success
is `partial` with an access-only limitation, not evidence of full cost coverage. It is
never used as an assessment baseline. Other readiness collectors are unchanged.

See [Cost Management Query](https://learn.microsoft.com/en-us/rest/api/cost-management/query/usage)
and [Microsoft guidance on Cost Management 429 responses](https://learn.microsoft.com/en-us/answers/questions/1520105/429-error-with-azure-cost-management-api-what-can).

## Databricks collectors

Every included workspace writes under `raw/databricks/<workspace-key>/`.

| Collector | REST/SQL sources | Raw outputs | Normalized mapping |
| --- | --- | --- | --- |
| Workspace | Configured scope; optional Account API workspaces; workspace configuration; current metastore assignment; IP access lists; optional SCIM groups | `workspace-inventory`, `account-workspaces`, `workspace-settings`, `metastore-assignment`, `ip-access-lists`, `groups` | `workspace`, `workspace_settings`, `metastore`; IP lists and groups remain raw-only |
| Billing | `system.billing.usage`, `system.billing.list_prices` | `billing-usage`, `billing-list-prices` | `databricks_usage`, `list_price` |
| Compute | Clusters, cluster policies, policy ACLs, pools, cluster events, `system.compute.node_timeline` | `clusters`, `cluster-policies`, `cluster-policy-permissions`, `instance-pools`, `cluster-events`, `node-timeline` | `compute`, `policy`, `pool`, `compute_event`, `node_timeline`; ACLs raw-only |
| Workloads | Jobs/tasks, runs, pipelines, pipeline details/events, `system.lakeflow.jobs`, job-run timeline, pipeline-update timeline | `jobs`, `job-runs`, `pipelines`, `pipeline-details`, `pipeline-events`, `system-jobs`, `job-run-timeline`, `pipeline-update-timeline` | `job`, `job_run`, `pipeline`; pipeline events raw-only |
| SQL | Warehouse list and `system.query.history` | `sql-warehouses`, `query-history` | `warehouse`, `query` |
| Unity Catalog | Catalogs, bindings, schemas, tables, `system.information_schema.tables`, selected `DESCRIBE DETAIL/HISTORY` | `uc-catalogs`, `uc-catalog-bindings`, `uc-schemas`, `uc-tables`, `table-metadata`, `table-detail-<hash>`, `table-history-<hash>` | `table`, `table_file_summary`, `table_operation`; hashed suffixes are recognized and source paths preserved |
| Governance | Compute policies, billing attribution fields, audit events, optional account budgets | `governance-compute-policies`, `governance-tags`, `governance-audit`, `account-budgets` | `policy`, `budget`; tags/audit remain raw-only |
| Spark deep dive | Selected Jobs API run metadata and related cluster events | `spark-selected-runs`, `spark-cluster-events` | Raw-only; full Spark UI stage/task/executor evidence is not collected |
| Optional assets | Repos, recursive notebook metadata, MLflow experiment search, serving endpoints, SQL alerts, Genie spaces, visible UC volumes | `repos`, `notebooks`, `experiments`, `serving-endpoints`, `sql-alerts`, `genie-spaces`, `uc-volumes` | Same-named normalized entities; notebooks contain metadata, not source code |

Executed workspace domains also write `<collector>.source-status.json`.
Standard collection skips optional assets. Extended selects all seven types by
default; Custom uses the configured list. Denials and collection bounds remain
visible in source status. Databricks collector concurrency is 1-4, default 1.

## SQL source mapping

| SQL asset | Source |
| --- | --- |
| `DatabricksBillingUsage.sql` | `system.billing.usage` |
| `DatabricksListPrices.sql` | `system.billing.list_prices` |
| `DatabricksNodeTimeline.sql` | `system.compute.node_timeline` |
| `DatabricksJobs.sql` | `system.lakeflow.jobs` |
| `DatabricksJobRunTimeline.sql` | `system.lakeflow.job_run_timeline` |
| `DatabricksPipelineTimeline.sql` | `system.lakeflow.pipeline_update_timeline` |
| `DatabricksQueryHistory.sql` | `system.query.history` |
| `DatabricksGovernanceTags.sql` | selected attribution columns from `system.billing.usage` |
| `DatabricksGovernanceAudit.sql` | selected services from `system.access.audit` |
| `DatabricksTableMetadata.sql` | `system.information_schema.tables` |
| `DatabricksTableDetail.sql` | `DESCRIBE DETAIL {{table_identifier}}`, replaced with validated, backtick-escaped identifier components |
| `DatabricksTableHistory.sql` | `DESCRIBE HISTORY IDENTIFIER(:table_name)` |

Time-based SQL uses half-open windows (`>= start`, `< end`) or overlap tests.
Table history uses a parameterized identifier; table detail uses validated identifier
substitution. Audit collection splits oversized inline results into bounded,
non-overlapping time windows; unrecovered failures and truncation remain partial.

## Machine-readable output catalog

| File | Schema/contents |
| --- | --- |
| `assessment-manifest.json` | Schema/toolkit version, IDs, timestamps, status, analysis window, selected scope, collector results, output root. |
| `assessment-config.json` | Effective scope, analysis rules, collection profile, redaction, and output configuration saved with the run. |
| `source-inventory.json` | Raw file path to record count, parse-error count, mapped entity, and reported source statuses. |
| `collection-status.json` | Array of collector result objects: name, status, timestamps, count, outputs, limitations, error. |
| `normalized/<entity>.ndjson` | One schema 1.0 normalized envelope per line. Only entities with at least one record are written. |
| `normalized/correlation.json` | Correlation rules version, workspace matches, matched Azure-cost count, unmatched/ambiguous workspaces. |
| `scope-filter.json` | Databricks input/included/excluded counts and scope-isolation details. |
| `capability-analysis.json` | Selected module datasets, effective rules/version, per-resource findings, workspace coverage, source statuses, and limitations. |
| `cost-reconciliation.json` | Reporting basis/currency, Actual/Amortized totals, collected total, list-price estimate, matched/unmatched/excluded cost, variance/tolerance, duplicate-prevention details, limitations. |
| `telemetry-quality.json` | Overall and per-source confidence levels, score, required-metric gaps, and component metrics. |
| `attribution-coverage.json` | Azure-cost record and spend attribution counts/percentages. |
| `optimization-candidates.json` | Analysis window, findings, candidate count, insufficient-evidence count. |
| `backlog-import.json` | Proposed optimization/evidence-gap items derived from every finding. |
| `benefits-baseline.json` | Baseline ID, time window, reporting basis, authoritative cost, currency, normalization placeholder, `realizedSavings: null`. |
| `errors.json` | Parse/read errors plus collector `partial`, `failed`, and `pending telemetry` records. |

The model and capability format versions are currently `1.0`. Core machine outputs
are pretty-printed and key-sorted; capability output is JSON without a key-order
guarantee. Normalized data is deterministic NDJSON. Raw PowerShell JSON is UTF-8
and may preserve provider-specific shapes.

UI operations add artifacts only when requested:

| File | Purpose |
| --- | --- |
| `.ui-review.json` | Saved human decisions; saving also updates the sign-off CSV without regenerating Markdown. |
| `import-provenance.json` | Declared import files, dataset mappings, row counts, hashes, and completeness limitations. |
| `reports/capability-workbook-<revision>.xlsx` | Full-run Summary, Rules, Quality, Review, Findings, and selected module sheets. |
| `reports/scenario-<digest>.json` | Commitment calculation over supplied hourly demand and price inputs. |

Child re-analysis creates a separate run with `parentRunId` and `analyzedAtUtc` in
its manifest, preserving the original evidence and review. It cannot fill collection gaps.

## Report catalog

The renderer creates one consolidated Markdown report:

- `reports/assessment-report.md`

The report contains 17 ordered sections covering executive summary through human validation and sign-off.

It also creates:

- `top-cost-drivers.csv`
- `prioritized-backlog.csv`
- `human-validation-sign-off.csv`

Reports are reproducible from machine outputs and should not be hand-edited. Missing evidence is rendered explicitly; unknown savings remains `Not estimated`.
