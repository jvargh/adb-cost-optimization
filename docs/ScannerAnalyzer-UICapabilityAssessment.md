# UI capability integration assessment

> **Historical design record:** This assessment compared the workbench with a standalone discovery package that has since been removed. Package-specific observations and baseline descriptions below refer to that earlier review, not the current implementation. Links into the removed source have been retired. See the [UI user guide](../ui/USER-GUIDE.md) for supported capabilities.

**Assessment date:** 2026-09-29  
**Status:** Proposed recommendations; awaiting human validation  
**Decision owner / reviewer:** Not assigned  
**Implementation approval:** None implied by this document  
**Scope:** The former standalone discovery package compared with the assessment collectors, analysis pipeline, production UI adapter, and React UI at the time of review.

## 1. Executive recommendation

**Yes, this package contains useful capabilities, but integrate selected analysis concepts rather than installing or embedding its complete discovery workflow.**

The best initial additions are:

1. **Compute utilization and right-sizing evidence:** CPU, memory, CPU wait, network activity, and driver/worker views.
2. **Job health:** Failed jobs without effective failure notifications, retry-policy coverage, and task complexity.
3. **Query analysis:** Slow/failed queries and user/warehouse summaries, without importing the package's cost-allocation formula.

Much of the required evidence is already collected by the current toolkit. The largest immediate gap is converting that evidence into trustworthy metrics, findings, and UI drilldowns, not adding another scanner.

Security posture, broader workspace-object inventory, and Excel export are useful second-phase candidates. Reserved Instance purchase quantities should remain a research item until supported by temporal demand and commitment evidence.

**This package does not solve the current detailed Spark-metrics warning.** The reviewed code uses node timelines, query history, and job metadata, not Spark event-log stage/task/executor metrics. Adding its features must not mark that evidence gap as resolved.

## 2. Review basis and boundaries

Reviewed:

- The former package's setup guides, configuration, and Python source, rather than generated build copies.
- Rules, security-check metadata, discovery/analysis notebooks, and the bundled Lakeview dashboard.
- The workbench's [collector inventory](../assessment/docs/collectors-and-outputs.md), relevant collector SQL, [detectors](../assessment/detectors/catalog.py), [production results adapter](../ui/server/assessment_server.py), and UI result/export components.

Method and limitations:

- This was a source-level capability and integration assessment, not a live scan or a full security audit.
- No scanner was executed against Azure or Databricks. No resources, roles, warehouse selections, or UI behavior were changed for this assessment.
- The local wheel is version **2.0.2**; the package README still identifies **2.0.0**. Python source files present in the wheel matched the local source after newline normalization.
- The former package's README identified an upstream Trinity Framework location. This review assessed the supplied local copy, not the current upstream repository or its complete history.
- Static inspection found 35 security metadata entries but only 21 distinct check IDs directly emitted by the analyzer. Metadata entries alone are not evidence of implemented checks.
- No automated test suite or license file was found in the supplied folder/wheel. The package declares an MIT classifier, but reuse rights and required attribution still need confirmation from the source owners.
- The effort labels below are relative implementation estimates, not delivery commitments.

## 3. What the current tool already provides

| Area | Verified current coverage | Implication |
| --- | --- | --- |
| Estate discovery | Azure subscription/resource-group/workspace selection; cluster, warehouse, job, pipeline, and Unity Catalog collection. | Do not add a second overlapping discovery workflow by default. |
| Utilization inputs | `system.compute.node_timeline` is collected and normalized. | Start by deriving metrics from existing evidence. |
| SQL inputs | `system.query.history` is collected and normalized. | Query analysis can reuse the current approved SQL path. |
| Job inputs and metrics | Jobs/tasks and runs are collected; the UI maps run count, failure rate, and p50/p95 duration. | Duration and failure summaries are overlap; notification/retry analysis is a genuine addition. |
| Cost governance | Azure cost collection, Databricks usage/list prices, reconciliation, attribution, confidence, findings, and human review. | Keep the current cost-authority and evidence-quality model. |
| Operational UX | Scope controls, explicit warehouse approval, readiness, run monitoring, historical snapshots, permission setup, review, and export. | Preserve these controls rather than routing around them through notebooks. |
| Current visualization | Executive, Cost, Compute, Findings, Quality, and Roadmap tabs. | Extend existing views where practical before adding more top-level tabs. |
| Current output | Markdown, CSV, and JSON artifacts. | A consolidated Excel workbook would be new; current artifact delivery is text-oriented. |

