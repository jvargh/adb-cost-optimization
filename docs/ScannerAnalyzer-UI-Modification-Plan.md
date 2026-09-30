# UI modification plan: CAP-01 through CAP-13

> **Historical design record:** This plan retains the original capability targets and pre-implementation baseline. The standalone discovery package used during planning is no longer included or required. See the [UI user guide](../ui/USER-GUIDE.md) for current behavior and remaining boundaries.

**Date:** 2026-09-29  
**Status:** Proposed UI/interaction specification; awaiting design validation  
**Planning assumption:** All capabilities CAP-01 through CAP-13 will be delivered. Sequencing is not a recommendation to drop any of them.  
**Companion:** [Capability assessment and source-level limitations](ScannerAnalyzer-UICapabilityAssessment.md)  
**Implementation status:** No application code changes are made by this document.

## 1. Design decision

Keep the existing six-step workflow:

**Configure -> Validate -> Run analysis -> Visualize results -> Review -> Export**

Do not add thirteen workflow steps, thirteen top-level tabs, or a second independent scanner UI. Integrate the capabilities into that workflow:

- Expand **Configure** with evidence source, analysis modules, collection profiles, and versioned rules.
- Make **Validate** show readiness by workspace and capability, with one next-step footer below all checks and permission controls.
- Extend **Run analysis** with module-level progress, bounded collection details, and honest partial outcomes.
- Expand **Visualize results** using grouped navigation, Compute subviews, and new Queries, Posture, and Assets destinations.
- Extend the existing **Review** register to cover individual resource findings across the new domains.
- Extend **Export** with binary workbooks and a separate, explicitly write-enabled dashboard publication operation.

The intended result is one assessment, one scope, one evidence model, one review process, and multiple views of the same saved evidence.

**Delivery is not UI-only.** Existing collectors already supply some inputs, but production analyzers, normalized contracts, persistence, and adapters must supply the new metrics. React must not infer missing telemetry, calculate savings, or perform direct cloud discovery.

## 2. Verified current baseline

The plan was prepared by reading the current production UI, its types/stores/backend interface, and the companion assessment. It is not based only on scanner screenshots or a mock.

| Current implementation | Required consequence |
| --- | --- |
| [App](ui/src/app/App.tsx) owns six workflow steps and saved-snapshot mode. | Preserve the shell and snapshot isolation; add features within the appropriate steps. |
| [ResultsPage](ui/src/features/results/ResultsPage.tsx) has Executive, Cost, Compute, Findings, Quality, and Roadmap tabs. | Preserve all six destinations while adding three result destinations and subviews. |
| [ComputeTab](ui/src/features/results/ComputeTab.tsx) contains cluster, warehouse, and workload tables. | Split this increasingly large screen into focused subviews rather than adding more stacked panels. |
| [Production result mapping](ui/server/assessment_server.py) leaves cluster idle and several warehouse query metrics unavailable. | Implement backend-derived metrics before enabling data-filled production cards. |
| [ConfigurePage](ui/src/features/configure/ConfigurePage.tsx) already handles scope, warehouses, dates, deep-dive targets, and privacy. | Extend it; do not introduce competing scope or warehouse selectors. |
| [App](ui/src/app/App.tsx) renders validation before a separate permission panel; [ValidationActions](ui/src/features/validate/ValidationActions.tsx) is reused in multiple locations. | Consolidate the page-level action area below both sections. This previously discussed layout change is not yet implemented. |
| [Results filters and review completion](ui/src/state/resultsStore.ts) use workspace names and detector IDs in important places. | Introduce stable resource/finding identities before adding multi-resource findings and cross-view navigation. |
| [DataTable](ui/src/components/DataTable.tsx) sorts the supplied rows in memory and has no paging contract. | Extend it for controlled server-side paging/sorting of saved query/asset data, retaining existing behavior for small tables. |
| [Backend interface](ui/src/api/backend.ts) loads a full results object and returns artifact content as text. | Add bounded detail-data operations and real binary downloads, behind the same interface. |
| [Finding categories](ui/src/types/findings.ts) are cost-oriented. | Add a separate domain classification for operational/posture findings rather than falsely classifying every new finding as cost optimization. |

This is a local source review. No browser acceptance run, scanner execution, live permission change, dependency installation, or performance benchmark was performed for this design document.

## 3. Information architecture and navigation

### 3.1 Keep workflow navigation; group navigation inside Results

Replace the flat results-tab strip with a compact grouped results navigator. On wide screens this is a local navigation rail inside the Results content area, not a second application workflow. On narrow screens use a labelled grouped selector above the content.

```text
Application header: Saved snapshots | New assessment | Theme
Workflow: Configure | Validate | Run analysis | Visualize results | Review | Export

Results header: Snapshot, source, collected time, analysis window, evidence coverage
Global estate filters: Subscription | Resource group | Workspace

OVERVIEW                 TECHNICAL                   DECISIONS
  Executive                Compute                    Findings
  Cost                     Queries [new]              Quality
                           Posture [new]              Roadmap
                           Assets [new]
```

Subview structure:

```text
Cost
  Existing cost analysis | Commitment opportunities [CAP-10]

Compute
  Clusters | Warehouses | Job health [CAP-03]
  Cluster details: Utilization [CAP-01] | Sizing [CAP-02] | Network [CAP-05]

Queries [CAP-04]
  Queries | Warehouses | Users

Posture [CAP-06]
  Controls | Findings

Assets [CAP-07]
  Summary | Inventory

Export
  Existing artifacts | Excel workbook [CAP-08] | Dashboard publication [CAP-12]
```

Preserve the recognizable labels of existing destinations. Display unavailable modules with explanatory states rather than making navigation items silently disappear. A backend feature not yet shipped is labelled **Not available in this version**, not **No issues found**.

### 3.2 Deep links, scope, and drilldowns

