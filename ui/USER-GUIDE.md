# Assessment UI user guide

Updated 2026-09-29 for the CAP-01 through CAP-13 implementation.
See the [recorded test plan](docs/capabilities-test-plan.md) for verified behavior and
live-test boundaries. The [CLI guide](../assessment/USER-GUIDE.md) remains the reference
for running the toolkit without the UI.

## Start or update the app

From the workspace root:

```powershell
.\ui\Start-AssessmentUi.ps1
```

Open `http://127.0.0.1:8765`. If updating an already running installation, finish active
operations, stop its launcher with Ctrl+C, run the command again, and refresh the browser.
Changing frontend files alone does not reload the Python backend. These capabilities
require backend version `2026.09.29.1` or later, visible at `/api/health`.
Existing snapshots and review decisions remain on disk.

Use a desktop-width window for dense evidence tables. Narrow screens retain navigation
and horizontally scrollable tables. The header's Light/Dark control changes the theme.

## Native assessment: the five steps

1. **Configure:** select subscription, groups, workspaces, analysis window and warehouses.
   Review **Analysis modules, rules and collection profile**.
2. **Validate:** explicitly approve any warehouse auto-start/charges, then run validation.
   The Run/Retry/Re-run validation button is above the progress area and stays there
   while checks run; approvals are locked until the active operation finishes.
   Resolve the reported permission issues. Green pipeline-table checks do not certify
   access to every optional asset API; those calls preserve their own denied/partial states.
3. Select the single **Continue to run** button **beneath** the permission content.
   On **Run analysis**, select **Start read-only assessment**.
4. After collection, select **Visualize results**. A partial run is still reviewable.
5. **Review & export:** download or preview the report immediately. If useful, expand
   **Record a decision**, select a finding, supply a decision and reviewer, optionally
   add a note, then **Save review decisions**. Review is optional for export.

No new tab, rule edit, snapshot selection, import preview or dashboard preview starts a
cloud assessment. Nothing resizes resources, buys commitments or silently grants access.
The existing explicitly confirmed permission-setup flow is unchanged.

### Partial, skipped, and the final color

Completed checks no longer display the gray "no checks are running" banner.
Saved Configure/Validate/Run pages and Evidence quality show a final collection outcome:

- **Green:** the run succeeded and every collected source passed. Intentional skips
  remain visible and are not counted as passes.
- **Red:** partial, failed, or pending evidence; a failed run; or no collected checks
  to verify. Red means review the source limitations, not that all findings are unusable.
- While viewing a snapshot, Validate is labeled **Saved collection checks**. Its color
  describes recorded collection evidence, not a fresh permissions check or an invented
  historical readiness report. Live validation still uses its own blockers/readiness.

Partial/skipped reasons are expanded in the saved checks panel. The recent run had
22 passed, 4 partial, and 4 skipped collectors:

| Indicator | Cause and action |
| --- | --- |
| Workloads partial in two workspaces | Empty job notification objects triggered a redaction error. Fixed; start a new assessment to collect the missing jobs. |
| Governance partial in two workspaces | Audit output exceeded Databricks' 25 MiB inline limit. Fixed with bounded, non-overlapping time-window splitting. Errors and remaining truncation still stay partial. |
| Spark deep dive skipped in three workspaces | No job run IDs were selected. Optional: enter **Job run IDs** for each workspace in Configure if you need run metadata. Full Spark metrics still require separate Spark UI/event-log review; no event-log importer is implemented. |
| Optional assets skipped | Standard collection did not select assets. Choose **Extended: include asset metadata** or select specific assets under Custom for a new assessment. |

The Databricks governance note that Azure budgets/policy are handled elsewhere is
not a failure; the separate Azure collectors supply that evidence. No extra grants
are needed to fix the two code defects above.

Existing snapshots are immutable historical evidence: refresh to see the clearer
red/green display, but collect a **new assessment** to replace missing evidence.
Re-analysis alone cannot recover data that was never collected. Do not enable
optional sources solely to remove gray skipped badges.