### Important distinction: collected is not the same as displayed

The production adapter currently sets cluster `idlePercent` to `None`. It also sets warehouse `queryCount`, `p95QueueSeconds`, `p95DurationSeconds`, and `spillGb` to `None`. The UI already has placeholders for several of these metrics.

Therefore, screenshots or fixture-backed demonstrations should not be treated as proof that production utilization or warehouse metrics are implemented. Wiring trustworthy production metrics is a higher priority than adding similar-looking charts.

Workbench components reviewed: [production results adapter](../ui/server/assessment_server.py), [Compute tab](../ui/src/features/results/ComputeTab.tsx), [node timeline SQL](../assessment/collectors/sql/DatabricksNodeTimeline.sql), and [query history SQL](../assessment/collectors/sql/DatabricksQueryHistory.sql).

## 4. Capability comparison and recommendations

Priority: **P1** = recommended first increment; **P2** = useful subsequent increment; **P3** = research or optional scope. Effort: **S/M/L** = relative small/medium/large, including integration and validation.

| ID | Capability in the former package | Existing coverage | Proposed UI addition | Recommendation / effort |
| --- | --- | --- | --- | --- |
| CAP-01 | CPU/memory/CPU-wait summaries and utilization categories. | Node evidence exists; production utilization metrics are not fully surfaced. | Compute drilldown with measured averages/peaks, sample coverage, and configurable categories. | **P1 / M: Adopt the capability; correct aggregation and missing-data semantics.** |
| CAP-02 | Worker sizing, single-node identification, autoscaling range analysis, and sizing recommendations. | Current UI shows node type and autoscale bounds; detector catalog has a basic autoscaling candidate. | Explain current configuration versus observed demand and offer benchmark candidates. | **P1 / M-L: Adapt after CAP-01; do not copy fixed downsizing percentages.** |
| CAP-03 | Failed jobs without alerts, retry coverage, task count, ownership, and long-running jobs. | Job/run inventory and failure/duration metrics already exist. Alert/retry findings are absent from the detector catalog. | Job Health section within Compute/Workloads, with evidence links and owner-filtered findings. | **P1 / M: High-value incremental functionality.** |
| CAP-04 | Query-level duration/failure analysis plus user and warehouse summaries. | Query history exists; current production warehouse metrics are placeholders. No dedicated query explorer. | Query drilldown and trustworthy warehouse metrics; user views subject to identity-redaction policy. | **P1 / M-L: Add performance/reliability analysis first; defer monetary allocation.** |
| CAP-05 | Network receive/send and CPU-wait diagnostics. | Input fields can exist in node timelines, but no dedicated network diagnostic view. | Network/CPU-wait panels under Compute, clearly distinguished from Azure network charges. | **P2 / M: Useful; fix units before use.** |
| CAP-06 | Security posture categories, findings, recommendations, and score. | Workspace settings, IP ACLs, governance/audit sources, and policy evidence are collected; no dedicated scored posture experience. | Optional posture section with passed/failed/unknown/not-applicable checks and authoritative source links. | **P2 / L: Start with a verified subset; do not import the current score as a compliance claim.** |
| CAP-07 | Notebooks, repos, MLflow experiments, serving endpoints, SQL alerts, Genie spaces, and UC volumes. | Core estate inventory overlaps; these broader asset types are not currently exposed as an asset inventory. | Optional Workspace Assets view with counts, ownership, and links. | **P2 / M-L: Valuable for broader discovery; keep optional for a cost-focused assessment.** |
| CAP-08 | Consolidated multi-sheet Excel reports. | Existing export is Markdown/CSV/JSON. | Downloadable workbook of approved metrics, findings, evidence quality, and human decisions. | **P2 / M: Useful validator deliverable; requires binary export support.** |
| CAP-09 | Editable analysis-rule JSON and category thresholds. | Existing assessment configuration already supports thresholds, but not this richer classification catalog. | Validated advanced thresholds using the existing configuration model, with versioned rule provenance. | **P2 / M: Extend the current model, not a separate competing rules file.** |
| CAP-10 | Reserved Instance candidate classification and suggested node quantities. | Azure commitments are collected; no equivalent reliable purchase-sizing engine is implemented. | Initially a commitment-readiness investigation, not a purchase recommendation. | **P3 / L: Defer until time-based demand, eligibility, coverage, and prices are available.** |
| CAP-11 | Offline analysis of scanner CSV/JSON exports. | Current offline pipeline supports its own exported run layout, not the scanner's schema. | Optional evidence importer with an explicit scanner format and coverage limitations. | **P2 / M-L: Consider only if users already have scanner exports to reuse.** |
| CAP-12 | Lakeview discovery dashboard backed by workspace inventory tables. | Current UI already presents local persisted assessments without dashboard deployment. | At most an optional external publication/integration path. | **P3 / L: Do not import the deployment workflow into the default assessment.** |
| CAP-13 | Simple/deep scan modes and concurrent scanner tiers. | Existing scope/collector controls and progress reporting overlap; new parallel scheduling would affect orchestration. | Potentially explicit collector profiles after measuring a bottleneck. | **P3 / M-L: Do not label this a new analysis capability or copy concurrency settings blindly.** |
| CAP-14 | Detailed Spark stage/task/executor analysis. | Unsupported in the current tool. | Separate event-log ingestion would be needed. | **Not supplied by this package. No capability credit or warning suppression.** |

