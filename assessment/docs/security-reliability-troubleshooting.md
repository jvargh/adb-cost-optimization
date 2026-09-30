# Security, reliability, limitations, and troubleshooting

## Redaction and data handling

Redaction is applied recursively before Databricks raw datasets are written.

| Field pattern/configuration | Behavior |
| --- | --- |
| Secret, password, credential, access-token, or private-key field names | Replaced with `[redacted]`. |
| Spark environment variables and job/task parameter collections | Replaced with `[redacted]`. |
| Query/statement text with `omitQueryText: true` | Replaced with `[omitted]`. |
| Identity-like fields with `hashIdentities: true` | SHA-256 hash. |
| Job/task notification settings | Preserve routing structure and hash recipients; legacy opaque notification hashes remain Unknown during analysis. |
| Notebook paths with `hashNotebookPaths: true` | SHA-256 hash. |
| Catalog/schema/table names with `hashTableNames: true` | SHA-256 hash. |

Set a customer-controlled `ADB_ASSESSMENT_HASH_SALT` (or the configured environment-variable name) before collection. If it is absent, hashing falls back to `customerId:assessmentId`; that fallback is deterministic but is not an appropriate secret salt for sensitive production exports.

Azure raw responses are not passed through the Databricks recursive redactor. Review Azure tags and provider properties before external sharing. The normalized model also preserves the raw source record inside `provenance.raw`; treat the complete run root as sensitive.

Store outputs on encrypted customer-controlled storage, restrict access, define a
retention policy, and inspect exports before sharing. The UI can explicitly delete
selected local snapshots, but automatic retention, encryption, and an external audit
sink are not implemented. Local permission/publication audits are sensitive too.

Imported raw evidence uses a separate recursive redactor before local persistence.
XLSX exports keep formula-like values as inert strings. Neither protection is a
general content-classification guarantee. The HTML report preview omits remote
images and embedded HTML; original downloads remain customer data.

## Status and partial-failure semantics

| Status | Meaning |
| --- | --- |
| `passed` | The source call completed within configured bounds. It does not prove visibility beyond the caller's permissions. |
| `partial` | Some evidence was collected, but a source failed, access was incomplete, or a page limit remained. |
| `failed` | The source/collector could not produce reliable evidence. An empty file may still be preserved, but it is not a successful empty observation. |
| `pending telemetry` | Required configuration, delayed telemetry, or a queryable source was unavailable. It is not zero. |
| `skipped` | The source was intentionally not selected or is outside that collector. Skips alone do not make a run partial. |

A run is `partial` when any collector is `partial`, `failed`, or `pending telemetry`. `-ContinueOnCollectorError` preserves other collector outputs and suppresses the final orchestrator throw; it does not convert failures to success.

## Progress, retry, and timeout behavior