## Profiles, modules and rules

| Setting | Behavior |
| --- | --- |
| Standard | Existing core collection; optional asset types off |
| Extended | Existing core collection plus all seven optional metadata types |
| Custom | Your selected assets and analysis modules |
| Concurrent Databricks collectors | Integer 1-4; default 1. Bounds collector workers, not global HTTP requests across all processes |
| Enabled analyses | Controls generated capability datasets/findings; does **not** skip the existing core source collectors |

Extended collection can encounter additional access restrictions and take longer.
Notebook collection lists metadata only, never exports source. UC volumes are discovered
through visible catalogs/schemas. Bounds, denials and truncation remain visible under
Evidence quality. The collector uses existing request/retry behavior.

Expand **Versioned analysis thresholds** to edit or import/export a flat rules JSON:

```json
{
  "idleCpuPercent": 10,
  "busyCpuPercent": 80,
  "highMemoryPercent": 80,
  "minimumSamples": 30,
  "slowQuerySeconds": 60,
  "failureRatePercent": 10
}
```

Values must be positive; percentages cannot exceed 100; minimum samples must be an
integer. Idle CPU must be less than busy CPU. Sample count and slow-query seconds have
an upper bound of 100,000. Unknown fields are rejected by the backend.
**Reset rules** asks for confirmation. Rules and their version hash are saved with the run.

## Results: where each capability lives

Use the grouped **Overview / Technical / Decisions** navigation. Scope filters use
workspace IDs for new results, so same-named workspaces remain independent.
New evidence tables support server-side search, sorting and 50-row pages. Sorting and
query summaries operate over the matching saved dataset, not only the visible page.
Workload/category filters are finding filters; they do not filter every capability table.

| Capability | Location and interpretation |
| --- | --- |
| CAP-01 Utilization | Compute and SQL > Utilization. CPU/memory means, CPU p95/peak, idle proportion, sample counts; select a resource and a driver/worker instance for its chart |
| CAP-02 Sizing | Compute and SQL > Sizing. Observed fixed/autoscaling configuration and conservative benchmark candidates; no inferred resize quantity or monetary savings |
| CAP-03 Job health | Compute and SQL > Job health. Observed runs/failures, job/task failure email or webhook routing, tasks and retry evidence |
| CAP-04 Queries | Queries. Individual query duration/queue evidence, warehouse summaries and protected-user summaries; no per-query currency allocation |
| CAP-05 Network | Compute and SQL > Network. Node traffic in MiB and CPU-wait evidence; details include interval receive rates |
| CAP-06 Posture | Posture. **Two supported checks**: IP access list setting and UC metastore assignment. Pass/Fail/Unknown; not a comprehensive security/compliance assessment |
| CAP-07 Assets | Assets. Repos, notebook metadata, MLflow experiments, serving endpoints, SQL alerts, Genie spaces and UC volumes |
| CAP-08 Workbook | Review & export > Excel workbook; select module sheets, generate, then download the XLSX from the artifact table |
| CAP-09 Rules/re-analysis | Configure, or Evidence quality > Inspect effective rules / create another analysis |
| CAP-10 Commitments | Cost analysis > Commitment opportunities; explicit saved hourly inputs and a proposed node quantity |
| CAP-11 Import | Header > Import evidence, or open `http://127.0.0.1:8765/?import=1` to avoid Azure discovery entirely |
| CAP-12 Publication | Review & export > Optional dashboard publication. **Coverage counts only**, separately approved cloud write |
| CAP-13 Profiles/concurrency | Configure > Analysis modules, rules and collection profile |

### Metric cautions

- Utilization means are weighted by observed node duration; p95 uses nearest rank over
  observed sample values. Neither proves whole-window coverage. Missing/out-of-range
  percentages are unavailable, not zero.
- Driver and worker series are selectable separately. No worker evidence alone does not
  establish that a cluster is single-node; cluster configuration is used.