- Persist the selected results destination/subview in the URL alongside the existing run ID. Proposed parameters are `view` and `section`; they do not initiate collection.
- Deep-linkable entity/finding identifiers must be opaque keys, not query text, identities, repository URLs, or customer paths.
- Use workspace IDs plus account/tenant context and resource IDs for keys. Display workspace names with subscription or ID suffixes where names collide.
- Apply global estate filters consistently to every compatible view. Keep query-user/status filters local to Queries and control-status filters local to Posture.
- Do not silently ignore a filter. If a record cannot be attributed to a selected scope, show it as unattributed/excluded with counts and an explanation.
- Label estate-wide totals separately from filtered totals. Preserve reconciliation equations rather than presenting a filtered subset as the authoritative whole.
- A chart click opens a filtered list; a row opens a detail drawer; a finding link opens the existing finding experience.
- Back/close restores filters, page, and keyboard focus. Changing snapshots cancels/invalidates old detail requests and clears stale drawers.
- Reuse one active detail surface at a time; avoid nested drawers. At narrow widths use a full-width detail surface with a visible Back control.

### 3.3 Overall Results wireframe

```text
+--------------------------------------------------------------------------+
| Saved snapshot | Native / Imported | Window | Rule version | Read-only    |
| Subscription [All]  Resource group [All]  Workspace [All]  Clear filters    |
+--------------------+-----------------------------------------------------+
| OVERVIEW           | Compute > Clusters                                  |
| Executive          | Coverage: measured 18 of 24 clusters | View gaps     |
| Cost               |                                                     |
| TECHNICAL          | CPU summary | Memory summary | Sizing candidates    |
| Compute            |                                                     |
| Queries            | Search | Utilization category | Coverage            |
| Posture            | Cluster | Workspace | CPU | Memory | Coverage       |
| Assets             | ...                                                 |
| DECISIONS          | Selected cluster -> detail / evidence / findings    |
| Findings           |                                                     |
| Quality            | Data source, units, sample window, limitations      |
| Roadmap            |                                                     |
+--------------------+-----------------------------------------------------+
| Continue to review                                                       |
+--------------------------------------------------------------------------+
```

## 4. Changes across the six workflow steps

### 4.1 Configure: evidence source, modules, profiles, and rules

Add an **Assessment input** choice at the beginning:

1. **Collect from selected Azure/Databricks scope**: existing workflow.
2. **Import scanner evidence**: CAP-11 local-file workflow, requiring no Azure sign-in or estate discovery.

Choose the input mode before live configuration bootstrap. Switching modes with unsaved input requires confirmation and must not alter any saved run.

For native input, preserve current scope/warehouse/date/privacy controls and add:

| New section | Controls and behavior |
| --- | --- |
| Analysis modules | Utilization/sizing, job health, query analytics, network, posture, assets, and commitment analysis. Show source dependencies and covered workspaces. Baseline cost analysis remains visible. |
| Collection profile | Standard, Extended, or Custom. Standard uses existing core evidence; Extended adds explicitly listed optional collectors. Profiles are presets, not implicit permission or warehouse approvals. |
| Asset selection | Per-type opt-ins for repos, notebook metadata, experiments, serving endpoints, SQL alerts, Genie spaces, and UC volumes. No notebook source or secret-value collection. |
| Posture selection | Supported control groups and whether account-level evidence is included. Explain missing account access without requesting elevation automatically. |
| Advanced collection | Bounds for pages, timeouts, and workspace/source concurrency, constrained by backend-supported limits. Do not expose arbitrary thread counts without validation. |
| Analysis rules | Named rule set/version, structured threshold editor, defaults, validation messages, and effective-value preview. See CAP-09. |
| Collection impact | Planned source list, privacy fields, potential warehouse use, and coverage limitations. No fabricated duration or monetary estimate. |

Module selection automatically includes required read sources but shows that dependency before validation. Deselecting a shared source identifies all affected modules; never silently remove an input needed by an enabled capability.

Changing scope, warehouses, source selection, privacy, rules, or approved compute use invalidates the relevant validation/run-plan fingerprint. If a read-only rule change needs no new permissions, the backend can reuse unchanged readiness evidence explicitly; the UI must not assume approval remains valid.

### 4.2 Validate: capability readiness and a single bottom action area

Add a **Capability readiness** matrix:

| Workspace | Capability | Required sources | Read access | Coverage expectation | Impact / action |
| --- | --- | --- | --- | --- | --- |
| Example workspace | Utilization | Node timeline, cluster config | Readable | May be empty for window | Ready to collect; not proof of useful telemetry |
| Example workspace | Query analytics | Query history | Denied | Unknown | Show exact access guidance or explicitly disable module |
| Example workspace | Posture | Selected APIs/settings | Partial | Some controls unassessed | Continue with limitations if policy permits |

Separate **can execute the plan** from **has enough evidence to make a recommendation**. An empty timeline or an unsupported security setting must not become a green analytical result.

Layout order:

```text
Selected plan and approvals
Validation progress / completed checks
Capability readiness by workspace
Permission checks and manual repair guidance
Blocking issues / warnings summary
---------------------------------------------------------
Back to Configure | Run / Re-run validation | Continue to run
```

- One authoritative page-level footer sits after both validation and permission content. Remove duplicate page-level continuation controls; keep contextual permission actions.
- `Continue to run` navigates only. `Start read-only assessment` remains a separate action in step 3.
- Green access checks alone do not unlock step 3. Full validation, matching plan, and no conflicting active operation are required.
- Repeat validation keeps the existing confirmation and results until the user confirms.
- A module-specific failure is either a blocker or an explicitly acknowledged partial-coverage condition according to backend policy. Never silently deselect the module.
- Existing permission repair stays separate. New posture/asset scopes do not inherit authorization to grant permissions or assign administrators.
- Import mode validates files, schemas, time/scope metadata, and redaction; it must not show misleading warehouse/grant controls.

### 4.3 Run analysis: progress understandable at capability level