## 5. Corrections required before reuse

These are integration blockers or limitations observed in the supplied code, not requests to change live infrastructure.

### B-01. The notebook workflow is not read-only

The setup notebook begins by dropping five inventory tables and subsequently creates a catalog, schema, and tables. The discovery notebook appends scan results to those tables. Its SQL queries can use a warehouse chosen by the scanner rather than the UI's approved selection.

**Required treatment:** Do not execute these notebooks from the normal assessment flow. Reuse local analysis and explicitly approved collectors. If dashboard publication is separately approved, it needs a distinct write-enabled deployment workflow, named destination, ownership, and confirmation.

### B-02. Query "cost" is not an authoritative currency amount

The query SQL calculates `estimated_dbu_cost` from hourly DBUs multiplied by query duration. It does not apply prices or currency. Concurrent queries can over-allocate a warehouse-hour's usage, and a query crossing hours is associated with its ending hour. The result is limited to 100 rows. Missing allocation is also converted to zero.

**Required treatment:** Do not import this field as actual dollars, complete usage, or savings. A future allocation model must reconcile to observed usage/cost, handle concurrency and idle time, preserve unmatched records, and explicitly label estimates. Performance analysis can proceed without assigning cost per query.

### B-03. Network byte conversion is incorrect

The utilization SQL divides bytes by `(1024^2)`. In Databricks SQL, `^` is bitwise XOR, not exponentiation. The divisor is 1,026 rather than 1,048,576, so values labelled MB are incorrect.

**Required treatment:** Use a tested byte-to-MiB conversion and distinguish interval bytes, throughput, and billed egress. Validate units before any threshold or recommendation uses them.