- Sizing candidates require enough valid CPU **and** memory samples. Validate peaks,
  concurrency, SLA and a reversible benchmark before changing anything.
- `1 MiB = 1,048,576 bytes`. Boundary-interval byte totals are retained without invented
  proportional estimates; rates use the original interval length. Traffic is **not Azure
  billed egress**. CPU wait alone does not establish network causality.
- Query durations/queue values are seconds converted from millisecond evidence. Queries
  without valid start times cannot be assigned to the window and are excluded with a limitation.
- Job failure routing considers failure notifications, not success-only notifications.
  Legacy snapshots whose entire email-notification object was hashed show **Unknown**,
  not "unconfigured." New collection preserves routing shape while hashing recipients.
  Task pagination and inherited routing still require human verification.
- Unknown posture evidence is not a failure or a passing control. Review applicability
  and exceptions through the shared finding register. There is no synthetic compliance score.

## Evidence quality and old snapshots

**Workspace capability coverage** shows saved module coverage for each workspace.
Inspect underlying source failures and limitations before interpreting findings.
Inventory rows can exist without metric samples; counts do not prove telemetry coverage.

Old snapshots remain readable. A new view can say **Not collected in this version**.
Under **Evidence quality**, expand the rule/re-analysis panel, review options, then select
**Create child analysis**. This copies saved raw evidence into a new local run and analyzes
it without cloud access. The parent and its decisions are not overwritten or silently
transferred. The child records its parent ID and requires its own review.

Re-analysis cannot recover missing telemetry, optional assets never collected, or
notification details already removed by legacy redaction. Run a new, explicitly started
native assessment when new evidence is needed. Linked raw paths are refused.
Local import/re-analysis display a busy state; they are not cancellable streaming jobs.

## Import raw evidence without an Azure login

1. Open `?import=1` or select **Import evidence**.
2. Enter one workspace ID and the declared start/end window in UTC.
3. Select JSON/CSV files, then inspect each dataset mapping.
4. Select **Validate import**. Review counts, content hashes, declared coverage and redaction.
5. Confirm the scope/limitations/redaction checkbox and select **Analyze imported evidence**.

Supported input is a JSON array of objects, an object containing an `items`, `rows` or
`data` array, or a CSV with header names matching the raw schema. Nested CSV objects/arrays
must be JSON strings. Use one file per dataset, at most 30 files, 100,000 rows per file,
and 8 MiB combined in the browser. Existing `.ndjson` files are not accepted directly;
use local re-analysis for toolkit snapshots, or convert a bounded record set to a JSON array.

| Dataset mapping | Minimum shape / useful fields |
| --- | --- |
| `clusters` | `cluster_id`; also `cluster_name`, `num_workers`, `autoscale`, `node_type_id` |
| `node-timeline` | `cluster_id`, `start_time`, `end_time`; CPU user/system %, memory %, wait %, instance ID, driver flag, network bytes |
| `jobs` | `job_id`; settings, tasks and email/webhook notifications |
| `job-runs` | `job_id`, `start_time`; run ID and state/result |
| `query-history` | `start_time`; statement ID, warehouse ID or compute object, duration/queue milliseconds, execution status |
| `sql-warehouses` | Warehouse ID/name and configuration |
| `workspace-settings` | `enableIpAccessLists` |
| `metastore-assignment` | `metastore_id` |
| `commitment-demand` | All fields in the example below |
| Asset mappings | One of the seven asset names from CAP-07; ID/name/path and metadata |

Every supplied workspace ID must match the declared workspace. Import workspaces separately.
Aggregate-only scanner summaries are not accepted as raw node timelines. Identities/paths
are protected, query text and known secret/parameter fields omitted; this is not a general
content-classification guarantee, so review input and outputs before sharing them.

Imported results are marked **imported**, with uncertain extraction completeness. Azure
authoritative cost is **unavailable**, not zero; cost views are gated accordingly.
No credentials, Azure discovery, warehouse queries or scanner-wheel installation are required.

## Commitment scenario inputs