Expand the pre-flight summary with input origin, selected modules/profile, effective rules, source count, workspace scope, privacy policy, and approvals.

Add a capability progress summary above the existing source table:

- Queued, collecting, normalizing, analyzing, completed, partial, failed, or canceled as operation states.
- Source rows retain the existing persisted collection-status vocabulary. Do not replace `pending telemetry` or `skipped` with generic failure.
- Expand each module to see its contributing sources, item counts, pages processed, throttling/backoff, last activity, and failures.
- Show determinate progress only when a denominator is known. Otherwise show activity and elapsed time, not invented percentages or ETAs.
- Cancellation stops scheduled work and requests cancellation of owned in-flight operations where supported. Explain that submitted remote SQL may still complete; cancellation does not claim a stopped warehouse.
- No automatic restart after failure/cancellation. A new attempt is an explicit run with provenance; previously saved evidence remains intact.
- Opening another snapshot must not hide the active operation or merge its data into the snapshot.

For imported evidence, show **Validating files -> Normalizing imported evidence -> Analyzing -> Saving snapshot**. No cloud collection stage should appear successful when it was never attempted.

### 4.4 Visualize results: shared context on every new screen

Every capability view shows:

- Saved run, source origin, analysis window, source timestamp, and active filters.
- Coverage denominator or an explicit statement that the denominator is unknown.
- Metric units, rule version, evidence links, and calculation limitations.
- Clear missing/partial/denied/not-selected/not-supported states.
- An action to review a candidate or inspect evidence, not to modify cloud resources.

The Executive view gains a compact **Assessment coverage and new insights** section: utilization coverage, job-health candidates, query failures, posture coverage, assets discovered, and commitment evidence readiness. Do not combine these into a single invented health score or monetary savings total.

Quality gains a capability-to-source dependency view, collector truncation details, imported-evidence limitations, rule versions, and metric availability. Roadmap links to scoped findings and review decisions, not automatic action scripts.

### 4.5 Review: one register for all new findings

- Add domain filters: Cost, Compute, Job operations, Query performance, Network, Posture, Assets, and Commitments.
- Retain existing decisions: Pending, Accepted, Rejected, Deferred. **Accepted means the reviewer accepts the recommendation for further action; it does not authorize execution, purchase, or publication.**
- Introduce stable backend-generated `findingId` per finding instance. Detector ID remains a rule identifier, not a unique resource finding.
- Bind review identity to run, finding, scoped resource, and rule version. Two clusters flagged by the same rule require independent decisions.
- Add domain-specific evidence/context in the detail form: benchmark/SLA for sizing, notification rationale for jobs, exceptions for posture, financial assumptions for commitments.
- Show passing posture checks and inventory records outside the actionable review queue. Missing-evidence findings remain visible and can be deferred; do not create a mandatory review row for every asset or query.
- Review completion must consider all applicable findings, not only the currently filtered page.
- Retain unsaved-edit protection when navigating, changing snapshots, importing files, or starting a new assessment.
- Carry new findings into the consolidated report and roadmap without losing current review fields or evidence links.

### 4.6 Export: artifacts, workbook, and publication are different actions

Keep current Markdown/CSV/JSON exports. Add:

- Workbook configuration, generation status, download, and source/review revision (CAP-08).
- Scanner import provenance and rule manifest in the export inventory.
- A separate **Publish dashboard** area with a write-operation warning, destination plan, permission check, explicit confirmation, progress, and persisted audit (CAP-12).

Downloading a file, accepting findings, and publishing a dashboard are three distinct states. Publication must not count as a download, and review acceptance must not implicitly authorize publication.

## 5. Capability-specific UI specifications

### CAP-01: Compute utilization

**Location:** Results > Compute > Clusters; Utilization section of cluster details.

**UI modifications**

- Add CPU utilization, memory utilization, CPU wait, coverage, and utilization-category columns; use a column chooser rather than showing every metric by default.
- Details show average, defined percentile, peak, measurement window, driver/worker split, active-node samples, and observed duration where supported.
- Add time-series charts with labelled units and gaps. State whether aggregation is sample-, duration-, or node-weighted.
- Show **Unclassified: insufficient telemetry** when minimum evidence requirements are unmet.
- Keep idle percentage separate from CPU average. Explain the exact backend idle rule and denominator.

**Interaction:** Select cluster -> Utilization -> inspect interval/evidence -> related finding or Sizing.

**Dependency:** Backend normalized utilization series and metrics, configuration history, units, and coverage. CPU/memory absence cannot become zero.

**Acceptance:** A cluster with valid zero CPU differs visibly from a cluster without telemetry; driver-only evidence is not labelled single-node; backend aggregate values and coverage are preserved exactly.

### CAP-02: Sizing and autoscaling evidence

**Location:** Cluster details > Sizing; cross-links to Findings and Review.

**UI modifications**

- Side-by-side **Configured capacity** and **Observed demand**: worker configuration, driver/worker types, observed node range, peaks, coverage, and relevant workload constraints.
- Candidate card includes rationale, counter-evidence, confidence, rule version, and **Validate with benchmark** action leading to Review.
- Identify configuration changes during the window rather than presenting an arbitrary historical configuration as current.
- Show candidate ranges only when the backend supplies a defensible result; otherwise offer an investigation, not an invented resize.
- No **Apply resize**, **Terminate**, or automatic percentage-savings control.

**Acceptance:** Sparse evidence suppresses numeric sizing; single-node classification uses configuration; recording a benchmark plan never calls a cluster mutation API.

### CAP-03: Job operational health

**Location:** Results > Compute > Job health.

**UI modifications**

- Preserve run count, failures, p50/p95 duration, owner, and compute type.
- Add effective failure-alert coverage, retry policy, task count, and operational-finding count.
- Detail sections: Overview, Runs, Tasks/dependencies, Notifications/retries, and Evidence. Start with a structured dependency list; an interactive graph is not required.
- Filters: workspace, job, owner when allowed, failures, missing failure alerts, retry-review candidates, and coverage.
- Distinguish failure-email/webhook routing from start/success notifications. Display unknown task configuration as unknown.
- Show intentional no-retry policies as reviewable context; do not universally prescribe retries.