Reference: [Microsoft operator documentation](https://learn.microsoft.com/en-us/azure/databricks/sql/language-manual/functions/caretsign).

### B-04. Missing evidence can become zero, empty inventory, or failure

Cluster preprocessing fills absent numeric telemetry with zero. Several scanners log exceptions and return empty lists or zero counts. Some security checks default absent configuration to a negative value and report failure.

**Required treatment:** Preserve `unknown`, `partial`, `unavailable`, and valid empty results separately. No telemetry must not mean idle compute; a denied API must not mean zero assets or a failed security control. Reuse the assessment's source-status and evidence-quality model.

### B-05. Scope, sampling, and aggregation require redesign

The scanner groups cluster configuration history using `ANY_VALUE`, associates a cluster with an arbitrary job, and later groups utilization by cluster ID alone. Driver and worker aggregates can be averaged without weighting their different populations. Its SQL result handlers inspect the immediate result array rather than implementing the current toolkit's bounded polling/chunking path.

The job scanner requests runs with `limit=5`; that is not proof of a complete selected-window history, and SDK iterator behavior must be checked before describing it as exactly five total runs.

**Required treatment:** Use the existing SQL transport; key every join by account/workspace plus the appropriate object identity; preserve historical configuration and time boundaries; use defined weighting and explicit coverage. Do not infer one-to-one job ownership from arbitrary billing rows.

### B-06. Sizing and reservation recommendations are heuristics

The package contains fixed downsizing/savings ranges. Its RI sizing sums one driver per candidate cluster and configured minimum/midpoint/maximum workers, without establishing concurrent sustained demand or subtracting existing commitment coverage. Those quantities are not sufficient evidence for a purchase.

**Required treatment:** Present experiment candidates, not guaranteed savings or automatic remediation. Require sample coverage, workload SLA, temporal concurrency, SKU/region eligibility, existing reservations/Savings Plans, and current pricing before approving financial recommendations.

### B-07. Security metadata exceeds implemented coverage

There are **35 enabled metadata entries** and **21 distinct statically identifiable emitted check IDs**. The 14 metadata-only IDs include additional download/clipboard controls, ABAC, token policy, and AI monitoring. Do not advertise them as implemented.

The score also deducts for every non-PASS result, including review/unknown-like states. Priority lists select by severity without first excluding passing findings. In the scanner, `cloud_provider` is initialized inside the optional account-ID branch but accessed unconditionally by `scan()`.

**Required treatment:** Validate each Azure control against a supported authoritative source, initialize optional paths safely, and distinguish unassessed coverage from actual failures. Consider shipping findings without an overall score first. Do not claim compliance certification.

### B-08. Job and query analysis need semantic fixes

The job helper treats success/start email notifications as sufficient notification coverage for a failed job. Webhooks, task-level failure notifications, inherited settings, and deliberate no-retry policies need explicit treatment.

The query analyzer generates insights before assigning its newly computed summary to `self.results`, so some insights can use empty or previous-run results.

**Required treatment:** Test each finding against realistic fixtures rather than copying labels. A missing retry policy is a review candidate, not necessarily a defect; a non-idempotent task may intentionally avoid retries.

### B-09. Packaging and rules are not a drop-in contract

The wheel intentionally excludes `analyzer_rules.json`; only security-check metadata is packaged. An explicit external rules path is needed to apply custom cluster thresholds. The consolidated orchestrator passes that path only to the core utilization analyzer, while specialized analyzers retain separate hardcoded logic.

**Required treatment:** Select one canonical rules model and version it with each run. Confirm license/attribution, add regression tests, and avoid bundling generated `build`, cache, and distribution copies into the UI implementation.

### B-10. Expanded collection changes the privacy and cost footprint

The scanner captures query text, executed-by identities, notebook paths, repository details, serving endpoints, and security metadata. Recursive inventory and per-table detail queries can also materially increase scan time and warehouse consumption.

**Required treatment:** Retain opt-in query text/identity handling, hashing and redaction, workspace scope, warehouse consent, bounded pagination, cancellation, and output protections. Never collect secret values as part of an asset inventory.

Workbench reference: [permissions/privacy contract](../assessment/docs/permissions-and-authentication.md).

## 6. Proposed integration shape

Do not add a parallel "run scanner" button with separate authentication, warehouse selection, output folders, and findings.

Prefer:

1. **Collect:** Existing collectors obtain the minimum approved evidence. Add bounded, optional REST collectors only for genuinely new asset types.
2. **Normalize:** Adapt evidence to workspace-scoped, versioned entities with source provenance and collection status.
3. **Analyze:** Implement validated utilization/job/query calculations and conservative detectors in the existing offline pipeline.
4. **Present:** Extend the current Compute/Workloads views and Findings drawer. Add a dedicated Query or Posture view only when its functionality justifies it.
5. **Review:** Use the existing human-validation workflow for recommendations, exceptions, and experiment approval.
6. **Export:** Preserve existing artifacts. Add Excel only with explicit binary transport, MIME handling, path protections, and spreadsheet formula-injection controls.

Relevant extension points:

- [Collector inventory](../assessment/docs/collectors-and-outputs.md) and [Databricks workload collector](../assessment/collectors/DatabricksWorkloads.ps1).
- [Assessment pipeline](../assessment/pipeline/run_assessment.py) and [detector catalog](../assessment/detectors/catalog.py).
- [Production response mapping and export discovery](../ui/server/assessment_server.py).
- [Compute view](../ui/src/features/results/ComputeTab.tsx), [result tabs](../ui/src/features/results/ResultsPage.tsx), [finding details](../ui/src/features/results/FindingDrawer.tsx), and [export view](../ui/src/features/export/ExportPage.tsx).

An optional foreign-evidence importer should identify scanner version, workspace, time window, schema, redaction state, and coverage. Aggregated CSVs lacking those facts must remain limited evidence, not silently become equivalent to a native assessment run.

## 7. Suggested delivery sequence

| Increment | Scope | Prerequisites | Explicit exclusions |
| --- | --- | --- | --- |
| A: Better use of existing evidence | CAP-01, CAP-03, and the performance portion of CAP-04; populate currently unavailable production metrics where evidence supports them. | Approved metric definitions, sample coverage rules, scoped joins, regression fixtures. | New broad scans, monetary query allocation, automatic remediation. |
| B: Explain optimization candidates | CAP-02, CAP-05, and shared threshold work from CAP-09. | Increment A and benchmark/SLA review criteria. | Guaranteed savings and unvalidated fixed resize percentages. |
| C: Optional adjacent capabilities | Selected CAP-06/CAP-07 plus CAP-08; CAP-11 only if an actual import use case exists. | Product owner approves broader scope, permissions, privacy, and maintenance costs. | Compliance certification and automatic account/metastore role changes. |
| Research backlog | CAP-10, CAP-12, CAP-13, and a separate Spark event-log workstream if desired. | A documented user need and architecture/measurement proposal. | Treating these as already provided or production-ready. |

Suggested first acceptance demonstration: use one saved native assessment with valid node/job/query evidence and one partial assessment. Show meaningful additional insight in the first, honest gaps in the second, and **zero new live collection merely from opening results**.

## 8. Human acceptance criteria

Before approving implementation:

- [ ] Business owner selects the capability IDs and confirms whether the product remains cost-focused or expands into general discovery/security posture.
- [ ] Source owner confirms reuse rights, attribution, and the canonical source/version.
- [ ] Data owner approves any newly collected identity, query text, repository, notebook, or security metadata.
- [ ] Technical reviewer agrees which existing artifacts are sufficient and which new collectors are actually required.
- [ ] Metric definitions specify units, sample weighting, time windows, scope keys, minimum coverage, and treatment of missing evidence.
- [ ] Recommendations distinguish observations, heuristics, experiments, estimated savings, and realized savings.
- [ ] Query financial allocation, if selected later, reconciles to authoritative usage/cost and cannot over-allocate overlapping workloads.
- [ ] Security checks, if selected, use supported Azure evidence and separate failure from unknown/not-applicable.
- [ ] New algorithms are tested with missing telemetry, zero-row success, permission failures, partial pages, heterogeneous schemas, colliding object IDs, and changed cluster configurations.
- [ ] UI and exports preserve source links, confidence, limitations, redaction, and human review decisions.
- [ ] Warehouse approval, scope controls, cancellation, snapshot isolation, and independent permission setup are unchanged.
- [ ] No notebook setup, DDL, grant, role change, or resource remediation runs as a side effect of discovery or viewing results.
- [ ] Operational owner approves additional runtime dependencies, support ownership, and performance/scan-cost budgets.
- [ ] Detailed Spark evidence remains explicitly unsupported until a separate validated source is implemented.

## 9. Human decision register

Use **Approve**, **Approve with conditions**, **Defer**, or **Reject**. Recommendations above are not approvals.

| Capability | Human decision | Conditions / scope | Accountable owner |
| --- | --- | --- | --- |
| CAP-01 Compute utilization | Pending | | |
| CAP-02 Sizing/autoscaling evidence | Pending | | |
| CAP-03 Job health | Pending | | |
| CAP-04 Query analysis | Pending | | |
| CAP-05 Network diagnostics | Pending | | |
| CAP-06 Security posture | Pending | | |
| CAP-07 Workspace assets / UC volumes | Pending | | |
| CAP-08 Excel workbook | Pending | | |
| CAP-09 Shared rule configuration | Pending | | |
| CAP-10 Commitment research | Pending | | |
| CAP-11 Scanner-evidence importer | Pending | | |
| CAP-12 External dashboard publication | Pending | | |
| CAP-13 Scan profiles / scheduling | Pending | | |
| CAP-14 Separate Spark event-log capability | Pending; not supplied | | |

**Reviewer:**  
**Review date:**  
**Approved initial increment:**  
**Required exclusions:**  
**Evidence/conditions to resolve before implementation:**  
**Final decision and rationale:**

## 10. Bottom line

The package is a useful source of **analysis ideas and some reusable logic**, not a replacement for the current assessment engine. Prioritize trustworthy utilization, job-health, and query-performance insights using evidence already collected. Require corrections and human approval before introducing financial recommendations, security scoring, broader collection, or write-enabled dashboard workflows.