Native collection does not infer eligible hourly concurrent demand from sequential machine
lifetimes or manufacture financial eligibility. Supply reviewed hourly evidence, for example:

```json
[
  {
    "hour": "2026-09-01T00:00:00Z",
    "region": "eastus",
    "sku": "EXAMPLE-ELIGIBLE-SKU",
    "currency": "USD",
    "eligibleNodes": 10,
    "coveredNodes": 4,
    "onDemandHourlyRate": 1.0,
    "commitmentHourlyRate": 0.6
  }
]
```

These are illustrative rates, **not Azure prices**. Use one SKU/region/currency, unique
hours, nonnegative values, and existing coverage no greater than eligible demand.
The proposed quantity is a positive integer. The calculation subtracts existing coverage,
charges the proposed commitment even when idle, and covers sampled hours only.
Workspace/subscription/resource-group filters apply; text search and page selection do not.
The result is saved as a scenario artifact. No contract-term extrapolation or purchase occurs.

## Review, workbooks and publication

Review and Export share one final step. **Download report** and **Preview report**
are at the top; the review form is collapsed by default. It edits one selected
finding at a time, using only decision, reviewer and optional note. A newly edited
non-pending decision needs a reviewer before saving. Existing role, risk, experiment
and other historical fields are retained even though the compact form does not edit them.

**Preview report** moves directly to the preview and places keyboard focus there.
Markdown reports render as formatted HTML with headings, tables, lists and code blocks,
using the current light or dark theme. Contents links jump to report sections, including
older reports with shortened section labels. Supporting evidence links open the matching
saved artifact locally; CSV and JSON remain plain-text previews. Loading and read failures
appear in the preview itself. Remote images and embedded HTML are not loaded or executed.
**Download report** still downloads the original Markdown artifact unchanged.

The step completes after a download, independently of optional review progress.
Pending findings remain unapproved. Downloads use saved decisions only; unsaved edits
are marked, save errors keep the draft, and workbook/publication actions that reload
results are disabled until edits are saved or explicitly discarded.

New findings have per-resource instance IDs so two findings from the same rule do not
overwrite each other's decisions. Reports, backlog/sign-off exports and workbook findings
preserve those IDs; legacy detector-ID behavior remains compatible.

The workbook includes Summary, Rules, Quality, saved Review and Findings plus selected
module sheets. It exports the **full run**, not current UI filters. Save review changes first.
Detailed arrays remain in canonical JSON. The revision-based filename changes with exported
evidence/review contents. XLSX cells use inert strings for untrusted formula-like text.
Large individual cells fail explicitly rather than being silently truncated.

Dashboard publication is deliberately narrower than an inventory/analysis dashboard:
it publishes a new Lakeview dashboard of **capability coverage counts**. It uploads no
raw evidence, creates/drops no tables, overwrites no existing dashboard, embeds no credentials,
and applies no grants.

To use it, enter the exact destination workspace URL and warehouse ID, preview the plan,
approve that destination and compute charges, then confirm the write. Viewers use their
own credentials. A local audit is written before the first cloud request.
If an outcome is failed or uncertain, inspect the audit and remote workspace; automatic
retries of that plan are blocked to avoid duplicate writes.
**Live publication/schema rendering has not been verified in an authorized destination.**

## Remaining boundaries

The [UI modification plan](../docs/ScannerAnalyzer-UI-Modification-Plan.md) remains a broader
target than this initial release: full posture categories, rich published analytics dashboards,
automatic financially authoritative commitment inputs, a pre-run workspace/module readiness
matrix, dedicated module-progress/cancellation, and complete filter/subview URL history are
not delivered here. Post-collection workspace coverage and existing collector progress are
available. The original deterministic `?mock=1` demo does not emulate the new operations;
use the synthetic production-stack acceptance harness described in the test plan.

CAP-14 detailed Spark stage/task/executor analysis remains excluded and is not supplied by
these changes. Existing permission grants and administrator assignments are not changed.