**Acceptance:** Success-only notifications do not satisfy failure-alert coverage; task-level alerts and retry special cases are tested; job history is bounded to the selected window and declares truncation.

### CAP-04: Query explorer and warehouse analytics

**Location:** New Results > Queries; links from Compute > Warehouses.

**UI modifications**

- Summary: collected query count, failed/canceled counts, duration percentiles, queue percentiles, and coverage.
- Paged table: query ID, workspace, warehouse, execution status, start time, duration, queue time, and user/pseudonym when permitted.
- Local filters: warehouse, status, duration/queue thresholds, user, and a date range bounded by saved evidence.
- Details: timing breakdown, supported spill/IO metrics with units, failure information, source references, and query text only if approved and retained.
- Warehouse and User subviews share the same saved dataset and explain denominators.
- Do not offer **Run query**. A Databricks link is a user-initiated navigation to an allowlisted workspace, not execution.
- Do not display scanner `estimated_dbu_cost` as currency. Any later estimated allocation must be labelled separately, reconciled, and accompanied by idle/unallocated amounts.

**Acceptance:** Paging/filtering aggregates the full saved dataset rather than the displayed page; a 100-row capped import is labelled incomplete; omitted query text cannot be revealed by a toggle or export.

### CAP-05: Network and CPU-wait diagnostics

**Location:** Cluster details > Network; summary links from utilization findings.

**UI modifications**

- Receive/send volume and throughput, CPU-wait series, peaks, and coverage, with explicit measurement interval.
- Distinguish MiB from MB and MiB/s from cumulative bytes; use a single validated backend unit contract.
- Label node network activity **not Azure billed egress**. Do not infer cross-region traffic, network charges, or network bottlenecks from this metric alone.
- Related finding describes an investigation with corroborating evidence, not a proven root cause.

**Acceptance:** A 1,048,576-byte sample displays as 1 MiB; throughput also requires a valid elapsed interval; missing intervals create gaps rather than zero throughput.

### CAP-06: Security/governance posture

**Location:** New Results > Posture.

**UI modifications**

- Categories: Network, Identity, Data protection, Governance, and Compliance-related checks.
- Coverage summary shows implemented applicable controls, evaluated controls, failures, unknowns, and not-applicable controls separately.
- Controls table: control ID, resource/workspace, category, severity, outcome, evidence timestamp, and source.
- Detail: applicability, observed configuration, expected condition, supporting evidence, limitations, guidance, and reviewable exception rationale.
- Use outcomes **Pass / Fail / Unknown / Not applicable**. Retain collection failure details separately from control outcome.
- No initial overall grade or compliance-certification badge. Unsupported metadata-only checks are labelled **Not implemented**, not evaluated.
- Failed controls can create scoped findings; unknown results identify evidence gaps. Neither grants nor role elevation are automatic.

**Acceptance:** Inaccessible APIs do not create failed controls; pass results do not enter prioritized remediation; coverage reflects implemented checks rather than claiming all 35 metadata definitions work.

### CAP-07: Workspace assets and UC volumes

**Location:** New Results > Assets.

**UI modifications**

- Summary counts by asset type and workspace, with visible collection coverage.
- Inventory type selector: repositories, notebook metadata, MLflow experiments, model-serving endpoints, SQL alerts, Genie spaces, and UC volumes.
- Common columns: name or protected label, type, workspace, owner if collected, last observed time, available state, and related findings.
- Type-specific detail fields, e.g. serving configuration/state, repository branch metadata, volume catalog/schema. Show only allowed, retained metadata.
- Search and paging operate on saved evidence; access-denied inventories are not displayed as zero assets.
- Ownership or configuration may support a finding. Inventory alone does not prove cost, inactivity, orphan status, or safe deletion.

**Acceptance:** Each supported asset type has a real collector/import adapter and production view; redaction is consistent in search/details/exports; no notebook source or secret values are fetched.

### CAP-08: Excel workbook

**Location:** Export > Excel workbook.

**UI modifications**

- Sheet checklist with available rows/coverage: Summary, Costs, Utilization, Sizing, Jobs, Queries, Network, Posture, Assets, Commitments, Findings, Review, Quality, and Rules/provenance.
- Default workbook scope is the full saved run. An explicit **Use current filters** option shows scope and excluded counts in the workbook manifest.
- Display generation progress, sensitivity, size, generation time, review revision, and download state.
- Preview a sheet manifest and bounded sample, not the XLSX binary as text.
- Regeneration after review changes creates a clearly versioned artifact; an older workbook remains labelled with its earlier review revision.
- Empty/unavailable sheets include an explanation instead of suggesting a clean result. Large datasets are split or capped with explicit disclosure; never silently truncate.

**Dependency:** Real binary artifact contract and server generation, correct MIME type, contained paths, spreadsheet-safe string handling, and approved dependency changes.

**Acceptance:** The generated workbook opens as XLSX, counts match its selected scope, redaction holds, formula-like untrusted text is inert, and existing text downloads still work.

### CAP-09: Rule configuration and reproducibility

**Location:** Configure > Analysis rules; read-only rule/provenance view in Results > Quality.

**UI modifications**

- Structured editors for supported thresholds with units, valid ranges, descriptions, and minimum-coverage requirements.
- Import/export validated rule JSON; reject unknown keys/versions explicitly rather than silently applying defaults.
- Show effective values, changed-from-default indicators, and the analyzers that consume each rule.
- Persist rule version/hash with each result and finding. Do not let specialized analyzers silently use inconsistent hardcoded thresholds.
- Editing a live configuration affects a future run only.
- **Re-analyze saved evidence** opens a separate local-only plan, validates evidence compatibility, and creates a child snapshot with parent linkage; it does not overwrite the original or call cloud collectors.
- Resetting edited rules requires confirmation. Never recalculate saved findings reactively in the browser.