- Domain and collector completion is printed to the console.
- A transcript is stored at `logs/assessment.log`.
- General retries use bounded exponential backoff with a 60-second maximum delay.
  Cost Management additionally paces requests and honors server cooldowns, with a
  separate 600-second wait bound; see [cost request handling](collectors-and-outputs.md#cost-management-request-handling).
- Databricks requests use `requestTimeoutSeconds`.
- SQL statement polling uses `collectorTimeoutSeconds`.
- `maxPages` bounds all supported pagination.
- Azure Cost Management ranges are split into windows of at most 31 days.

Current limitations:

- Azure CLI REST requests have no toolkit-level request timeout. Cost Management's
  separate HTTP transport uses a 120-second request timeout.
- `collectorTimeoutSeconds` applies only to SQL polling, not every collector.
- There is no engine-level whole-run timeout or cancellation checkpoint. The UI
  cancels tracked live processes and marks any created run partial/canceled; it
  does not claim a clean transactional rollback.
- Incremental collection/checkpoint resume is not implemented.
- Databricks GET pagination reports truncation as partial; Azure helpers throw if continuation remains.
- Direct Python re-analysis and CLI Reports rewrite generated files in place.
  UI child re-analysis instead creates a separate run without changing the parent.

## Historical live-run limitations

The 2026-09-26 run was intentionally read-only and completed `partial`, with 13 collector results: 3 passed, 8 partial, 0 failed, 1 pending telemetry, and 1 skipped. The following describes that saved run and code revision, not the current feature set.

- Actual Cost completed with 5,084 rows and 2,642.122153 USD.
- Amortized Cost exhausted bounded retries after HTTP 429.
- Three observed Azure resource types did not support diagnostic settings.
- No Databricks account ID/host was configured, so account workspace and account budget inventory remained pending.
- No SQL Warehouse ID was configured. Billing/list prices, node timeline, query history, system jobs/pipelines, information schema, governance tags, and audit evidence remained pending. This also ensured the toolkit did not auto-start either stopped warehouse.
- Identity collection was disabled.
- Some Unity Catalog binding calls returned `PERMISSION_DENIED` for `READ METADATA`.
- No Spark run IDs or deep-dive table names were selected.
- Full Spark stage/task/executor/UI metrics are not available from the implemented Jobs and cluster-event APIs.
- At that revision, the normalized model covered 20 entity types and the detector
  catalog contained six rules; later capability analysis was not yet present.
- Azure budgets/commitments and some raw Databricks evidence are collected but not all are normalized.
- At that revision, hashed table detail/history filenames were not normalized.
- The single live finding (`MON-MISSING-BUDGET`) is medium-confidence and requires human validation. No savings value was inferred.
- Although reconciliation variance was zero for the selected Actual Cost basis, almost all cost was unmatched to normalized Azure resources; do not interpret zero variance as high attribution quality.

Current code maps 30 entity types, unwraps Azure budgets, recognizes hashed table
detail/history files, and adds capability analysis. This does not rewrite old
snapshots or recover data never collected. Full Spark stage/task analysis, broad
posture coverage, automatic commitment eligibility, and detailed published dashboards
remain outside the [supported subset](../../ui/USER-GUIDE.md#remaining-boundaries).

## Troubleshooting

### Azure CLI authentication or wrong subscription

```powershell
az account show --output table
az login --tenant '<tenant-id>'
az account set --subscription '<subscription-id>'
```

Confirm the configured subscriptions and cost scope match the active identity's access.

### Databricks OAuth token failure

Verify that Azure CLI can request the Databricks application token:

```powershell
az account get-access-token `
  --resource 2ff814a6-3304-4ab8-85cb-cd0e6f879c1d `
  --query expiresOn `
  --output tsv
```

Then verify that the same identity is assigned to the workspace/account and is not blocked by workspace network controls.

### `pending telemetry` for every SQL source

Add a valid `sqlWarehouseId` globally or on each workspace and grant `CAN USE` plus the required system-table privileges. Confirm that auto-start is approved; SQL Statements API execution may start the warehouse.

The UI now discovers warehouse choices and defaults to the smallest running warehouse,
otherwise the smallest stopped one. Existing choices and explicit None are preserved.
Review per-workspace discovery errors if no default is available. Selection does not prove
CAN USE or table access and never approves SQL charges automatically.

### Unity Catalog `PERMISSION_DENIED`

Grant only the required metadata permissions (`BROWSE`/`READ METADATA` as applicable), `USE CATALOG`, `USE SCHEMA`, and `SELECT` for approved system or deep-dive tables. Re-run and confirm the source status rather than assuming an empty catalog.

For `system.lakeflow.pipeline_update_timeline`, the separate **Pipeline timeline permission
setup** panel in Validate can preview and, after exact confirmation, apply the three required
grants to the verified signed-in assessment identity. Existing grant authority is required;
validation never grants access itself. Other table permissions are outside this action.

Use **Check access and preview grants** first. It checks the actual read access before
offering security changes. **Already accessible - no grants needed** means SELECT succeeded,
even if no rows were returned. A failed self-grant does not by itself prove missing read
access. Only a permission-denied SELECT opens the grant preview; other query failures remain
explicit errors without grant recommendations.

If setup is denied, earlier grants may remain applied. If the response is lost, use **Check
setup status** rather than resubmitting. After a host restart, inspect the local
`.ui-server/permission-setup` audit and actual permissions before dismissing unknown status
or retrying. No automatic rollback, retry, elevated login, or alternative principal is used.

A status spinner now stops when polling fails. The remaining safety hold means the outcome
needs review, not that this page is still sending requests. Saved terminal setup outcomes
are recoverable after a restart; stale previews require fresh identity verification.
`User does not have MANAGE on Catalog 'system'` is a grant-authority denial, not a UI failure.
Ask an authorized Unity Catalog administrator to apply the displayed grants. The tool marks
an explicitly rejected statement failed and does not attempt later grants.

### HTTP 429 or throttling

Honor the recorded retry window and avoid overlapping assessments. Cost Management
requests are paced by the client; server cooldowns longer than the supported wait
bound stop collection with an explicit limitation. Reduce the collection window or
retry later before increasing retry limits. One cost basis can remain incomplete
even when another succeeds.

### Jobs redaction or oversized audit results in an older snapshot

Current collectors handle empty notification objects and split audit queries that
exceed the inline response limit into bounded, non-overlapping windows. Historical
failures stay recorded; start a new authorized assessment to collect missing data.
Re-analysis alone cannot repair those source gaps. See the
[recovery regression record](../../ui/docs/capabilities-test-plan.md#partialskipped-indicators-and-final-state-remediation).

### Page limit reached

Increase `analysis.maxPages` only after estimating output volume and retention impact. Databricks outputs retain a partial status; Azure pagination throws rather than discarding continuation silently.

### Output path failure

Use an absolute Windows path or a path relative to the shell's current directory. Ensure the operator can create child directories and files. Each normal run creates a unique directory; it does not overwrite an earlier run.

### Python analysis failed

Run the pipeline directly to expose its error:

```powershell
python .\assessment\pipeline\run_assessment.py --config .\scope.json --run-root C:\path\to\run
```

The pipeline returns exit code 2 for handled file, value, or JSON errors. Inspect `raw/` and retain prior outputs before reanalysis.

### A report says `Insufficient evidence`

Check, in order:

1. `collection-status.json`
2. relevant `*.source-status.json`
3. `errors.json`
4. `source-inventory.json`
5. `telemetry-quality.json`

An empty source can mean a real empty list, restricted visibility, an unconfigured optional source, or unavailable telemetry. Use source status and permissions to distinguish them.