**Acceptance:** Invalid rules prevent analysis with field-level errors; two rule sets produce separately identifiable snapshots; existing saved results retain their original findings and review identities.

### CAP-10: Commitment opportunities

**Location:** Results > Cost > Commitment opportunities.

**UI modifications**

- Separate existing commitment inventory, coverage/benefit utilization, and candidate demand.
- Evidence-readiness checklist: hourly concurrent eligible demand, region/SKU and scope, existing coverage, benefit overlap, prices/currency/date, term, and financial assumptions.
- Demand/coverage chart and candidate table when authoritative inputs exist. If not, present the precise missing inputs and an investigation finding.
- Scenario form uses backend-supported terms and assumptions; **Calculate scenario** reads saved inputs and returns a versioned estimate without making purchases or refreshing cloud prices silently.
- Comparison identifies uncovered baseline, proposed coverage, remaining on-demand usage, assumptions, risk, and estimate currency. Do not equate high CPU with reservation demand.
- Action **Send for financial review** records assumptions and approver context; no purchase button.

**Acceptance:** Valid evidence produces a traceable scenario, not just a disabled card; missing evidence yields a blocked estimate rather than a fabricated quantity. Already-covered demand and incompatible currencies/SKUs cannot be double counted.

This implements CAP-10 as an evidence-based decision-support capability. Copying the scanner's fixed node counts is not an acceptable shortcut, and the UI cannot be marked complete until both supported and blocked scenarios work end to end.

### CAP-11: Import scanner evidence

**Location:** Configure > Assessment input > Import scanner evidence.

**UI modifications**

- File selection with accepted formats, size limits, and explicit schema/version help.
- Import preview: file names, declared/detected producer version, workspace mapping, time window, datasets, row counts, missing fields, sensitivity, and redaction preview.
- Prefer an explicitly supported CSV/JSON file set. Do not accept wheels/notebooks as executable imports. Archive import is not required for the initial implementation.
- Workspace mapping uses IDs. User-entered labels/windows are marked as declarations; they do not prove original collection coverage.
- Show **Supported / Partial / Unsupported** per dataset. Unsupported formats fail with actionable messages; no empty-success import.
- Require confirmation of final scope/redaction, then **Analyze imported evidence**. Persist a new snapshot labelled Imported with file checksums and limitations.
- Never merge imported data into a native run implicitly or demand Azure credentials for a local import.

**Acceptance:** Supported evidence produces real results; files without cost evidence show **Cost unavailable**, not zero; malformed/out-of-scope data is rejected or explicitly excluded; SQL/query text is treated as data, never executed.

### CAP-12: Databricks dashboard publication

**Location:** Export > Dashboard publication; saved publication details accessible from the run.

**UI modifications**

- Explicit boundary banner: **Optional write operation outside the read-only assessment**.
- Choose source snapshot/review revision, publication dataset scope, destination workspace, catalog/schema or supported storage destination, and dashboard name.
- Preview exact resources/data to create and operations to execute. Default to a unique run-scoped destination; no drop/truncate or replacement of existing shared objects.
- Check destination authority without granting it. Explain minimum permissions and any approved warehouse/compute usage.
- Require dedicated destination-bound write approval. Assessment warehouse approval and review acceptance do not authorize publication.
- Publish with operation ID, visible progress, terminal status, created-object identifiers, and a verified returned dashboard link.
- Failed/partial publication lists what was created and what failed. Do not blindly retry non-idempotent writes; cancellation must not claim rollback.
- Provide a template/data export fallback, clearly labelled **Not published**. Downloading a template does not satisfy publication success.
- Published data respects redaction and approved scope; dashboard access is configured/validated separately from access to the local application.

**Acceptance:** In a separately approved test destination, the published dashboard reads the selected run's data and its link works; replay cannot overwrite unrelated tables. Default assessment runs and ordinary exports perform no publication writes.

The supplied six-dataset discovery dashboard is a starting point, not proof of coverage for all new analyzers. Publication must declare which inventory/analysis datasets it contains; unavailable or unsupported panels need explicit status.

### CAP-13: Collection profiles and bounded concurrency

**Location:** Configure > Collection profile / Advanced collection; Validate and Run summaries.

**UI modifications**

- Standard/Extended/Custom presets resolve to an explicit collector plan, not ambiguous "deep scan" labels.
- Display module dependencies, optional per-table/recursive operations, page/timeout bounds, and privacy/cost implications.
- Advanced controls expose only supported concurrency ceilings. Backend caps and throttling rules remain authoritative.
- Run view shows queued/active sources by workspace, retry/backoff, last activity, and terminal state.
- Freeze the effective execution plan when a run starts. No mid-run changes that quietly expand scope.
- Preserve current deep-dive target scoping and explicit warehouse consent.

**Acceptance:** Concurrency never exceeds configured backend bounds; cancellation prevents new dispatch; throttling and partial-source failures are visible. Performance claims require measured comparisons using the same scope/evidence.

This capability is execution scheduling within an explicit run, not unattended recurring assessments. No cron, background timer, or automatic rescan is introduced.

## 6. Shared contracts and backend work required by the UI

All additions must pass through [AssessmentBackend](ui/src/api/backend.ts), with matching implementations in [httpBackend](ui/src/api/httpBackend.ts) and [mockBackend](ui/src/api/mockBackend.ts). Components should not call cloud endpoints directly.

### 6.1 Contract changes

| Contract area | Proposed additions / changes | Why required |
| --- | --- | --- |
| Configuration | Input mode, enabled capabilities, collector plan/profile, per-type optional collection, validated concurrency, rule set/version/hash. | Reproducible execution and explicit consent. |
| Manifest | Evidence origin, parent run if derived, producer/import versions, supported capability states, executed plan/rules, collection/analysis timestamps. | Distinguish native, imported, legacy, and re-analyzed snapshots. |
| Scoped resource reference | Tenant/account context, subscription/RG where known, workspace ID, resource type/ID, display labels. | Avoid joining/filtering by non-unique names or bare IDs. |
| Capability summary | Availability, selected/not selected, contributing sources, coverage, limitations, dataset references. | Consistent navigation/empty states without inferring success. |
| Metric payload | Nullable value, unit, statistic, time window, coverage, source, method/rule version, unavailable reason. | Preserve unknown versus zero and defensible calculations. |
| Detail datasets | Utilization series, sizing candidates, job/task health, query rows/aggregates, network, controls, assets, commitment scenarios. | Backend owns calculation; UI renders bounded data. |
| Findings/review | Stable per-instance finding ID, domain, resource references, rule version, evidence links, applicable review fields. | Prevent one accepted detector from accepting many different resource findings. |
| Paged reads | Run/dataset ID, validated filters/sort, page cursor, rows, total or unknown-total indicator, coverage/truncation metadata. | Avoid loading every query and asset into the initial results payload. |
| Artifacts | Text versus binary payload, format/MIME, sensitivity, byte size, source/review revision, generation state. | Valid XLSX delivery and reproducible exports. |
| New operations | Local import/re-analysis, workbook generation, saved-input commitment scenario, separately authorized publication. | Distinct operation IDs, progress, cancellation semantics, and error handling. |

These are proposed contracts, not claims that the endpoints already exist. Decide precise schema names during implementation and version them in the engine and both UI adapters together.

### 6.2 Snapshot and schema compatibility

- Existing saved runs must still open without cloud access. Missing new fields mean **Not collected in this version**, not zero, failure, or corrupted legacy data.
- Preserve legacy review semantics. Migrate detector-level decisions only when their mapping is unambiguous; do not spread one old acceptance across newly split resource findings.
- Imported runs may have no currency, authoritative cost, or reconciliation. Introduce a versioned unavailable-cost result rather than satisfying current required numeric fields with zero.
- Make new result sections optional/version-aware, with explicit availability metadata. Reject unsupported future schemas with a useful message.
- Never rewrite old snapshots on load. Re-analysis produces a new child snapshot; review/export/publication changes are separate revisioned sidecars or operations.
- Preserve the existing stale-request guards for results/review and extend them to queries, drawers, imports, workbooks, and publication status.
- All summary calculations, counts, and filtering for large datasets must have the same semantics as exported datasets. Sorting only the current page is not global sorting.

### 6.3 Operation and consent matrix

| User action | Reads saved local evidence | Reads cloud | Writes cloud | Confirmation / guard |
| --- | --- | --- | --- | --- |
| Open/filter/drill into saved results | Yes | No | No | None; input/scope validation only. |
| Import evidence / re-analyze | Yes, or selected local files | No | No | Confirm input/rules/new snapshot; preserve original. |
| Generate/download workbook | Yes | No | No | Explicit scope/sensitivity; generation tied to revision. |
| Calculate commitment scenario | Yes | No | No | Saved prices/assumptions shown; unavailable inputs block. |
| Validate native assessment | Plan plus readiness | Yes | No grants/DDL; SQL may use compute | Existing compute approval and active-operation checks. |
| Start native assessment | Plan | Yes | No data/resource mutation; SQL may use compute | Valid current plan and explicit start. |
| Permission repair | Status/audit | Yes | Only separately confirmed repair | Existing exact-target confirmation; never implied by modules. |
| Publish dashboard | Selected snapshot | Yes | Yes | Separate destination, operation plan, write/compute approval, audit. |

Dashboard publication is not allowed to overlap conflicting permission setup or collection on the same execution context. Validation expires or is invalidated when its bound destination/plan changes.

## 7. Shared UX, failure states, and accessibility

### 7.1 Evidence state vocabulary

Keep source collection state, analytical availability, security-control outcome, finding confidence, review decision, and operation lifecycle as separate concepts. They must not share one overloaded status field.

| Situation | Required presentation |
| --- | --- |
| Collected complete dataset with zero matching events | "No matching events in the collected window", with coverage. |
| Source reachable but no evaluable telemetry | "Pending telemetry" / insufficient evidence; no zero-utilization claim. |
| Read denied or collection failed | "Unavailable: access denied/collection failed", source and recovery guidance. |
| Some workspaces/pages missing | Partial banner, covered subset, excluded count if known, limitations on metrics. |
| Module not selected | "Not selected for this run"; configure a new plan, not an inline auto-scan. |
| Old snapshot lacks capability | "Not collected in this version"; original results remain usable. |
| Backend does not implement feature/control | "Not available in this version" / "Not implemented". |
| Filters exclude all rows | "No rows match these filters", with Clear filters; do not change source status. |
| Request failed while loading a detail/page | Visible error and bounded Retry for that read; preserve other results. |

### 7.2 Theme and interaction consistency

- Reuse [design tokens](ui/src/styles/tokens.css), existing typography, warm light/dark surfaces, rose primary accent, chart tokens, and spacing. No scanner-specific visual theme.
- Reuse [Panel/Callout primitives](ui/src/components/Panel.tsx), [Drawer](ui/src/components/Drawer.tsx), [DataTable](ui/src/components/DataTable.tsx), [charts](ui/src/components/charts/index.tsx), and [WorkflowNextStep](ui/src/components/WorkflowNextStep.tsx).
- Give new sort headers and drilldown actions keyboard-operable buttons/links; do not rely exclusively on clickable table rows or color.
- Charts have legends, units, accessible summaries, and a tabular alternative. No color-only pass/fail.
- At 1440, 768, and 390 CSS pixels: navigation remains usable; horizontal overflow stays inside wide tables; primary actions remain visible and reachable.
- Dialogs/drawers trap and restore focus appropriately; closing a detail does not reset the selected dataset page.
- Long operations expose last activity, cancellation availability, and error/recovery state. Avoid indefinite spinners after a terminal error.
- Protect New assessment, rule reset, mode switches, and snapshot changes from accidental loss of unsaved work. Saved evidence is never deleted by these actions.

### 7.3 Data scale and privacy

- Use bounded server-side queries over saved datasets for Queries/Assets and large finding lists. Initial Results loading should fetch summaries, not all raw rows.
- Proposed UI page-size default: 50 rows; maximum: 200. Backend enforces bounds independently. These are design targets, not measured current performance.
- Cache only by run/dataset/filter/rule context; never share a query page across snapshots. Obsolete responses cannot replace current results.
- Enforce redaction before persistence/response where applicable, not merely by hiding columns. Search, chart tooltips, URLs, logs, exports, and publication must follow the same policy.
- Imported evidence remains local unless the user explicitly approves publication/export handling. Never execute embedded SQL, scripts, formulas, or notebooks.

## 8. Concrete implementation map

Existing files below are extension points, not instructions to rewrite them wholesale. Proposed new component names are illustrative and do not yet exist.

| Existing surface | Planned modifications |
| --- | --- |
| [App](ui/src/app/App.tsx) | Input-mode bootstrap; validation composition/footer; preserved step/snapshot guards; results deep links. |
| [ConfigurePage](ui/src/features/configure/ConfigurePage.tsx) | Input source, modules, profiles, rules, impact preview. Extract focused controls as size grows. |
| [ValidatePage](ui/src/features/validate/ValidatePage.tsx), [PermissionSetupPanel](ui/src/features/validate/PermissionSetupPanel.tsx), [ValidationActions](ui/src/features/validate/ValidationActions.tsx) | Capability readiness; one final workflow footer; preserve contextual permission actions and existing safeguards. |
| [RunPage](ui/src/features/run/RunPage.tsx), [runStore](ui/src/state/runStore.ts) | Module progress, profile/plan summary, import/re-analysis lifecycle integration, concurrency visibility. |
| [ResultsPage](ui/src/features/results/ResultsPage.tsx), [resultsStore](ui/src/state/resultsStore.ts) | Grouped navigator, ID-based global scope, typed view-local filters, paged detail state, URL selection, request isolation. |
| [ComputeTab](ui/src/features/results/ComputeTab.tsx) | Cluster/Warehouse/Job-health subviews; focused utilization/sizing/network details. |
| [CostTab](ui/src/features/results/CostTab.tsx), [ExecutiveTab](ui/src/features/results/ExecutiveTab.tsx) | Commitment view, no-cost/imported states, coverage-aware overview links. |
| [FindingsTab](ui/src/features/results/FindingsTab.tsx), [FindingDrawer](ui/src/features/results/FindingDrawer.tsx) | Domain and stable finding identity; metric provenance; scoped entity links; domain-specific limitations. |
| [QualityTab](ui/src/features/results/QualityTab.tsx), [RoadmapTab](ui/src/features/results/RoadmapTab.tsx) | Capability/source coverage, import/rules provenance, new scoped review dependencies. |
| [SnapshotPicker](ui/src/features/results/SnapshotPicker.tsx), [SnapshotSummary](ui/src/features/results/SnapshotSummary.tsx), [SnapshotHistory](ui/src/features/results/SnapshotHistory.tsx) | Origin, parent/re-analysis relationship, capability availability; no-cost-compatible summaries. |
| [ReviewPage](ui/src/features/review/ReviewPage.tsx) | Domain filters, unique finding decisions, domain evidence, full-run completion, review revisions. |
| [ExportPage](ui/src/features/export/ExportPage.tsx) | Workbook configuration/binary download and separate publication lifecycle. |
| [Types](ui/src/types), [API seam](ui/src/api/backend.ts), [HTTP adapter](ui/src/api/httpBackend.ts), [mock adapter](ui/src/api/mockBackend.ts) | Versioned contracts and all new operation/data methods. |
| [configStore](ui/src/state/configStore.ts), [validation helpers](ui/src/lib/validation.ts) | Plan fingerprint, approved-target binding, import-mode validation, schema-safe rules. |
| [Shared components](ui/src/components), [styles](ui/src/styles) | Controlled paging, accessible detail actions, grouped navigation using existing visual tokens. |
| [Python host](ui/server/assessment_server.py), [assessment pipeline](assessment/pipeline/run_assessment.py), [detectors](assessment/detectors/catalog.py), [collectors](assessment/collectors) | Production data, persisted datasets, metrics, typed availability, local dataset reads, import/export/scenario/publication operations. |

Likely focused components: `ResultsNavigator`, `CapabilityReadiness`, `AnalysisModulePicker`, `CollectionProfileEditor`, `RuleSetEditor`, `ClusterDetail`, `JobHealthView`, `QueriesView`, `PostureView`, `AssetsView`, `CommitmentView`, `EvidenceImportWizard`, `WorkbookOptions`, and `PublicationWizard`.

Use existing helpers and interfaces first. Add separate stores only for genuinely independent long-lived operations; do not create thirteen stores or copy authentication/transport into feature components.

## 9. Delivery sequence covering all thirteen capabilities

| Stage | Deliverable | Prerequisites / completion evidence |
| --- | --- | --- |
| A: Shared foundations | Stable IDs, versioned availability/data contracts, grouped Results navigation, scoped filters, single validation footer, paged table support. | Existing six-step workflow/snapshots/review/download regressions pass. |
| B: Configuration and execution | CAP-09 rules, CAP-13 profiles/concurrency, module readiness/progress, plan fingerprint. | Effective plan/rules persisted; invalid config blocked; consent and cancellation enforced. |
| C: Existing-evidence insights | CAP-01 utilization, CAP-03 jobs, CAP-04 queries. | Real production evidence appears with truthful coverage; no placeholder-only delivery. |
| D: Compute recommendations | CAP-02 sizing and CAP-05 network. | CAP-01 and corrected backend units/aggregation; candidate review flow verified. |
| E: Broader evidence and import | CAP-06 posture, CAP-07 assets, CAP-11 import. | Correct collectors/importers, privacy controls, no-account offline path, unavailable-cost contracts. These streams can proceed independently once contracts exist. |
| F: Financial decision support | CAP-10 commitments. | Temporal demand, existing coverage, prices, scoped joins, and validated scenario backend; both positive and insufficient-evidence paths verified. |
| G: Handoff and publication | CAP-08 workbook and CAP-12 dashboard publication. | Shared output schema, review revisions, binary support, separately authorized non-destructive publishing. Workbook can ship before publication. |
| H: Integrated acceptance | All selected capabilities work together across native/imported/legacy runs. | Contract/unit/integration/browser tests and source-to-export reconciliation complete. |

Use feature availability flags during staged rollout. A disabled preview is not completion of a capability. Implement all thirteen according to the planning assumption, while keeping optional collection and cloud writes explicitly opt-in.

## 10. Acceptance and validation plan

### 10.1 Capability traceability

| Capability | Required end-to-end demonstration |
| --- | --- |
| CAP-01 | Open native saved metrics, inspect driver/worker coverage and time series, distinguish missing from measured zero. |
| CAP-02 | Inspect observed/configured capacity, send scoped candidate to Review, save benchmark rationale without changing compute. |
| CAP-03 | Detect missing effective failure alerts, inspect tasks/retries and window-bounded runs, save an independent job decision. |
| CAP-04 | Page/filter queries, verify whole-dataset summaries, inspect permitted details, preserve redaction and unit semantics. |
| CAP-05 | Verify exact bytes-to-MiB conversion and interval rates; show gaps and avoid egress-cost claims. |
| CAP-06 | Show pass/fail/unknown/not-applicable and implementation coverage; denied evidence remains unknown. |
| CAP-07 | Browse each selected asset type, inspect metadata, distinguish no assets from inaccessible inventory. |
| CAP-08 | Generate and open a valid workbook with scope, review revision, all selected supported sheets, and safe string cells. |
| CAP-09 | Validate edited/imported rules, save effective version, create a child analysis without altering parent evidence or contacting cloud. |
| CAP-10 | Produce a reconciled saved-input financial scenario and correctly block one with missing demand/pricing/coverage evidence. |
| CAP-11 | Import supported files with no sign-in, preview/reject invalid data, save an explicitly imported partial/no-cost snapshot. |
| CAP-12 | Separately approve publication to a test destination, inspect exact created objects and dashboard, handle partial failure without destructive retries. |
| CAP-13 | Execute bounded profile concurrency, surface retries/partial errors, cancel without scheduling new work or auto-restarting. |

### 10.2 Cross-cutting regression scenarios

- Fully covered native run; native run with empty telemetry; denied source; truncated pages; failed source; canceled run.
- Two workspaces with the same display name and colliding cluster/job/query IDs; filters and reviews stay scoped.
- Two findings from the same detector on different resources; accepting one never accepts the other.
- Imported scanner data with no authoritative cost; unsupported schema; missing window; mismatched scope; protected identifiers.
- Old snapshot predating every new capability; it opens with no cloud requests and retains original results/reviews.
- Slow response from snapshot A arrives after switching to B; no result, export marker, or detail is attached to the wrong run.
- Unsaved review/rules while navigating, importing, resetting, or starting a new assessment; cancellation preserves drafts.
- Permission access green but validation incomplete; continuation remains blocked. Completed validation has its action footer below permission content.
- Continue to run navigates without collecting. Start assessment is separate. Results/filter/export generation do not start warehouses.
- Posture failures never trigger grants; accepted sizing/commitment findings never execute resize/purchase; publication needs separate consent.
- Workbook/publication created before a review update remains labelled with its original revision; no misleading "latest review" claim.
- Light/dark at 1440, 768, and 390 pixels, keyboard-only navigation, focus restoration, accessible sort controls, and visible terminal errors.

Use existing [UI test infrastructure](ui/tests) for contracts, stores, guards, filters, and components; extend backend tests for metrics/import/export/publication. Use isolated Playwright pages for workflow/responsiveness verification, without resetting the user's current live page.

Live dashboard tests require a specifically approved destination and write scope. Unit tests and mock success are not a substitute for publication verification, but no live mutation should be performed simply because this design includes CAP-12.

## 11. Design sign-off and completion definition

The CAP-01 through CAP-13 scope is assumed for this plan. Human validation is still needed for the proposed interaction design, rollout policy, privacy scope, dependencies, and separate write-enabled publication behavior.

- [ ] Accept grouped Results navigation and Compute/Cost subviews.
- [ ] Accept input-mode choice before any Azure bootstrap.
- [ ] Accept module/profile/rule configuration and a single validation action footer.
- [ ] Confirm data-source/metric definitions and existing scanner corrections from the companion assessment.
- [ ] Confirm posture control applicability and asset-type privacy permissions.
- [ ] Confirm commitment financial assumptions and reviewer ownership.
- [ ] Confirm workbook content, export scope, and sensitivity defaults.
- [ ] Confirm publication destination policy, non-destructive resource plan, and separate approval/audit.
- [ ] Confirm legacy snapshot/review migration and no-cost imported-run behavior.
- [ ] Approve test evidence and release gates for all thirteen capabilities.

**Reviewer / owner:**  
**Date:**  
**Design changes requested:**  
**Approved rollout constraints:**  
**Outstanding acceptance evidence:**

**Definition of complete:** Each capability has a usable production-backed interaction, correct missing/partial states, persisted provenance, appropriate review/export behavior, and passing acceptance evidence. Adding a tab, a disabled button, or fixture-only charts is not completion.

**Explicit exclusion:** CAP-14 detailed Spark stage/task/executor analysis is not part of this request and is not supplied by the scanner. Its evidence warning remains until a separately implemented source resolves it.
