# Azure Databricks Cost Optimization: End-to-End Specification and Post-Implementation Plan

**Version:** 1.0  
**Consolidated:** 2026-09-26  
**Evidence cutoff:** Recorded deployment, implementation, and validation through 2026-09-26  
**Purpose:** One start-to-finish specification covering the content framework, L300 workshop, reference environment, assessment toolkit, final outputs, fixes, acceptance evidence, and remaining delivery plan.

## Contents

1. [Authority, status, and conventions](#authority)
2. [Objectives, scope, and safety boundaries](#scope)
3. [Delivery history and final disposition](#history)
4. [Workshop specification](#workshop)
5. [Technical optimization framework and best practices](#optimization)
6. [Reference environment: implemented architecture](#reference-environment)
7. [Reference environment: assets and operations](#reference-operations)
8. [Assessment entry point and scope contract](#assessment-entry)
9. [Collection and aggregation requirements](#collection)
10. [Normalization, correlation, cost, and quality](#model)
11. [Detector and finding contract](#detectors)
12. [Final output specification](#outputs)
13. [Authentication, permissions, and data protection](#security)
14. [Implementation corrections and operational lessons](#corrections)
15. [Validation record and test requirements](#validation)
16. [Acceptance and human handoff](#acceptance)
17. [Post-implementation plan and 30/60/90-day roadmap](#post-implementation)
18. [Requirements and implementation traceability](#traceability)
19. [Source references and technical currency](#references)

<a id="authority"></a>
## 1. Authority, status, and conventions

This is the consolidated specification to use for future implementation planning and handoff. It reconciles, rather than simply concatenates:

- [Original workshop requirements](L300AzureDatabricksCostOptimizationWorkshopRequirements.md).
- [Original assessment toolkit requirements](AzureDatabricksAssessmentToolkitRequirements.md).
- [Cost-optimization content framework](docs/AzureDatabricksCostOptimization.md).
- [Azure deployment plan](.azure/deployment-plan.md).
- [Reference-environment validation](infra/reports/validation-report.md).
- [Assessment implementation, operating documentation, and recorded tests](assessment/test-results.md).

The original requirement documents remain as historical detail and requirement-ID references. This document takes precedence for the **current implementation disposition and post-implementation plan**. Executable code and dated evidence remain authoritative for what actually ran. A requirement, checked planning task, generated report section, or successful API response does not by itself prove complete implementation.

### 1.1 Status vocabulary

| Label | Meaning |
|---|---|
| Implemented | Executable behavior or a deliverable exists; its bounded behavior is described here. |
| Validated | Named automated or live evidence exists. The tested scope and date must be stated. |
| Partial | A useful subset exists, but coverage, automation, telemetry, or acceptance remains incomplete. |
| Blocked | A prerequisite prevented completion; retain the error and do not claim a pass. |
| Deferred | Required or proposed capability is not implemented in the present release. |
| Operational | Requires a customer/facilitator process, approval, or human decision. |
| Historical | Evidence from an earlier run, not a fresh validation of today's environment. |

`SHALL` denotes a requirement, not an assertion that it has been delivered. `SHOULD` is recommended subject to a documented exception. Unknown customer values and unassigned owners remain `TBD`.

### 1.2 Final release position

- **Workshop design:** specified at L300, including nine modules, seven exercises, a two-day agenda, outputs, and follow-up governance.
- **Reference environment:** deployed and validated for serverless jobs and Serverless SQL. Classic configuration exists; live Classic execution remains blocked by East US capacity in the recorded evidence.
- **Assessment toolkit:** working, read-only, **partial implementation** of the broader discovery requirements, with a single-command entry point and one consolidated report.
- **Scope selection:** implemented and tested for interactive and explicit subscription/resource-group selection, qualified group identity, workspace discovery, and saved-scope report regeneration.
- **Customer savings:** no realized savings are established by the lab or by the validation runs.
- **Human acceptance:** not implied by automated test success or the OS successfully opening a report.

This consolidation is documentation work. It does not deploy, rerun billable workloads, change customer resources, or replace the dated test results with new execution claims.

<a id="scope"></a>
## 2. Objectives, scope, and safety boundaries

### 2.1 Business and technical objectives

The solution SHALL help an experienced customer team determine:

1. Where Azure Databricks-related cost is generated.
2. Why material workloads are expensive.
3. Which changes reduce consumption or effective rates without unacceptable performance, reliability, correctness, security, operability, or scalability regression.
4. Which evidence is missing before a recommendation can be accepted.
5. Who owns each action and how results will be measured after implementation.

Expected outcomes include a reconciled baseline, cost-driver map, ownership/attribution assessment, compute and SQL decisions, Spark/code/data evidence packs, governance gaps, commitment readiness, prioritized backlog, and 30/60/90-day roadmap.

### 2.2 Two separate execution boundaries

| Boundary | Purpose | Permitted behavior |
|---|---|---|
| `infra` reference lab | Provision and operate isolated training resources and generate representative evidence | Explicitly authorized Bicep deployment, Databricks object configuration, sample writes, scenario execution, maintenance demonstrations, stopping compute, and guarded teardown. |
| `assessment` customer toolkit | Read approved estate evidence and generate analysis | ARM/Databricks reads, guarded read-only SQL, local evidence and reports. No remediation, workload launch, resource resize, deletion, policy edit, or commitment purchase. |

The lab setup and workload scripts are **not** estate assessment collectors. Running them does not discover all customer workspaces, reconcile the customer's bill, or automatically diagnose every workload.

Read-only SQL is not necessarily free: the SQL Statements API can auto-start a configured Warehouse. The assessment preserves an explicit approval boundary and does not stop that Warehouse afterward. Autostop and operational approval remain the owner's responsibility.

### 2.3 Non-goals

- Introductory Spark, Delta, Unity Catalog, workspace, cluster, or Warehouse training.
- Automatic production remediation, a complete migration, or commitment procurement.
- Guaranteed savings percentages or treating list-price changes as realized savings.
- Full coverage inferred from a successful list call when permissions restrict visibility.
- Treating missing cost, delayed telemetry, empty exports, or unavailable metrics as zero or healthy behavior.
- Copying customer data into the reference lab or exporting sensitive metadata outside customer-approved boundaries.

<a id="history"></a>
## 3. Delivery history and final disposition

| Stage | Requirement or issue | Work incorporated into the final output | Disposition |
|---|---|---|---|
| 1 | Populate the Databricks cost guide with supplied links | Cost structure, usage/system-table references, Spark UI review, code/data techniques, governance, and financial optimization framework | Content retained under `docs`; external features still require currency checks |
| 2 | Match the requested Spark UI section structure | Jobs/Stages analysis; Storage & Jobs; Executor memory, GC, and shuffle guidance | Incorporated into workshop diagnostics; not an automated Spark UI export |
| 3 | Create an advanced, customer-specific workshop | L300 positioning, discovery, nine modules, seven exercises, agenda, backlog, deliverables, and roadmap | Specified |
| 4 | Plan reproducible infrastructure before execution | Bicep/PowerShell architecture, isolated subscription/resource-group boundary, quotas, preview, approval, cost controls | Planned, then separately authorized |
| 5 | Build and test the reference environment | Azure resources, Databricks jobs/policy/Warehouse, seven notebooks, four SQL assets, tests and validation records | Deployed; serverless/SQL validated; Classic execution blocked |
| 6 | Require automated and human validation | Portal/UI checks, evidence fields, shutdown checks, reviewer decisions, and handoff gate | Templates/process delivered; human sign-off remains explicit |
| 7 | Address setup and Classic execution problems | Managed-catalog fallback, effective storage-policy handling, visible polling, optional result-state handling, stockout/startup guards, cancellation, node flexibility | Code/operational mitigations delivered; no capacity guarantee |
| 8 | Identify collection gaps against the workshop and Microsoft guidance | Separate assessment requirements for inventory, cost, telemetry, attribution, detectors, model, reporting, security, and tests | Requirements retained and disposition reconciled here |
| 9 | Implement the assessment | PowerShell collectors, Python model/reconciliation/detectors/reports, tests and evidence | Working partial implementation, not the full requested detector catalog |
| 10 | Reduce commands and reports | `Invoke-Assessment.ps1`; default collect/analyze/open; readiness and offline regeneration; one report plus CSVs | Implemented |
| 11 | Fix failures found after handoff | SQL request-body handling, permanent-error retries, readiness SQL omission, persisted approval, regression and real-command validation | Recorded corrections; continued handoff gate required |
| 12 | Exclude unrelated Azure resources and costs | Collection/model filtering, managed-group expansion, cost-basis isolation, exclusion evidence | Validated at resource-group boundary |
| 13 | Select subscriptions/resource groups | Picker, explicit arrays, qualified IDs, selected workspace discovery, multi-scope cost collection, run snapshot | Implemented; live single-subscription and mocked multi-subscription validation |
| 14 | Consolidate the post-implementation plan | This master specification, current-state disposition, acceptance criteria, and remaining-work register | Documentation consolidation |

The work was organized through dependent planning, infrastructure, workload, assessment, and validation tasks. Parallel implementation was used for bounded independent components. Task completion is not substituted for the live/test evidence in Section 15.

<a id="workshop"></a>
## 4. Workshop specification

### 4.1 Audience, customer profile, and readiness

Participants should already interpret Spark jobs/stages/tasks/executors, query plans, cluster/Warehouse scaling, Delta maintenance, Unity Catalog system tables, billing data, and service objectives.

Required roles are the platform administrator, data engineering lead, Spark performance engineer, SQL/BI owner, data architect, Azure platform owner, FinOps lead, selected workload owners, security/governance reviewer, and executive/product sponsor. One person need not cover all roles.

The discovery record SHALL capture:

- Customer/business unit, regulatory context, executive sponsor, technical owner, and FinOps owner.
- Tenant, subscriptions, resource groups, accounts, workspaces, regions, environments, and residency/network constraints.
- Workspace organization, user population, workload categories, Classic/serverless/SQL footprint, and storage/data formats.
- Monthly spend and currency, financial target, contract/commitment context, budget and forecast.
- Runtime, latency, concurrency, throughput, freshness, availability, RTO/RPO, correctness, and business-window requirements.
- Ownership/tags, policy exceptions, dashboards/alerts, cost review cadence, incidents, growth, and planned architecture changes.
- Approved analysis dates, sensitive fields, storage/retention, access owners, and selected deep dives.

Use a representative **30-90-day** window where available, including peak or month-end behavior. Annotate incidents, migrations, tests, and unusual demand. A shorter or incomplete window requires a confidence limitation.

Select **three to five** deep-dive workloads: top cost, performance-sensitive, SQL/BI if material, ETL/streaming, and an ownership/reliability concern. Select by value, evidence availability, owner participation, and transferability, not spend alone.

Readiness is `Ready`, `Ready with limitations`, or `Not ready`. Missing core cost evidence or an unanalyzable workload cannot be concealed by a polished report.

### 4.2 Nine required modules

Each module SHALL have an objective, topics, discovery questions, evidence, activity, expected findings, and customer deliverable.

#### Module A - Estate discovery, cost model, and prioritization

- **Objective:** locate material spend and establish a reconciled baseline.
- **Topics:** Azure/DBU boundaries; workspace/SKU/product/owner rankings; Pareto concentration; seasonality; failures/retries/idle cost; unit cost; list versus actual/amortized/contract pricing.
- **Discovery:** which billing view is authoritative, what spend is justified, what business volumes explain growth, which commitments apply, and how shared cost is allocated?
- **Evidence:** Azure daily resource/meter costs, billing usage/prices, estate and workload identifiers, budgets, business volumes, and quality/attribution outputs.
- **Activity:** build a cost bridge, reconcile, rank material drivers, annotate anomalies, and confirm deep dives.
- **Expected findings:** concentrated spend, justified growth, unowned/shared charges, retry waste, or a mismatch between list price and financial treatment.
- **Deliverable:** current-state cost baseline and cost-driver map, with exclusions and limitations.

#### Module B - Observability, attribution, and governance

- **Objective:** make cost accountable and actionable after the workshop.
- **Topics:** system tables, account reports, tags/inheritance, serverless usage policies, compute policies, showback/chargeback, dashboards, budgets/alerts, exceptions, and FinOps cadence.
- **Discovery:** what proportion of spend has an owner, where are tags enforced, who acts on alerts, how are shared Warehouses allocated, and when do policy exceptions expire?
- **Evidence:** tag/owner mappings, system-table access/retention, policies/assignments, budgets/recipients, dashboards, and review/action records.
- **Activity:** measure attribution by spend, map preventive/detective controls, design escalation and exception handling.
- **Expected findings:** inconsistent tags, workload-level ownership gaps, dashboards without action, permissive policies, or divergent Finance/engineering numbers.
- **Deliverable:** cost observability and governance control model.

#### Module C - Compute portfolio and right-sizing

- **Objective:** select compute that fits workload behavior and service constraints.
- **Topics:** job versus all-purpose; Classic versus serverless; driver/workers; CPU/memory/I/O; startup/idle time; autoscaling; pools; Photon/runtime; spot and fallback.
- **Discovery:** which workloads are persistent, bursty, CPU/memory/I/O/driver-bound, interruption tolerant, or constrained by libraries, networking, and governance?
- **Evidence:** cluster specs, policies, events, node timeline, active/provisioned time, workload concurrency, evictions, retries, and representative price-performance tests.
- **Activity:** segment workloads, compare demand and worker bounds, identify scheduled work on persistent compute, and design a controlled right-sizing experiment.
- **Expected findings:** excessive minimums/drivers, idle time, unsuitable compute, obsolete runtime, or a conditional serverless/Photon opportunity.
- **Deliverable:** workload-to-compute decision matrix and right-sizing plan with rollback thresholds.

#### Module D - SQL Warehouse and query efficiency

- **Objective:** improve SQL price-performance without harming BI experience.
- **Topics:** Warehouse type/size, cluster range, autostop, cold start, concurrency, queueing, throughput, query frequency, scan/pruning/join/spill/cache, and isolation versus consolidation.
- **Discovery:** are queues caused by capacity, inefficient queries, synchronized dashboard refreshes, or resume latency; what p95/user SLO applies?
- **Evidence:** Warehouse configuration, query history/profiles, concurrency/cluster timelines, bytes/rows, failures, dashboard schedules, and attributable costs.
- **Activity:** separate queue/startup from execution time, inspect at least two representative expensive queries, and compare sizing/rewrite/refresh hypotheses.
- **Expected findings:** over/undersizing, refresh storms, expensive scans, contention, or materialization/serverless opportunities.
- **Deliverable:** SQL Warehouse and query optimization plan.

#### Module E - Spark root-cause diagnosis

- **Objective:** explain expensive execution instead of defaulting to more compute.
- **Topics:** Jobs/Stages/Storage/Executors, critical path, task distribution, scan, shuffle/fetch wait, skew, spill, GC, CPU/memory/I/O, executor loss, driver gaps, partitions, AQE, retries.
- **Discovery:** which run is representative, what dominates the critical path, are outlier tasks or non-Spark work responsible, and does data growth explain the regression?
- **Evidence:** Spark UI/event logs, physical/AQE plans, stage/task/executor metrics, input/file layout, and comparison runs.
- **Activity:** quantify median-versus-tail task behavior and attribute time to execution, I/O, shuffle, spill, GC, or scheduling.
- **Expected findings:** stragglers, low CPU/high I/O, memory pressure, recomputation, executor loss, or driver serialization.
- **Deliverable:** workload-specific Spark evidence pack with hypotheses and measurable experiments.
- **Implementation boundary:** the toolkit currently collects selected-run metadata/events, not complete Spark UI metrics.

#### Module F - Code, joins, and pipeline engineering

- **Objective:** eliminate avoidable scans, serialization, data movement, full reruns, and reprocessing.
- **Topics:** incremental/CDC, checkpoints/watermarks/idempotency, joins and statistics, AQE/CBO, native expressions versus UDFs, parallelism, repeated actions, driver loops/collect, cache cleanup, and task-level recovery.
- **Discovery:** how much input changed, what replay/late/duplicate semantics apply, which joins/UDFs dominate, and which correctness tests protect a rewrite?
- **Evidence:** approved source/plans, execution metrics, cardinality/statistics, change rate, schedules/dependencies, retries, and data-quality tests.
- **Activity:** trace source-to-sink behavior, locate waste, propose safe alternatives, and benchmark correctness plus runtime/resource cost.
- **Expected findings:** full history reprocessed for small changes, expensive joins/UDFs, unnecessary exchanges, or reruns of successful work.
- **Deliverable:** code/pipeline engineering change set with rollout and rollback criteria.

#### Module G - Delta and data layout

- **Objective:** align layout and maintenance with actual read/write patterns.
- **Topics:** Delta format, file distribution, optimized writes/compaction, OPTIMIZE, clustering/ZORDER/partitioning, statistics/skipping/DFP, low-shuffle MERGE, deletion vectors, VACUUM/retention, and lifecycle.
- **Discovery:** which tables dominate scan/rewrite/maintenance, what predicates recur, and what streaming, clone, recovery, or compliance requirements constrain changes?
- **Evidence:** table metadata/history/properties, file sizes, access predicates, scan and write amplification, maintenance history, compatibility, and retention dependencies.
- **Activity:** compare layout to predicates, evaluate maintenance cost versus downstream benefit, and design a safe table benchmark.
- **Expected findings:** small files, inappropriate partitioning, ineffective clustering, merge amplification, or unmeasured/unsafe maintenance.
- **Deliverable:** table-level data optimization plan with compatibility and retention review.

#### Module H - Commitments and rate optimization

- **Objective:** optimize eligible rates only after demand and waste are understood.
- **Topics:** stable versus burst demand, Azure Reservations/Savings Plans, Databricks commitments, coverage/utilization, term/break-even, migration risk, and procurement.
- **Discovery:** which meters are eligible, what demand remains after right-sizing, what commitments exist, and how do region/family/serverless plans affect them?
- **Evidence:** usage and forecast, eligible SKUs, utilization/coverage, approved contract information, roadmap, and Finance assumptions.
- **Activity:** model growth/decline/migration scenarios and define procurement gates.
- **Expected findings:** underused commitments, conditional stable baseline, or an unsuitable infrastructure commitment before serverless migration.
- **Deliverable:** commitment-readiness and rate-optimization assessment; no automated purchase.

#### Module I - Deep dives, prioritization, and operating model

- **Objective:** turn Modules A-H into accountable decisions and repeatable optimization.
- **Topics:** three to five workload packs, confidence, impact/effort/risk, quick wins versus engineering/architecture, benefits, and governance.
- **Discovery:** which actions can be validated now, what evidence/dependencies block others, who approves rollout, and what regression thresholds apply?
- **Evidence:** module outputs, owner/SLA context, release capacity, architecture/security/procurement dependencies, and baseline metrics.
- **Activity:** accept/reject/defer/request evidence, assign owners, score candidates, sequence the roadmap, and agree reassessment.
- **Expected findings:** reversible quick wins, engineering experiments, dependency-heavy architecture changes, and rejected low-confidence opportunities.
- **Deliverable:** approved optimization backlog and 30/60/90-day roadmap.

### 4.3 Seven advanced exercises

| Exercise | Required analysis and acceptance | Result |
|---|---|---|
| 1. Attribution and cost drivers | Reconcile Azure/DBU boundaries; rank material drivers; explain unattributed charges and pricing basis | Baseline and ownership gaps |
| 2. Utilization/right-sizing | Relate worker bounds and resource utilization to service objectives; define an A/B test and rollback | Compute experiment |
| 3. SQL concurrency | Separate queue/startup/execution; inspect expensive queries; compare sizing and query improvements | SQL decision and evidence |
| 4. Spark UI | Identify critical path, skew, shuffle, spill, GC, CPU/memory/I/O, driver gaps, and retries | Root-cause pack |
| 5. Code/incremental design | Evaluate joins/UDFs/reprocessing; prove equivalent outputs and replay correctness | Engineering candidate |
| 6. Delta layout | Assess file/layout/maintenance cost and safe retention; compare supported alternatives | Table benchmark plan |
| 7. Candidate validation | Review evidence, reject false positives, assign owners and thresholds, sequence dependencies | Backlog and roadmap |

Every exercise needs prerequisites, permitted scope, bounded execution, expected evidence, correctness checks, troubleshooting, cost controls, and cleanup. Customer telemetry is preferred; synthetic data is a fallback, not evidence of customer savings.

### 4.4 Delivery format and agenda

Two full days are recommended. A one-day or two-half-day format requires explicitly reduced scope and pre/post-session deep dives; it must not claim equivalent outcomes.

| Day | Time | Session |
|---|---|---|
| 1 | 09:00-09:30 | Sponsor/technical alignment, scope, guardrails, and success measures |
| 1 | 09:30-10:30 | A: cost model, baseline, and drivers |
| 1 | 10:45-12:00 | B: observability, attribution, and governance |
| 1 | 13:00-14:45 | C + Exercise 2: compute portfolio |
| 1 | 15:00-16:30 | D + Exercise 3: SQL Warehouses |
| 1 | 16:30-17:00 | Findings, evidence gaps, and Day 2 preparation |
| 2 | 09:00-09:15 | Recap and evidence questions |
| 2 | 09:15-10:45 | E + Exercise 4: Spark diagnosis |
| 2 | 11:00-12:00 | F + Exercise 5: code and incremental processing |
| 2 | 13:00-14:00 | G + Exercise 6: Delta/data |
| 2 | 14:00-14:30 | H: financial optimization |
| 2 | 14:45-16:15 | I + Exercise 7: prioritization and roadmap |
| 2 | 16:15-17:00 | Executive readout, owners, and decisions |

Breaks/lunch occupy the omitted intervals. Exercise 1 supports pre-work and Module A. Pre-work includes kickoff, permissions/data handling, collection, reconciliation, quality review, workload selection, and facilitator packs. Follow-up includes evidence closure, experiments, benefits reviews, and reruns.

The workshop deck, polished participant/facilitator guides, completed questionnaire, customer-specific executive readout, and approved action plan are **downstream deliverables**, not proven finished merely because their requirements exist.

<a id="optimization"></a>
## 5. Technical optimization framework and best practices

### 5.1 Cost and performance principles

Conceptually, total Databricks-related cost comprises applicable Azure infrastructure/supporting services plus Databricks usage. The billing boundary must be established from evidence:

- Classic can expose DBUs plus customer-paid VMs, disks, networking, storage, and monitoring.
- Serverless bundles its underlying compute infrastructure; do not add a second VM estimate.
- SQL, jobs, all-purpose, Lakeflow/DLT, streaming, training, and serving have different SKU/workload behavior.
- Size, runtime, Photon, tier, concurrency, request rate, model execution time, retries, and storage/egress can influence cost.
- Optimize consumption separately from rate discounts. Faster is not necessarily cheaper; cheaper is not acceptable if correctness or service objectives regress.

The four [Microsoft cost-optimization principles](https://learn.microsoft.com/en-us/azure/databricks/lakehouse-architecture/cost-optimization/best-practices) organize the assessment:

| Principle | Required coverage | Current automation boundary |
|---|---|---|
| Choose optimal resources | Performance-optimized formats; job compute; SQL Warehouses; current runtimes; appropriate GPUs; serverless suitability; instance family/generation/size; Photon; T-shirt sizing standards | Inventory plus a small detector subset; most suitability decisions require benchmarks |
| Dynamically allocate resources | Autoscaling, bounds, auto-termination, streaming scale-down constraints, pools, and policy enforcement | Configuration/events and limited gates; complete utilization/pool-cost analysis deferred |
| Monitor and control cost | Azure Cost Management, system billing, account views, attribution tags, budgets/alerts, serverless policies, OpenSharing egress, audited tag housekeeping, recurring cost reviews | Collection and basic attribution/findings; process and many specialized detectors remain manual/deferred |
| Design cost-effective workloads | Incremental/CDC, triggered versus always-on streaming, AvailableNow, fault-tolerant spot workers with safe driver placement, efficient joins/UDFs/layout, repeated BI patterns | Lab demonstrations and bounded metadata; full workload diagnosis remains evidence/owner dependent |

### 5.2 Technique coverage and safeguards

| Technique/reference | Diagnostic or optimization purpose | Required guardrail |
|---|---|---|
| [Disk caching](https://learn.microsoft.com/en-us/azure/databricks/optimizations/disk-cache) | Repeated file reads and local I/O reuse | Verify engine/runtime support and cache hits; distinguish cold/warm tests and Spark persistence |
| [Dynamic File Pruning](https://learn.microsoft.com/en-us/azure/databricks/optimizations/dynamic-file-pruning) | Reduce unnecessary file reads | Inspect predicates, layout, and physical plan; do not assume every query benefits |
| [Low-shuffle merge](https://learn.microsoft.com/en-us/azure/databricks/optimizations/low-shuffle-merge) | Reduce unaffected-data rewriting/shuffle | Verify runtime/operation support and measure rewrite metrics |
| [AQE](https://learn.microsoft.com/en-us/azure/databricks/optimizations/aqe) | Runtime plan adaptation, skew mitigation, partition coalescing | Inspect actual plans and supported settings before overriding defaults |
| [Deletion vectors](https://learn.microsoft.com/en-us/azure/databricks/delta/deletion-vectors) | Reduce immediate rewrite for row changes | Validate protocol/client/runtime compatibility and later maintenance costs |
| [Materialized views](https://www.databricks.com/blog/introducing-materialized-views-and-streaming-tables-databricks-sql) | Repeated BI/query acceleration | Include refresh cost, freshness, support, and operational ownership |
| [OPTIMIZE](https://learn.microsoft.com/en-us/azure/databricks/sql/language-manual/delta-optimize) | File compaction and layout maintenance | Compare maintenance spend to downstream scan/runtime benefit |
| ZORDER | Co-locate data for selective predicates | Use measured access patterns on compatible tables; not together with Liquid Clustering as one layout strategy |
| [Optimized writes/auto compaction](https://learn.microsoft.com/en-us/azure/databricks/delta/tune-file-size#auto-optimize) | Reduce small files during/after writes | Verify defaults/eligibility and write-latency impact |
| [Liquid Clustering](https://learn.microsoft.com/en-us/azure/databricks/delta/clustering) | Flexible data layout for evolving access | Evaluate compatibility, migration, key choice, and maintenance cost |
| [File-size tuning](https://learn.microsoft.com/en-us/azure/databricks/delta/tune-file-size) | Balance file overhead and parallelism | Measure distributions, not just averages; avoid universal target sizes |
| [Broadcast/shuffle join hints](https://learn.microsoft.com/en-us/azure/databricks/sql/language-manual/sql-ref-syntax-qry-select-hints) | Reduce costly exchanges or sorts | Use actual cardinality/statistics and memory limits; do not force a join universally |
| [CBO](https://learn.microsoft.com/en-us/azure/databricks/optimizations/cbo) | Better join ordering and planning | Validate table/column statistics and resulting physical plan |
| Skew, spill, and data explosion | Identify uneven partitions, oversized tasks, or excessive `explode`/join output | Inspect tails, shuffle, GC, memory, file-read and partition settings |
| Native functions versus UDFs | Reduce serialization/optimizer barriers | Prove equivalent null, type, boundary, and aggregate behavior |
| [Delta MERGE](https://learn.microsoft.com/en-us/azure/databricks/delta/merge) and CDC | Process changed records instead of full history | Deterministic keys, duplicate/late/correction semantics, idempotency, and replay tests |
| [VACUUM](https://learn.microsoft.com/en-us/azure/databricks/sql/language-manual/delta-vacuum) | Remove unreferenced retained files | Retention, time travel, clones, streaming, audit, and recovery review; no assessment-side mutation |
| [Photon](https://learn.microsoft.com/en-us/azure/databricks/compute/photon) and runtime upgrades | Improve eligible price-performance | Benchmark representative inputs and total cost; preserve rollback |
| [AvailableNow](https://learn.microsoft.com/en-us/azure/databricks/structured-streaming/triggers#available-now) | Triggered incremental execution instead of unnecessary 24/7 compute | Freshness SLA, checkpoint/state, arrival pattern, backlog, and late-data evidence |

The source article's tuning switches are discussion inputs, not unconditional settings applied by the toolkit. Exploratory `LIMIT` is not proof of a bounded physical scan. Configuration defaults, preview status, supported APIs, and feature compatibility must be verified for the target runtime/workspace.

<a id="reference-environment"></a>
## 6. Reference environment: implemented architecture

### 6.1 Recorded deployment

| Field | Recorded value |
|---|---|
| Subscription | `463a82d4-1896-4332-aeeb-618ee5a5aa93` |
| Region/profile | East US; isolated, non-production L300 workshop |
| Deployment ID | `adb-cost-l300c01` |
| Resource group | `rg-adb-cost-workshop-l300c01` |
| Workspace | `dbw-adb-cost-l300c01`, Premium |
| Workspace ID/host | `7405608792310779`; `adb-7405608792310779.19.azuredatabricks.net` |
| Managed resource group | `mrg-adb-cost-l300c01` |
| Storage | `stadbcostl300c01` |
| Access Connector | `ac-adb-cost-l300c01` |
| Log Analytics | `log-adb-cost-l300c01` |
| Catalog/schema | `dbw_adb_cost_l300c01.adb_cost_workshop` |
| Classic job | `752079096325650` |
| Serverless job | `614161130219943` |
| SQL Warehouse | `19dfff78c4e639c4` |
| Interactive Classic cluster | `0925-205430-is4saraa` |

These are historical lab identifiers, not defaults to apply to an arbitrary customer estate. Existing workspaces `databricks-serverless-ws` and `dbx-lab-test` were explicitly excluded from deployment changes.

### 6.2 Azure control plane

[main.bicep](infra/main.bicep), [parameters](infra/main.bicepparam), and [modules](infra/modules) implement a subscription-scope entry point with resource-group modules:

- Dedicated tagged resource group and Premium Databricks workspace.
- Secure cluster connectivity/no public IP for Classic nodes.
- ADLS Gen2, hierarchical namespace, TLS 1.2, LRS sample storage; shared-key and anonymous access disabled.
- Access Connector system-assigned identity and storage-scoped `Storage Blob Data Contributor`.
- Dedicated Log Analytics workspace, 30-day retention, and Databricks diagnostic logs.
- Optional budget, disabled unless approved amount/recipients are supplied.

Deployment uses incremental Azure CLI subscription deployment, with validation/what-if before explicit `-Deploy -AcknowledgeCostRisk`. The recorded preview was **11 creates, 0 modifications, 0 deletions**.

Quota evidence distinguished regional/family quota from stock availability: 98 regional vCPUs and 100 DDSv5/DADSv5 family vCPUs were available during preflight, yet Classic VM allocation subsequently failed. Quota is not capacity reservation.

### 6.3 Effective state and exceptions

- Azure Policy made workshop storage `publicNetworkAccess=Disabled`; optional external-location setup was skipped instead of bypassing policy.
- When catalog `main` was unavailable, bootstrap used the workspace-managed Unity Catalog catalog and dedicated workshop schema. This was not a fallback to a legacy/non-UC metastore.
- The reference profile omits customer-managed keys and Private Link. Approved non-production scanner exceptions are recorded in [Checkov configuration](infra/.checkov.yml); they are not production architecture recommendations.
- Policy-created supporting resources, including a storage Event Grid topic, may appear in inventory; they are not necessarily undeclared application changes.
- The checked-in configuration/templates and the bootstrap-generated job payloads are not identical. **The actual bootstrap code and recorded live object state determine the deployed limits**, not the standalone JSON templates.

### 6.4 Implemented compute controls

- Classic interactive auto-termination: 15 minutes; worker range 1-2; Photon and selected LTS runtime; bounded node types.
- Classic job tasks are sequential, zero retry, with 2,400-second task limits in the bootstrap payload.
- Serverless job: maximum one concurrent run, 1,800-second job timeout, 1,200-second task limits, zero retries, sequential comparison/CDC/maintenance tasks.
- Serverless SQL: `2X-Small`, one cluster minimum/maximum, five-minute autostop.
- Workload runner: default 2,400-second overall wait; polling default 15 seconds; separate Classic startup limit default 600 seconds.
- A recent stockout guard examines recent Classic runs within six hours and refuses a new attempt unless `-ForceClassicRetry` is explicit.
- Node flexibility was configured across compatible D4 alternatives, but did not overcome the recorded regional stockout.
- Lab validation/SQL execution include shutdown handling; assessment collection has a different, read-only boundary.

### 6.5 Original reference requirements not fully delivered

The original Section 24 describes a stronger reusable environment contract than this deployment implements:

- A fully dynamic confirmed-default-subscription profile instead of lab-specific expected-subscription defaults.
- Atomic, immutable-ID ownership manifests covering every object; collision rejection by proven ownership; reset generations.
- A dedicated reset command with dependency-aware cancellation, stop, data rebuild, permission reset, and immutable evidence archive.
- Seven-day expiration enforcement and refusal to run expired scenarios; `reviewAfter` metadata is not equivalent.
- Seeded retail customers/products/orders/order-lines/change datasets with byte/time caps and an expected-results ledger.
- Manifest-driven per-object teardown, unknown-resource/lock adjudication, finite deletion polling, and verified destroyed state.
- Separate serverless-notebook validation and full Spark stage/task/executor evidence.

These remain deferred or partial. Existing `deployment-outputs.json` and `databricks-state.json` support the lab, but must not be presented as the complete lifecycle manifest specified in the original requirements.

<a id="reference-operations"></a>
## 7. Reference environment: assets and operations

### 7.1 Implemented sample data and scenarios

The current implementation uses bounded Databricks sample datasets, not the proposed multi-million-row retail generator.

| Asset | Behavior and acceptance |
|---|---|
| [00_setup_data.py](infra/notebooks/00_setup_data.py) | Copies ordered, bounded samples from TPC-H orders/customer, TPC-DS store sales, and NYC taxi trips into workshop Delta tables. Default 250,000 rows per source; accepted range 1-500,000. Validates identifiers and nonzero bounded counts. |
| [01_classic_baseline_optimized.py](infra/notebooks/01_classic_baseline_optimized.py) | Classic baseline/improved query comparison; shuffle setting constrained to 4-128; equivalent result assertion. |
| [02_serverless_baseline_optimized.py](infra/notebooks/02_serverless_baseline_optimized.py) | Serverless comparison with equivalent output assertion. |
| [03_shuffle_skew_spill.py](infra/notebooks/03_shuffle_skew_spill.py) | Controlled skew/shuffle and pre-aggregation experiment; 4-128 partition bound; output equivalence. It does not guarantee that every run produces spill. |
| [04_udf_vs_native.py](infra/notebooks/04_udf_vs_native.py) | UDF/native fare-bucket comparison; matching results required. |
| [05_full_vs_incremental_cdc.py](infra/notebooks/05_full_vs_incremental_cdc.py) | Full refresh versus keyed incremental snapshot; default 5,000 changes, maximum 10,000; bidirectional `exceptAll` equality check. |
| [06_delta_layout_maintenance.py](infra/notebooks/06_delta_layout_maintenance.py) | Layout/maintenance demonstration; row count and digest unchanged; VACUUM is 168-hour **DRY RUN**, not deletion. |
| [SQL setup](infra/sql/00_setup.sql) | Creates bounded lab SQL artifacts in the recorded catalog/schema. |
| [SQL comparison](infra/sql/01_baseline_optimized.sql) | Baseline/improved result differences must be zero. |
| [SQL concurrency](infra/sql/02_bounded_concurrency.sql) | At most four submitted scenario statements in the actual runner. |
| [SQL validation](infra/sql/03_validation.sql) | Data validations must return `PASS`. |

Ordering samples makes the fixture repeatable within source assumptions; it is not proof of the original seed/byte-cap contract or unchanged upstream samples. Synthetic/sample timings demonstrate mechanisms, not customer production savings.

### 7.2 Script responsibilities

| Script | Responsibility |
|---|---|
| [Deploy-WorkshopEnvironment.ps1](infra/scripts/Deploy-WorkshopEnvironment.ps1) | Subscription guard, Bicep validation/what-if, optional authorized deployment, sanitized outputs |
| [Configure-DatabricksWorkspace.ps1](infra/scripts/Configure-DatabricksWorkspace.ps1) | API/catalog/storage checks; notebooks, policy, Classic/serverless jobs, Warehouse and schema; state persistence |
| [Initialize-SampleData.ps1](infra/scripts/Initialize-SampleData.ps1) | Execute bounded setup in the dedicated schema |
| [Invoke-WorkshopWorkloads.ps1](infra/scripts/Invoke-WorkshopWorkloads.ps1) | Classic/Serverless/All selection; run IDs/URLs; state polling; timeouts, stockout guard, cancellation |
| [Invoke-SqlWorkshop.ps1](infra/scripts/Invoke-SqlWorkshop.ps1) | Setup/comparison/concurrency/validation; statement IDs; bounded waits; cleanup |
| [Test-WorkshopEnvironment.ps1](infra/scripts/Test-WorkshopEnvironment.ps1) | Environment checks, telemetry readiness, machine summary, shutdown |
| [Remove-WorkshopEnvironment.ps1](infra/scripts/Remove-WorkshopEnvironment.ps1) | Exact-name/subscription/tag/deployment-ID guarded group deletion with explicit acknowledgment and high-impact confirmation |
| [Workshop.Common.ps1](infra/scripts/Workshop.Common.ps1) | Shared subscription/authentication/API/state/wait helpers |

Bootstrap submits SQL to create the schema and may start the SQL Warehouse; it must not be described as universally zero-compute configuration.

### 7.3 Authorized lab operating sequence

From the repository root, review configuration and permissions first:

```powershell
az account show --output table
az bicep build --file .\infra\main.bicep
Invoke-Pester -Path .\infra\tests
checkov -d .\infra --config-file .\infra\.checkov.yml
.\infra\scripts\Deploy-WorkshopEnvironment.ps1
```

After separately approving billable deployment:

```powershell
.\infra\scripts\Deploy-WorkshopEnvironment.ps1 -Deploy -AcknowledgeCostRisk
.\infra\scripts\Configure-DatabricksWorkspace.ps1
.\infra\scripts\Initialize-SampleData.ps1
.\infra\scripts\Invoke-WorkshopWorkloads.ps1 -Mode Serverless
.\infra\scripts\Invoke-SqlWorkshop.ps1
.\infra\scripts\Test-WorkshopEnvironment.ps1
```

Classic retry is a deliberate, potentially billable action, not a recommended automatic loop:

```powershell
.\infra\scripts\Invoke-WorkshopWorkloads.ps1 `
  -Mode Classic -TimeoutSeconds 7200 -PollSeconds 15 `
  -ClassicStartupTimeoutSeconds 600 -ForceClassicRetry
```

The 7,200-second overall timeout does not override the separate startup deadline. Increasing either deadline does not fix unavailable VM stock.

Teardown requires `-ResourceGroupName`, `-ExpectedDeploymentId`, the expected subscription, required tags, `-AcknowledgePermanentDeletion`, and PowerShell confirmation. The implemented script requests group deletion with `--no-wait`; it does **not** implement the original full object-by-object manifest teardown or verify eventual deletion. The provider manages deletion of its managed group. No teardown was performed for this documentation update.

<a id="assessment-entry"></a>
## 8. Assessment entry point and scope contract

### 8.1 One-command experience

The front door is [Invoke-Assessment.ps1](assessment/Invoke-Assessment.ps1):

```powershell
# From the repository root: select, collect, analyze, and open one report.
.\assessment\Invoke-Assessment.ps1 -SelectScope

# From the assessment directory:
.\Invoke-Assessment.ps1 -SelectScope
```

The picker accepts comma-separated numbers, `*` for all displayed choices, and `q` to cancel. It displays subscription IDs beside group names. Blank/invalid input fails before collection; it does not silently select everything.

Without scope-selection arguments, the existing saved-config workflow remains:

```powershell
.\assessment\Invoke-Assessment.ps1
```

Configuration precedence is explicit `-ConfigPath`, local scope, workshop scope, then example scope. The checked-in defaults are lab-oriented; customer ID, dates, privacy settings, thresholds, and other non-scope settings must be reviewed before customer use.

### 8.2 Actions and switches

| Action | Implemented behavior |
|---|---|
| `Initialize` | Copy example to local config and open it; existing local config is preserved unless `-Force` is supplied |
| `Run` (default) | Safety check, collection, normalization/correlation/reconciliation, findings, one report, default open |
| `Readiness` | Real source checks with analysis skipped; Cost Management uses one one-day aggregate access probe per scope rather than full cost pagination; SQL Warehouse IDs omitted unless the approval switch is explicit. The UI distinguishes successful limited probes and unsupported diagnostics from genuine evidence gaps, grouping shared causes with expandable source responses; original collection statuses are preserved |
| `Reports` | Regenerate from an existing run without collection; use saved run config unless explicitly overridden |
| `Open` | Open the selected/latest consolidated report without collection |
| `Validate` | Read-only scanner, Pester, and Python contract/model/report suites |

| Switch | Contract |
|---|---|
| `-SelectScope` | Interactive subscription/group selection; valid for Run/Readiness |
| `-SubscriptionIds <string[]>` | Explicit subscription GUIDs; not display names |
| `-ResourceGroups <string[]>` | Bare group names when unique, or full subscription-qualified ARM group IDs |
| `-ConfigPath <path>` | Customer base settings; relative paths resolve from invocation directory |
| `-OutputRoot <path>` | New-run output location; for Reports/Open, latest-run search location |
| `-RunRoot <path>` | Select existing report run; relative paths resolve from invocation or assessment directory |
| `-ApproveSqlWarehouseAutoStart` | Explicit one-run Warehouse auto-start acknowledgment |
| `-NoOpenReport` / `-OpenReport` | Suppress/request OS report opening; explicit OpenReport takes precedence |
| `-FailOnCollectorError` | Request stricter orchestration instead of default continuation |
| `-ContinueOnCollectorError` | Preserve progress through source failures; does not make missing evidence valid |

Per-source `partial`/`failed` results still require status review; an exit code alone is not the completeness gate.

### 8.3 Explicit multi-scope invocation

```powershell
.\assessment\Invoke-Assessment.ps1 `
  -SubscriptionIds '<subscription-a>', '<subscription-b>' `
  -ResourceGroups '/subscriptions/<subscription-a>/resourceGroups/rg-data', `
                  '/subscriptions/<subscription-b>/resourceGroups/rg-data' `
  -NoOpenReport
```

Selection semantics:

1. Use enabled subscriptions in the active Azure CLI tenant; cross-tenant runs require separate login/run contexts.
2. Explicit IDs must be accessible; inaccessible/disabled/invalid IDs fail without fallback.
3. Resource groups stay paired with their subscriptions. Ambiguous bare names are rejected.
4. `-ResourceGroups` alone uses base-config subscriptions.
5. With subscriptions but no groups, discover all Databricks workspaces in those subscriptions and derive workspace groups, rather than treating every group as a cost target.
6. Picker groups are explicit selections; selecting a supporting/mixed-use group includes that group boundary.
7. ARM workspace discovery must return usable workspace IDs and hosts; zero selected workspaces fails before collection.
8. `-SelectScope` and explicit scope arrays cannot be combined.
9. Selection inputs are rejected for Reports/Open/Initialize/Validate.
10. A base config may have empty target arrays only when new selection will supply targets; a normal empty-scope run remains invalid.

### 8.4 Scope propagation and reproducibility

- Effective config records `azure.subscriptions`, `azure.resourceGroups`, qualified `azure.resourceGroupIds`, and `azure.costScopes`.
- Qualified group IDs take precedence over legacy group-name matching when provided. Explicitly empty qualified IDs represent no group limit at that input layer, not permission to bypass the derived Databricks boundary.
- Picker-generated cost scopes cover every selected subscription; the previous single `costScope` is removed. Legacy saved configs retain their explicit single scope; without either cost-scope field, all selected subscriptions are queried.
- Discovered workspace entries include subscription, resource group, ARM IDs, Databricks workspace ID, URL, name, and inclusion flag.
- Associated managed groups are included from matched workspace metadata.
- Model filtering protects against same-name cross-subscription collisions, unrelated account workspace records, and stale template-derived managed groups.
- No-scope/no-evidence conditions must not fall back to subscription-wide cost attribution.
- The original config is cloned, not overwritten. Temporary effective configs are cleaned up.
- Each new run persists `assessment-config.json`; the manifest also records qualified group IDs.
- The collector's `-PassThru` result lets the wrapper open the **exact new run**, not a different concurrently created latest directory.
- Reports uses the selected run's snapshot by default. Explicit `-ConfigPath` overrides it; older runs without snapshots use legacy config precedence.

**Attribution limit:** filtering is at resource-group granularity. Resources within a shared or mixed-purpose selected group may still need human allocation. "Zero outside-scope rows" is not proof that every in-group charge exclusively belongs to Databricks.

### 8.5 SQL approval and reselection safety

- A configured Warehouse requires `databricks.allowSqlWarehouseAutoStart=true` or the explicit approval switch for Run.
- Readiness deliberately ignores persisted approval unless `-ApproveSqlWarehouseAutoStart` is present; omitted Warehouse IDs mean unavailable SQL-backed evidence.
- Matching existing workspace settings are preserved by ARM ID or normalized host.
- A prior global Warehouse ID is carried into matching previously configured workspace entries only; it is not copied to newly discovered workspaces.
- CLI reselection does not select a Warehouse automatically. The UI separately defaults an unset choice to the smallest running, otherwise smallest stopped, discovered Warehouse; existing choices and explicit None remain intact.
- Global `deepDiveJobRunIds` and `deepDiveTableNames` are cleared during reselection so old identifiers are not applied to a new target.
- Assessment never runs a production job to manufacture evidence and never stops compute to compensate for an approved read-only SQL auto-start.

### 8.6 Configuration defaults and limitations

The example config contains customer/assessment IDs, Azure scope/cost basis/currency, workspace targets, SQL/identity/deep-dive options, analysis limits, thresholds, redaction, and output settings.

| Setting | Example/default behavior |
|---|---|
| Analysis dates | Explicit stored start/end, not a rolling window; start must precede end |
| `maxPages`, `pageSize` | 100 and 1,000 in the example; endpoint-specific caps may apply |
| `requestTimeoutSeconds` | 120 for Databricks HTTP; no equivalent toolkit-level Azure CLI timeout |
| `collectorTimeoutSeconds` | 1,800 for pending SQL, not a universal collector deadline |
| `retryCount`, `retryBaseSeconds` | 3 and 2; bounded exponential delay capped at 60 seconds |
| Cost basis | ActualCost and AmortizedCost collected separately; reporting basis defaults to ActualCost |
| Material cost / termination | Example 100 currency units and 60 minutes; not a universally justified customer threshold |
| Redaction | Hash identities/notebook paths; omit query text; optional table-name hashing |
| Output root | Example `./assessment/output`; wrapper supports invocation-relative override |

Not every declared threshold or output-format flag is consumed. Exclusion lists, management-group discovery, business-scope filters, retention enforcement, a formal versioned scope schema, and complete source-specific sampling are not fully implemented. Taxonomy/allocation example files are not automatically loaded. Do not infer functionality from a placeholder field.

<a id="collection"></a>
## 9. Collection and aggregation requirements

### 9.1 Architecture and lifecycle

```text
saved base config + optional scope selection
    -> resolved config and read-only safety validation
    -> unique run, manifest, and configuration snapshot
    -> Azure collectors + Databricks collectors
    -> raw evidence and explicit source/collector statuses
    -> Python normalization and Databricks scope filtering
    -> correlation, cost reconciliation, attribution, quality
    -> conservative findings, backlog, benefits baseline
    -> one assessment report + CSV exports
    -> human review, controlled experiments, later reassessment
```

The internal collector is [Collect-CostOptimizationAssessment.ps1](assessment/Collect-CostOptimizationAssessment.ps1). Shared functions are in [Assessment.Common.ps1](assessment/scripts/Assessment.Common.ps1), [Assessment.Scope.ps1](assessment/scripts/Assessment.Scope.ps1), and [Databricks.Common.ps1](assessment/collectors/Databricks.Common.ps1). Analysis is dependency-free Python through [run_assessment.py](assessment/pipeline/run_assessment.py), [core.py](assessment/model/core.py), [catalog.py](assessment/detectors/catalog.py), and [render.py](assessment/reports/render.py).

Run directories use the assessment ID, UTC millisecond timestamp, and random suffix. Azure and Databricks domains run sequentially, preserving individual collector results. Transcript logging and final manifest status accompany each run.

### 9.2 Implemented Azure collection

| Collector | Reads / raw evidence | Present boundary and missing aggregation |
|---|---|---|
| Inventory | Resource Graph resources/containers; ARM workspace detail; managed-group resources; tags/ownership | Resource/workspace/owner normalization; no complete tag history or management-group traversal |
| Policy and diagnostics | Policy resources; diagnostic settings on observed resources | Policy normalization; diagnostic payloads raw-only; unsupported types remain explicit limitations |
| Cost Management | Daily resource-ID/meter cost/usage, Actual and Amortized, pagination, windows of at most 31 days, all selected cost scopes | Qualified group and managed-group filtering; no automatic detailed shared-resource allocation or full meter/service enrichment |
| Budgets/commitments | Subscription budgets, reservation orders, Savings Plans | Raw evidence; Azure budget payload is not currently normalized into `budget` entities; no complete coverage/utilization/break-even modeling |
| Quotas | Compute usage by subscription and observed/configured region | Raw quota evidence; not live SKU stock availability |

Raw Azure files include `resource-inventory.ndjson`, `databricks-workspaces.json`, `managed-resource-inventory.ndjson`, `tags-ownership-inputs.ndjson`, `policy-inventory.ndjson`, `diagnostic-settings.ndjson`, `cost-management.ndjson`, `cost-scope-filter.json`, `budgets-commitments.json`, `compute-quotas.ndjson`, and `source-status.json`.

### 9.3 Implemented Databricks collection

Every included workspace writes under `raw/databricks/<workspace-key>` and produces domain source-status files.

| Domain | Sources / output families | Boundary |
|---|---|---|
| Workspace | Configured inventory, optional account workspaces, selected workspace settings, current metastore assignment, IP lists, optional SCIM groups | Settings/network/identity evidence is not a complete account governance inventory |
| Billing | `system.billing.usage`, `system.billing.list_prices` | Requires approved Warehouse and system-table access; list price is not contract price |
| Compute | Clusters, policies/ACLs, pools, events, `system.compute.node_timeline` | Inventory and timelines, not full utilization/right-sizing aggregation |
| Workloads | Jobs/tasks, runs, pipelines/details/events, `system.lakeflow.jobs`, job-run and pipeline-update timelines | Not complete per-run cost, retry-waste, overlap, or streaming analysis |
| SQL | Warehouse list, `system.query.history` | No full query-profile export or comprehensive queue/concurrency/cost attribution |
| Unity Catalog | Catalogs/bindings/schemas/tables, information schema, selected table detail/history | Hashed-suffix detail/history files remain raw-only under the current exact-name mapping |
| Governance | Compute policies, usage attribution fields, audit events, optional account budgets | No complete budget-policy assignment, alert delivery, or audit-cadence automation |
| Spark deep dive | Selected job-run metadata and related cluster events | No full Spark UI/event-log stage/task/executor metric collection |

### 9.4 SQL assets and evidence dependencies

The collector SQL directory contains twelve guarded assets:

| Asset | Source or operation |
|---|---|
| `DatabricksBillingUsage.sql` | `system.billing.usage` |
| `DatabricksListPrices.sql` | `system.billing.list_prices` |
| `DatabricksNodeTimeline.sql` | `system.compute.node_timeline` |
| `DatabricksJobs.sql` | `system.lakeflow.jobs` |
| `DatabricksJobRunTimeline.sql` | `system.lakeflow.job_run_timeline` |
| `DatabricksPipelineTimeline.sql` | `system.lakeflow.pipeline_update_timeline` |
| `DatabricksQueryHistory.sql` | `system.query.history` |
| `DatabricksGovernanceTags.sql` | Selected attribution fields in billing usage |
| `DatabricksGovernanceAudit.sql` | Selected services in `system.access.audit` |
| `DatabricksTableMetadata.sql` | `system.information_schema.tables` |
| `DatabricksTableDetail.sql` | `DESCRIBE DETAIL` with validated, backtick-escaped identifier components |
| `DatabricksTableHistory.sql` | Parameterized `DESCRIBE HISTORY` |

Time-based SQL uses explicit interval boundaries/overlap tests; table identifiers are parameterized. Statement polling, result chunks, and missing fields need contract tests. Warehouse access, table grants, retention, and actual data arrival are separate prerequisites.

### 9.5 Full target discovery and aggregation inventory

The following requirements remain in scope for the end-to-end vision even where automation is partial:

| Area | Required evidence and aggregation | Current disposition |
|---|---|---|
| Azure topology | Tenant/subscription/group/resource hierarchy; workspace tier/region/network/encryption; managed/supporting resources; tags/owners; policy/diagnostics/quota | Partial, strongest at resource-group scope |
| Azure financial | Actual/amortized daily meter cost, quantity/unit/SKU/tags, marketplace/storage/monitoring/egress, forecast/budget variance, commitment benefits | Cost query and basic inventory implemented; enrichments/forecast/benefit analysis incomplete |
| Account/workspace | IDs/status, metastore/bindings, settings, entitlement groups/principals, tags, private/serverless connectivity, system-table availability/retention, account reports/Governance Hub | Partial collection and manual review |
| Usage/attribution | Corrected/restated DBUs, prices, product/SKU, workload metadata, tags; owner/team/project/business-unit/environment/cost-center/data-product allocation by count and spend | Billing sources exist; normalized attribution primarily Azure-cost tags |
| Classic compute | Driver/worker/runtime/Photon/policy/pools/spot; startup/active/idle/scale/termination/failure intervals; worker-hours, occupancy percentiles, resource utilization, runtime adoption, idle cost | Inventory/events/SQL timeline available; most aggregations deferred |
| Jobs/pipelines | Definitions, owner/run-as, schedules/triggers/concurrency, dependencies, retry/repair, setup/queue/execution/cleanup, task state, checkpoint semantics | Partial collection; cost per successful run, failed/retry cost, overlap and reprocessing analysis incomplete |
| SQL | Type/size/scaling/autostop, events, concurrency, queue/compile/execute/total time, rows/bytes/spill/cache, fingerprints, refresh patterns, p50/p95 and cost | Warehouse/query-history collection; advanced aggregation/profiles deferred |
| Spark | Application/job/stage/task/executor IDs, critical path, duration distributions, input/output, shuffle/fetch wait, spill, GC, CPU/memory/I/O, scheduler/serialization, retries/loss/cache/AQE | Selected metadata only; detailed evidence requires manual export/future collector |
| Delta/layout | Format/size/files/distributions/partitions/clustering, statistics, DV compatibility, merge/write amplification, OPTIMIZE/VACUUM, access predicates, storage lifecycle and recovery constraints | UC metadata and selected raw detail/history; advanced normalization/detectors deferred |
| Code/plans | Opt-in UDF/native, driver loops/collect/toPandas, repeated actions, scans, joins/stats, sorts, partitions, caching and incremental evidence | Lab examples exist; customer source scanner deferred |
| Streaming | Trigger/freshness, arrivals, input per trigger, processing/idle, state/checkpoint, backlog/late data, 24/7 cost, AvailableNow/enhanced-autoscaling suitability | Dedicated analysis deferred |
| GPU/serving | GPU type/count/library use/utilization, training/inference time, endpoint throughput/latency/scaling, batch-inference and idle candidates | Dedicated collection/detectors deferred |
| Pools/spot | Pool consumers and idle instances/timelines, Azure idle cost, driver/worker mix, evictions/fallback/retries, interruption/SLA | Inventory and driver-spot rule; detailed cost/reliability model deferred |
| FinOps | Budgets/notifications, usage-policy assignments, sizing standards, policy exceptions/expiry, dashboards, monthly reports, audited tag housekeeping and recurring reviews | Some raw sources/rules; process operational and assignment analysis incomplete |
| Commitments | Eligible stable demand after waste removal, term/coverage/utilization, contracts, renewal, migration/forecast and break-even | Raw inventory plus manual Finance assessment; full model deferred |

Idle pool instances can incur Azure infrastructure cost without DBU charges. Tags added today do not repair historical attribution. Shared-cost allocation must be approved, not invented to increase match rates.

### 9.6 Reliability and status contract

- Azure read helpers allow only GET and approved Resource Graph/Cost Management POST endpoints.
- Databricks allows GET plus SQL Statements and historical cluster-events POST.
- Mutation SQL and unsupported POST paths are rejected.
- Pagination is bounded; remaining continuation is explicit, not silently discarded.
- Transient retries are bounded. Permanent unsupported-resource/authorization/bad-request conditions are not retried as capacity/transient failures; throttling is distinct.
- Cost Management query/forecast uses a header-preserving PowerShell HTTP transport with Azure CLI authentication and a stable toolkit client identifier. Requests are paced at least 20 seconds apart within the collector process. HTTP 429 honors the largest server cooldown and uses a 60/120/240-second fallback plus jitter. Exhausted throttling stops remaining cost windows/bases/scopes; a server cooldown over ten minutes stops instead of being shortened. These are client safeguards, not a guarantee against shared Azure quotas.
- Item counts, start/end timestamps, outputs, limitations, and errors are preserved.
- `passed` means the source call succeeded within its visibility; `partial` means incomplete; `failed` means unreliable/unavailable; `pending telemetry` includes delayed or unconfigured sources; `skipped` means not selected.
- Any partial/failed/pending collector makes the run manifest partial; skipped alone does not.
- Current limitations: no universal Azure CLI HTTP deadline, whole-run timeout, complete cancellation checkpoints, incremental partition resume, or global collector timeout. SQL's deadline is not a substitute.

<a id="model"></a>
## 10. Normalization, correlation, cost, and quality

### 10.1 Model and provenance

The schema 1.0 envelope carries `schemaVersion`, `entityType`, `assessmentRunId`, `sourceSystem`, `sourceIdentifier`, extraction/effective timestamps, `customerScope`, `collectionStatus`, `qualityFlags`, sensitivity classification, `normalized`, and `provenance`.

Provenance preserves source-relative file, record ordinal, and raw source data. Canonical Azure IDs normalize separators/case/trailing slash. Unmatched and ambiguous relationships remain explicit; a forced match is prohibited.

Twenty entity mappings currently exist:

```text
azure_resource, workspace, owner, azure_cost, databricks_usage, list_price,
compute, compute_event, node_timeline, pool, job, job_run, pipeline,
warehouse, query, table, table_file_summary, table_operation, policy, budget
```

A mapped entity is not proof that each collector populates it. Quotas, diagnostics, Azure budget/commitment payloads, many ACL/audit/metadata exports, selected Spark metadata, and suffixed table details/history may remain raw-only.

The original 33-entity target also requires explicit normalized `assessment_run`, `source_collection`, `scope`, `tag`, `commitment`, `task`, `task_run`, `spark_application`, `spark_stage`, `spark_task_summary`, `finding`, `validation_experiment`, and `benefit_measurement`. Some concepts exist in separate top-level JSON artifacts, but the full normalized entity contract is not delivered.

Record-level quality flags and sensitivity labels are currently coarse. Do not mistake a parsed record's `passed` label for complete source coverage.

### 10.2 Correlation and filtering

Required keys include Azure subscription/group/resource IDs, Databricks account/workspace/cluster/Warehouse/job/task/run/pipeline/query/statement IDs, approved notebook/identity fields, UC object IDs, and tags/owners.

Implemented scope filtering uses exact selected workspace/group identities, managed-group evidence, and selected subscriptions. Costs correlate by canonical resource ID. Duplicate selected/managed inventory is removed by canonical identity. Broader account inventories cannot silently enlarge an explicitly empty workspace selection.

Correlation remains incomplete for many workload-level relationships. Full many-to-many allocation, lineage, and historical ownership require additional evidence and rules.

### 10.3 Financial calculation rules

1. Preserve Actual and Amortized costs separately; only the configured reporting basis feeds rankings, attribution, and detectors.
2. Join list prices by SKU and effective half-open date interval; preserve billing corrections/restatements.
3. Label list-price estimates separately from invoiced/contract/commitment-adjusted costs.
4. Do not sum currencies without an approved exchange source/date; tax treatment is unknown unless supplied.
5. Prevent adding underlying serverless VM cost twice, or adding DBU estimates when Azure rows already include Databricks charges.
6. Preserve authoritative/collected totals, variance/tolerance, matched/unmatched/excluded amounts, and duplicate-prevention explanation.
7. Do not interpret zero variance as good attribution; both totals may agree while most cost is unmatched.
8. Approved shared allocation, full contract pricing, commitment-adjusted calculations, and detailed tax inputs remain deferred.

Unit economics should include cost per successful run, TB processed, refresh/data product, query/dashboard, active user/team, model request, or business outcome where the denominator is valid. Incomparable workloads must not be ranked as if their units were equivalent.

### 10.4 Quality and confidence

The target dimensions are coverage, freshness, completeness, consistency, attribution, sample adequacy, and source authority. Findings use High/Medium/Low/Insufficient with rationale.

Current quality scoring is implemented but coarse, especially source age/authority. Unknown savings stays unknown. Missing minimum evidence should yield an evidence-gap action or manual review rather than an unjustified technical recommendation.

<a id="detectors"></a>
## 11. Detector and finding contract

### 11.1 Implemented catalog

| Rule/gate | Input | Output boundary |
|---|---|---|
| Interactive auto-termination | Interactive compute configuration and configured threshold | Candidate for missing/excessive termination; no inferred idle savings |
| `DYN-AUTOSCALING` | Fixed-size configuration and utilization/timeline evidence | Evidence gate/candidate; configuration alone does not prove safe target sizing |
| `MON-UNOWNED-COST` | Material Azure cost and owner tags | Ownership gap for the reporting basis; incomplete tagging can limit confidence |
| `WRK-JOB-COMPUTE` | Scheduled job and existing all-purpose cluster reference | Review job-compute suitability; validate owner/service constraints |
| `MON-MISSING-BUDGET` | Cost evidence and normalized budget evidence | Review missing budget evidence, not proof no Azure budget exists |
| `WRK-DRIVER-ON-SPOT` | Driver/availability configuration | Review driver resilience; does not automatically recommend against spot workers |

Because Azure budget/commitment raw JSON is not normalized as `budget`, budget findings need particular human verification. Threshold labels do not establish a validated monthly projection for every input grain.

### 11.2 Required catalog beyond the implemented subset

- **Resources:** non-Delta material workloads; SQL on general Spark; legacy runtime/instances; GPU without acceleration; persistent Classic with bursty demand; family/size mismatch; missing sizing standards; Photon suitability.
- **Dynamic allocation:** ineffective autoscaling bounds; excessive idle time; pool waste/orphan consumers; streaming scale-down limitations; policy coverage.
- **Monitoring:** tag propagation; missing business-unit/project/environment fields; unattributed serverless; alert ownership; anomalies; missing system-table access; OpenSharing egress; stale/audited tag cleanup; recurring cost review.
- **Workload design:** unnecessary always-on streaming; safe spot eligibility; full reprocessing; joins/shuffle; UDF bottlenecks; layout/maintenance; repeated BI/materialization.

Each new detector SHALL have positive, negative, boundary, insufficient-evidence, false-positive, and human-validation examples before release.

### 11.3 Finding and backlog requirements

A finding SHALL state identity, category/domain, affected assets, evidence/window, measured baseline, confidence/limitations, benefit mechanism, proposed action, alternatives, effort/risk/dependencies, service/security impact, experiment, success/rollback thresholds, and owner/approver.

Current machine findings include evidence, confidence, limitations, unknown savings by default, recommended action, and `humanValidationRequired: true`. Generated backlog imports are proposed items, not approved work.

The desired lifecycle is:

```text
observed -> candidate -> evidence reviewed -> experiment validated
         -> accepted/rejected/deferred -> implemented -> measured benefit
```

Quick wins are low-risk/reversible configuration or ownership changes; engineering changes require code/query/table benchmarks; architectural changes require design/migration/Finance decisions. All three require change control.

<a id="outputs"></a>
## 12. Final output specification

### 12.1 Persistent machine-readable run

| Path | Purpose |
|---|---|
| `assessment-config.json` | Effective scope/settings snapshot for reproducibility |
| `assessment-manifest.json` | Version/run/customer IDs, timestamps, selected scope, analysis window, collectors, status |
| `collection-status.json` | Collector counts, status, timing, outputs, limitations, errors |
| `raw/azure`, `raw/databricks/<workspace-key>` | Source evidence and source-status files |
| `source-inventory.json` | Raw source paths, counts, parse errors, mappings, reported statuses |
| `scope-filter.json` | Derived/declared allowed boundary, exclusions, and scope limitations |
| `normalized/<entity>.ndjson` | Open-format normalized records with provenance |
| `normalized/correlation.json` | Correlation rules and matched/unmatched/ambiguous evidence |
| `cost-reconciliation.json` | Cost basis/currency/totals/variance/attribution/exclusions/duplication safeguards |
| `telemetry-quality.json` | Source/overall quality, confidence, and evidence gaps |
| `attribution-coverage.json` | Record/spend ownership coverage |
| `optimization-candidates.json` | Findings and candidate/insufficient-evidence counts |
| `backlog-import.json` | Proposed optimization and evidence-gap work items |
| `benefits-baseline.json` | Versioned baseline, comparison window, normalization placeholder, `realizedSavings: null` |
| `errors.json` | Parse/read and partial/failed/pending source details |
| `logs/assessment.log` | PowerShell collection transcript |

Normalized NDJSON is the implemented alternative to the proposed Parquet format. Not every entity will be present in every run. Scope snapshots/raw provenance can contain sensitive customer metadata and must be protected together.

The browser's **Saved snapshots** dropdown beside the Light/Dark toggle reopens these
persisted runs without recollection, including partial runs. It lists all snapshots by
collection timestamp, newest first, and refreshes on completion and dropdown focus.
A selected run ID is retained in the URL so page refresh reopens the same snapshot
without Azure discovery. Restarting the local host with the same output root preserves
the history; review decisions remain separate from generated evidence.

**New assessment** returns to Step 1 with editable random-suffixed customer/assessment
IDs and a default window covering the previous 30 complete UTC days, ending at today's
midnight UTC. Scope and deep-dive targets are cleared. It resets approvals, validation,
run progress, results, filters, and review/export
UI state without deleting snapshots or recorded decisions. Installation defaults and
tenant connection settings are retained. It replaces the selected run in the URL with
`?new=1`, so refresh stays on a fresh Configure screen. Selecting a saved snapshot
restores the snapshot URL behavior. Reset is disabled while discovery, sign-in,
validation, or a run is active; it never starts an assessment automatically.

Selecting a snapshot enters historical mode: Configure, Validate, and Run display saved
scope and collector outcomes without loading a live configuration or issuing readiness
calls. The saved collector outcomes are not represented as a stored pre-run validation
report. Live validation requires an explicit Validate configuration/Run validation/retry
action; navigation and configuration/approval changes cannot start it.
Re-running existing results requires confirmation, and cancel preserves the report.
Returning from Configure without changes opens the existing report rather than rerunning.

Selecting a subscription, or first loading a setup with preselected subscriptions, automatically
includes its discovered workspace-containing resource groups and new workspaces. Initial
defaults apply once after successful discovery; retries keep edits and manual exclusions.
Saved snapshots retain their original scope. Empty groups remain unchecked by default, and
manual deselections are preserved when another subscription is selected. Qualified group
IDs keep same-named groups independent across subscriptions. Unset Warehouse choices default
to the smallest running Warehouse, otherwise the smallest stopped one. Existing choices and
explicit None are preserved. Warehouse use requires explicit approval; initial live load and
included workspace/Warehouse changes clear old approval. Selection never starts compute,
validation, or collection.

Deep-dive run IDs and table names are configured per workspace. Single-workspace legacy
targets are migrated before adding discovered workspace groups; ambiguous multi-workspace
global lists require explicit assignment or removal. Collectors do not send a run ID to
every selected workspace. Empty workspace target lists skip the optional deep dive, while
selected run deep dives still disclose the lack of detailed Spark UI metrics. Missing
SQL Warehouse guidance names workspaces still lacking a selection and displays discovery
errors without guessing. Listing and default selection never start compute.

An optional **Pipeline timeline permission setup** panel is separate from read-only
validation/collection and unavailable in snapshots or demo mode. Warehouse approval permits
identity and read-access queries, not grants. The server verifies `current_user()` and probes
pipeline timeline SELECT access. A successful query, including zero rows, shows Already
accessible with no grants. Only an explicit permission denial previews the exact
USE CATALOG on system, USE SCHEMA on system.lakeflow, and SELECT on
system.lakeflow.pipeline_update_timeline grants, then requires separate confirmation.
Other query failures do not suggest grants, and a previous target's success is not applied
to a different workspace selection.
Only the verified current identity can receive them, using its existing grant authority.
Five-minute previews, identity re-verification, one-shot apply, loopback/same-origin routes,
and local auditing bound the action. Shared-metastore permissions can affect other workspaces.
No elevation, automatic retry, rollback, or automatic revalidation occurs. Partial/unknown
outcomes stay explicit. Saved terminal setup outcomes recover from audits after a host
restart without SQL; unused previews are invalidated, and interrupted submitted grants
require audit/actual-permission inspection before retrying. Failed status requests stop the
spinner while an unresolved outcome still blocks new live work. Explicit SQL failures mark
the denied grant failed, not unknown; grant-authority denials require an authorized Unity
Catalog administrator, never elevation by the tool. Previewing/canceling grants preserves
the validation report. A successful post-grant SELECT verifies that access, not all assessment coverage.

The panel also provides a display/copy-only **Manual permission repair commands** guide:
target-bound SQL grants, verification SQL, and an optional PowerShell 7/Azure CLI command
for an authorized Account Admin to establish the selected workspace's metastore administrator.
The latter validates identity, account role and assignment, refuses existing-administrator
replacement, and requires exact metastore-ID confirmation before one account-level PUT.
Broad persistent privileges and shared-metastore impact are explicit; the UI never executes
this command. Existing administrators/designated administrator groups are preferred.
Unknown outcomes and non-permission failures do not offer manual changes. Successful access
retains reference commands without recommending a permission change.
A green access result includes full-validation and Continue actions. These share the main
validation controls' rerun confirmation and operation guards; only full validation can
enable continuation, and collection still needs its separate start action.

Manage snapshots supports permanent single-run and bulk deletion with a second confirmation
listing the exact run IDs. The local API removes only matching terminal run folders beneath
the output root, rejects active runs and links/junctions, and reports per-run failures.
Bulk deletion never sweeps the output root or includes runs created after confirmation.
Deleting the selected run clears the results and snapshot URL without starting collection.

Workflow steps retain their numbers and change from gray to green only on completion.
Configure uses valid local fields/scope, Validate requires backend readiness, Run requires
collection completion, Visualize requires loaded results, Review requires decisions and
reviewers, and Export requires a download. The active-page outline does not imply completion.

Validation first checks required engagement IDs, scope, analysis dates, output settings,
and SQL approvals locally. Invalid configuration produces named blockers and a route
back to Configure without launching PowerShell or cloud reads. Once local checks pass,
backend readiness remains mandatory. Early PowerShell failures preserve their blocking
report and actual error even if no source-progress events were emitted.

Configure exposes optional Databricks account UUID/host settings; live readiness verifies
account access and reads the v2.1 budgets API. Progress groups shared causes, supplies
specific remedies, and retains expandable source responses. Applicable Azure diagnostics
can pass with explicit unsupported-resource notes; entirely inapplicable checks stay neutral.
OPEN catalogs skip unnecessary binding calls, while isolated/unknown catalogs still require
binding visibility. Missing pipeline timeline SELECT access and detailed Spark metrics remain
explicit gaps; the app neither grants permissions nor imports Spark event logs.

The analysis maps hashed table-detail/history filenames into normalized evidence and
unwraps Azure budgets separately from commitment records. It decodes SQL-returned JSON
pricing, prefers effective list prices, retains Databricks service charges, and evaluates
unmatched cost only within the reporting cost basis. Unpriced usage stays an explicit gap.
SQL result conversion preserves single-row and chunked response arrays and rejects row
width/schema mismatches rather than creating incomplete records with manufactured nulls.

### 12.2 Exactly one human-readable assessment report

The final path is:

```text
assessment\output\<run-id>\reports\assessment-report.md
```

The 17 ordered sections are:

1. Executive summary.
2. Estate topology and scope.
3. Current cost baseline and reconciliation.
4. Top cost drivers.
5. Unattributed cost.
6. Compute and right-sizing.
7. SQL Warehouse and query.
8. Jobs and pipelines.
9. Spark deep-dive index.
10. Delta and data layout.
11. Governance, policies, budgets, and FinOps.
12. Commitment readiness.
13. Telemetry quality and limitations.
14. Prioritized backlog.
15. 30/60/90-day roadmap.
16. Benefits realization.
17. Human validation and sign-off.

Companion exports are `top-cost-drivers.csv`, `prioritized-backlog.csv`, and `human-validation-sign-off.csv`. These do not create additional Markdown reports. The separate lab validation report remains a different operational artifact, not another customer assessment report.

Report sections are navigable summaries with evidence links, not proof of complete automated analysis in each domain. Raw detail is retained while human-facing cost rows are aggregated to avoid enormous repetitive reports.

### 12.3 Regeneration and review

```powershell
.\assessment\Invoke-Assessment.ps1 -Action Reports
.\assessment\Invoke-Assessment.ps1 -Action Reports -RunRoot 'C:\assessments\<run-id>' -NoOpenReport
.\assessment\Invoke-Assessment.ps1 -Action Open -RunRoot 'C:\assessments\<run-id>'
```

Regeneration does not recollect and uses the saved config when available. Generated findings should not be edited in place. Preserve decisions in a separately retained sign-off register/CSV before regeneration, which rewrites generated outputs.

### 12.4 Workshop output package

The complete customer deliverable also requires a completed profile/discovery record, evidence inventory, cost-driver map, workload packs, governance/commitment decisions, agreed owners, executive readout, roadmap, and benefits plan. Generated report skeletons and templates require customer-specific completion.

<a id="security"></a>
## 13. Authentication, permissions, and data protection

### 13.1 Authentication and roles

Azure ARM uses the active Azure CLI identity. Databricks requests obtain short-lived Entra tokens for application `2ff814a6-3304-4ab8-85cb-cd0e6f879c1d`. Tokens are held in memory and are not stored in output/config; PAT input is not the implemented path.

| Surface | Required access |
|---|---|
| Subscription/group/workspace/managed-resource discovery | Reader at the selected scope; picker listing needs adequate subscription visibility |
| Policy/diagnostics | Appropriate Policy Reader and Monitoring Reader/read actions |
| Cost/budget queries | Cost Management Reader at each queried scope |
| Reservation/Savings Plan inventory | Relevant billing/Reservations/Savings Plan reader permissions |
| Workspace object inventory | Workspace membership plus view permissions; broader completeness may require delegated/admin visibility |
| Account APIs | Configured account ID/host and account-view/budget visibility |
| SQL-backed sources | Warehouse `CAN USE`, system/UC `USE CATALOG`, `USE SCHEMA`, `SELECT`, and relevant metadata access |
| UC bindings | Required `BROWSE`/`READ METADATA` visibility where enforced |
| Selected deep dives | Approved job/table metadata and applicable event/source access |

Assessment does not require Contributor/Owner or permission to remediate. Lab deployment does require separate resource and RBAC creation rights. Authentication success is not proof of authorization or full visibility.

### 13.2 Read-only enforcement

- Runtime method/endpoint allowlists and SQL mutation-keyword guards.
- Static mutation-pattern scanning before collection.
- No job run-now, compute start/stop/edit, maintenance SQL, policy mutation, or purchase in assessment.
- API errors remain visible; source gaps are not success-shaped empty recommendations.
- These guards are defense in depth, not a replacement for least-privilege credentials.

### 13.3 Redaction and custody

Databricks recursive redaction removes secret/password/token/private-key fields, Spark environment variables and task/job parameter collections; omits query text by default; hashes approved identity/notebook/table fields according to config.

Set a customer-controlled hash salt using the configured environment variable, normally `ADB_ASSESSMENT_HASH_SALT`. The deterministic customer/assessment fallback is not a secret production salt.

Azure raw tags/properties are **not** processed by the Databricks recursive redactor. Provenance preserves raw records. Customer-managed encrypted storage, access controls, retention/deletion, export approval, and secret/metadata review apply to the entire run root. Built-in encryption, retention deletion, and an external audit sink are not implemented.

<a id="corrections"></a>
## 14. Implementation corrections and operational lessons

| Symptom/request | Root distinction and delivered response | Remaining constraint |
|---|---|---|
| Setup appeared to hang | Progress by stage; explicit API/catalog checks; asynchronous state waits | Remote readiness still depends on permissions/network/UC |
| `main` catalog unavailable | Use workspace-managed UC catalog and dedicated schema | Not permission bypass or guaranteed metastore provisioning |
| External storage access blocked | Observe policy-effective public access; skip optional external location | External-storage scenario requires an approved compatible network design |
| Classic stockout guard rejected rerun | Six-hour guard prevents repeated attempts; explicit override available | Capacity is external; override incurs another attempt, not a fix |
| Missing `result_state` during pending run | Optional-field-safe polling; display pending state instead of strict property failure | Terminal success still must be verified |
| RUNNING/PENDING for many minutes | Print task states/elapsed time; separate startup guard; cancel unfinished run | 600-second startup guard is independent of overall timeout |
| Classic capacity still unavailable | Supported alternate driver/worker node types and bounded retries | Recorded East US stockout remains unresolved |
| Serverless CDC comparison differed | Deterministic keyed-snapshot correction and bidirectional equality validation | Fixture correctness does not validate every customer CDC semantic |
| Unsupported Azure diagnostic settings repeatedly retried | Distinguish permanent `ResourceTypeNotSupported` from transient/429 errors | Unsupported resources still report coverage limitations |
| SQL POST said statement was absent | Handle dictionary as well as object body properties; test actual SQL submission path | SQL requires configured Warehouse and grants |
| Human found failures after handoff | Mandatory real documented-command gate added alongside regression tests | Mocks/static scans cannot certify production completeness |
| Warehouse approval blocked simple run/readiness | Persisted Run approval supported; readiness strips IDs unless explicit approval | Preserve cost awareness; do not silently auto-approve new Warehouses |
| Too many scripts and reports | One wrapper with default Run/open; one consolidated Markdown plus CSVs | Advanced/lab commands remain separate for distinct safety boundaries |
| Unrelated Azure resources in report | Collection and normalization scope filters; managed/supporting group inclusion; basis isolation | RG-level inclusion can still need shared-resource allocation |
| Multiple subscriptions/groups needed | Picker, arrays, qualified IDs, all cost scopes, discovered workspace scope | Cross-tenant collection is separate; inaccessible targets stop |
| Regeneration drift or wrong run opened | Saved effective config, invocation-relative paths, exact returned-run opening | Explicit config override intentionally changes reanalysis context |
| Cost API returned 429 | Preserve failed/partial status after bounded retries; later full run succeeded | Throttling is not zero cost; no guaranteed API availability |

Regression evidence includes Windows-safe JSON request bodies/continuation URLs, missing-field handling, culture-independent SQL timestamps, source status propagation, and same-name cross-subscription boundaries. Historical fixes do not establish every broader collector behavior as complete.

<a id="validation"></a>
## 15. Validation record and test requirements

### 15.1 Historical infrastructure validation

Recorded on 2026-09-25, not rerun by this documentation change:

- Bicep and parameter builds, Azure template validation, and additive what-if passed.
- Pester: **17 passed**; Checkov: **4 passed**, zero unresolved failures after recorded non-production exceptions.
- PowerShell parsing, notebook compilation, config JSON parsing, provider/quota checks, and storage-scoped RBAC verification passed.
- Serverless sample setup run `855276813802690` passed.
- Final serverless scenario run `1046670031216278` passed.
- SQL setup, result equivalence, four-statement concurrency, and data validation passed.
- Classic run `815894152576571` was blocked by VM stockout; subsequent bounded attempts did not establish success.
- Recorded shutdown: zero running clusters/Warehouses.
- Formal full reference acceptance and human sign-off remain incomplete.

Detailed evidence and statement IDs remain in [lab validation](infra/reports/validation-report.md), [validation-summary.json](infra/reports/validation-summary.json), and [sql-workload-runs.json](infra/reports/sql-workload-runs.json).

### 15.2 Latest assessment automated validation

Recorded on 2026-09-26 using:

```powershell
.\assessment\Invoke-Assessment.ps1 -Action Validate
```

| Check | Recorded result |
|---|---|
| Static read-only scan | `AssessmentReadOnlySafety=PASS` |
| Pester | 136 passed, 0 failed, 0 skipped |
| Python contracts/model/reports | 40 passed, 0 failed |
| Combined assessment tests | **176 passed** |
| PowerShell parsing | 34 scripts, zero parse errors |
| Validation command | Exit 0 |

These counts supersede inconsistent older assessment summaries. Do not add historical infrastructure tests or older assessment totals to 176 and label the sum a single current suite.

### 15.3 Real front-door scope validation

| Execution | Recorded result |
|---|---|
| Explicit-scope Readiness from the assessment directory | Run `adb-cost-assessment-20260926T214513741Z-2ebbd911`; exit 0; SQL IDs omitted; partial with Cost Management 429 exhaustion |
| Real console picker + Run from repository root | Run `adb-cost-assessment-20260926T214949861Z-1e4e3e10`; console choices supplied through stdin; collection, analysis, one report, and default open completed |
| Reports against that run without config override | Exit 0; saved scope used, no recollection, report SHA-256 unchanged |
| Open against that run | Exit 0; report passed to the OS opener |
| Picker cancellation | Expected nonzero exit; no new run directory |
| Nonexistent group | Rejected before collection without broader fallback |

Full picker-run verification:

- One selected workshop subscription/group plus the associated managed group.
- **76 Azure cost rows** across the collected cost evidence; not a DBU row count or savings amount.
- **15 normalized Azure resource records**, zero outside allowed groups.
- Zero outside-scope cost rows and zero outside-scope resource-group IDs in the consolidated report.
- Exactly **one Markdown report**.
- **63 JSON/NDJSON files** parsed successfully.
- Snapshot and manifest preserved qualified scope IDs; temporary effective configs were removed.
- Post-run SQL Warehouse GET returned `STOPPED`, with five-minute autostop.
- No Warehouse was selected by discovery and no SQL approval was used for that full picker run.

The final manifest was **partial**: SQL-backed sources intentionally lacked a Warehouse, optional account/metadata/diagnostic coverage remained limited, and deep dives were not selected. This validates the end-to-end scope/report path, not a complete customer assessment.

Multi-subscription collection, same-name groups, inaccessible/disabled/cross-tenant inputs, and partial subscription failures were tested with fixtures/mocks. They were not validated against a live multi-subscription customer estate.

Earlier SQL-approved readiness/full runs demonstrated real SQL submission and recorded billing/query/governance evidence; they are distinct historical runs, not part of the no-SQL picker validation. See [assessment test results](assessment/test-results.md).

### 15.4 Required regression matrix

| Layer | Mandatory cases |
|---|---|
| Configuration/entry point | Invalid dates/IDs/limits; empty targets; config precedence; both working directories; custom output root; action restrictions; exact returned run; snapshot regeneration |
| Selection | Single/multiple subscriptions/groups; full IDs; duplicate names; cancel/blank/invalid; inaccessible/disabled/cross-tenant; zero workspace; no broadening |
| Scope/data isolation | Managed groups, explicit supporting groups, stale templates, account inventory, deduplication, out-of-scope costs, selected reporting basis |
| Azure transport | Body serialization, paging/windows, continuation, throttling, permanent failure, partial multi-scope result |
| Databricks transport | Optional fields, list/SCIM/events paging, SQL dictionary/object body, polling/chunks/deadline, permission errors, delayed telemetry |
| Financial/model | Corrections, price dates, actual/amortized separation, currency, serverless duplication, unmatched/ambiguous IDs, source provenance |
| Detectors | Positive, negative, boundary, missing evidence, false-positive exclusion, human-review requirement |
| Privacy | Token non-persistence, sensitive-field redaction, identity/query/path controls, sanitized exports |
| Reports | One Markdown, ordered subjects, evidence links, unknown savings, reproducible regeneration, CSV contracts |
| Live handoff | Applicable documented command runs, explicit scope, actual failures/limitations, compute state, and human review |

No static string test, synthetic report, or successful compile alone is sufficient for handoff. If a documented applicable command fails, fix the root cause, add regression coverage, rerun that command, and record the outcome or explicitly block acceptance.

<a id="acceptance"></a>
## 16. Acceptance and human handoff

### 16.1 Acceptance gates

| Gate | Evidence required | Current disposition |
|---|---|---|
| Specification | Scope, modules, assets, behavior, output, risks, and remaining work are traceable | Consolidated here |
| Lab deployment | Reviewed additive deployment, identity/RBAC/security controls, exact ownership boundary | Historical validation available |
| All compute modes | Classic, serverless job/notebook, and SQL correctness/performance/evidence | Partial; Classic blocked and separate notebook acceptance not established |
| Assessment workflow | Select/collect/analyze/open; preserved snapshot; safe failure and scope boundary | Validated for recorded lab path |
| Collection completeness | Every selected workspace/source succeeds or has a named limitation; required telemetry available | Scope-dependent and partial |
| Financial correctness | Basis/currency/boundaries explicit; variance explained; no double counting; unmatched cost visible | Bounded tests; full allocation/contract modeling incomplete |
| Findings | Evidence/window/confidence/limitations; no unsupported savings; owner review | Implemented bounded catalog, not full target |
| Reports | One reproducible Markdown with linked evidence and review exports | Validated |
| Human approval | Technical/FinOps/workload sign-off and exceptions accepted | Operational; not automatically complete |
| Benefits | Approved implementation plus comparable normalized before/after measurements | Not established |

A `partial` report may support a workshop **with limitations**. It cannot certify the full original specification or substantiate a savings claim without the missing evidence.

### 16.2 Human review record

For each candidate capture reviewer/role, UTC time, finding ID, evidence links, accept/reject/defer/more-evidence decision, business/SLA context, cost mechanism, correctness/performance/reliability/security impact, experiment, success/rollback thresholds, owner/approver, due date, dependencies, and rationale.

Approvers include platform and workload owners, data engineering/SQL owners, FinOps, security/governance as needed, and the executive sponsor for architecture/commitments.

Human validation SHALL:

1. Confirm the selected subscriptions/groups/workspaces and exclusions against approved scope.
2. Check managed/supporting group attribution, especially mixed-use groups.
3. Reconcile the chosen billing basis and investigate unmatched/duplicate/currency issues.
4. Review source statuses and grants before using absence as evidence.
5. Inspect Spark UI/query profiles/table history for selected workload conclusions.
6. Verify equivalence, service metrics, and rollback for experiments.
7. Confirm required compute/autostop and lab shutdown behavior without assessment-side mutations.
8. Review/export sanitized evidence and preserve the decision register before regenerating reports.
9. Obtain explicit final acceptance or named limitations.

<a id="post-implementation"></a>
## 17. Post-implementation plan and 30/60/90-day roadmap

### 17.1 Completed baseline to preserve

- One consolidated assessment report and single front-door invocation.
- Separate billable lab and read-only assessment boundaries.
- Scope selection, qualified group identity, all selected subscription cost scopes, workspace matching, and snapshot-based regeneration.
- No transfer of old SQL/deep-dive identifiers to new targets.
- Explicit failures/partial telemetry and dated test evidence.
- Working serverless/SQL lab scenarios with correctness checks and cost controls.
- Human review and no-realized-savings guardrails.

Future work SHALL preserve these behaviors through the regression matrix; it must not reintroduce multiple report Markdown files, silent broadening, or implicit Warehouse approval.

### 17.2 Remaining implementation and acceptance register

Priorities and horizons below are planning recommendations derived from the remaining requirements, not an approved implementation commitment. Named owners and dates must be assigned by the customer/project lead.

| ID | Priority / horizon | Work and dependency | Accountable role | Exit evidence |
|---|---|---|---|---|
| POST-01 | P0 / first 30 days | Complete human acceptance of current scope/report; prerequisite: source-status and financial review | Platform + FinOps + workload owners, names TBD | Signed review register with accepted limitations and no unsupported savings |
| POST-02 | P0 / first 30 days | Close required customer telemetry/permissions and configure approved per-workspace Warehouses; decide SQL cost approval before execution | Platform/UC/SQL owners | Actual SQL-backed collection, grants/retention documented, unavailable sources distinguished, autostop verified |
| POST-03 | P0 / when capacity permits | Validate Classic on approved available capacity; do not bypass stockout guards indefinitely or move region without approval | Azure platform + facilitator | Successful bounded Classic run, equality assertions, Spark evidence, shutdown; otherwise retain blocked status |
| POST-04 | P1 / first 30 days | Align reusable lab config/templates with bootstrap; replace lab-specific defaults only through reviewed configuration | Platform automation owner | One clear source of deployed limits, compatibility tests, no unintended resource changes |
| POST-05 | P1 / 30-60 days | Normalize collected Azure budgets/commitments and suffixed table detail/history; dependency: source schemas and attribution review | Toolkit/model owner | Mapping fixtures, accurate source coverage, no false "no budget" conclusion from raw-only evidence |
| POST-06 | P1 / 30-60 days | Add workload-level joins and compute/job/SQL utilization, queue, retry, worker-hour and unit-cost aggregation | Performance + toolkit owners | Grain/ID contracts, authoritative reconciliation, representative fixtures, exclusions and confidence |
| POST-07 | P1 / 30-60 days | Add approved Spark event/UI evidence and Delta file/layout analysis; dependency: customer opt-in and access | Spark/data owners | Stage/task/executor and table distribution evidence, bounded collection, validated detectors |
| POST-08 | P1 / 30-60 days | Add opt-in code/plan scanning and incremental/CDC recommendations | Engineering owner | Restricted-source handling, correctness/replay tests, no source export beyond approval |
| POST-09 | P1 / 30-90 days | Improve collector reliability: Azure deadlines, cancellation/checkpoints, resumable partitioned collection, source-age quality | Toolkit owner | Interruption/timeout/large-export tests, no corrupted completed partitions, visible partial status |
| POST-10 | P1 / 30-90 days | Finish reusable lab lifecycle: ownership manifest, collision checks, reset, expiration, separate notebook validation, exact teardown verification | Platform automation owner | Fresh deploy/reset/teardown test with immutable retained evidence and no out-of-scope mutation |
| POST-11 | P2 / 60-90 days | Add streaming/AvailableNow, GPU/serving, pool/spot reliability, OpenSharing/egress and anomaly detectors | Domain owners + toolkit owner | Each rule's minimum evidence and positive/negative/boundary/insufficient tests |
| POST-12 | P2 / 60-90 days | Add approved shared allocation, contract/tax inputs, commitments/coverage/utilization/forecast/break-even | FinOps + Finance | Customer-approved financial rules, meter eligibility, migration-aware scenarios, reconciliation tests |
| POST-13 | P2 / 60-90 days | Complete broader scope/model contracts: exclusions, management groups, business scopes, sampling, versioned config and remaining entities | Architecture + toolkit owner | Explicit schema/version migration and no ambiguous identity broadening |
| POST-14 | P1 / before customer delivery | Produce polished workshop deck, facilitator/participant guides, completed questionnaire, evidence packs, executive readout | Workshop lead + domain experts | Dry run of all nine modules/seven exercises within agenda; accessible evidence and owner-ready outputs |
| POST-15 | P2 / 60-90 days | Implement approved cross-run benefits comparison and recurring audit workflow | FinOps + toolkit owner | Comparable windows/basis/currency/volume; measured cost and SLO changes; retained baseline and regression checks |
| POST-16 | P1 / approved pilot | Extend live testing to a deliberately approved multi-workspace/multi-subscription estate | Customer platform + validation owner | Real selected-scope results, permissions/partial cases, no cross-subscription name leakage |

Unresolved capacity, missing access, or lack of approval is a blocker to the relevant exit gate, not permission to invent evidence.

### 17.3 Customer optimization roadmap

**Days 0-30: establish control and validate.** Confirm baseline, close high-impact evidence and ownership gaps, agree tags/policies/budgets/alerts, run low-risk right-sizing/Photon/runtime/SQL experiments, and assign owners. Quick wins remain subject to change control.

**Days 31-60: implement validated engineering changes.** Roll out tested joins/UDF/incremental/retry changes, Delta layout/maintenance and SQL scaling adjustments; extend successful patterns carefully to comparable workloads; improve weak collectors/mappings.

**Days 61-90: architecture and benefits.** Execute approved serverless/isolation/layout migrations, make commitments against the post-rightsizing eligible baseline, institutionalize showback/chargeback and exceptions, rerun assessments, measure regressions/benefits, and refresh next-quarter priorities.

Every roadmap item needs a named owner and approver, target date, dependency, baseline/target, experiment, rollback, status, and evidence. Financial commitment decisions follow consumption cleanup and architecture review, not the reverse.

### 17.4 Measurement and operating cadence

Track customer-relevant measures: owner-attributed spend, policy coverage, idle hours/cost, failed/retry cost, cost per successful run/TB/refresh/query/request, queue/runtime p50/p95, freshness/SLA attainment, scans/shuffle/spill, maintenance cost, and commitment utilization.

Separate volume, rate, currency, and architecture effects in before/after comparison. Record implemented change dates and exceptional periods. Hold technical checkpoints after experiments and sponsor/FinOps reviews at the agreed monthly/30/60/90 cadence.

The present toolkit writes a versioned baseline but has no automated cross-run benefits comparator. `realizedSavings` stays null until an approved comparison supplies defensible measurements.

<a id="traceability"></a>
## 18. Requirements and implementation traceability

### 18.1 Source requirement coverage

| Source area | Consolidated coverage | Disposition |
|---|---|---|
| Workshop POS/OBJ, Sections 1-6 | Sections 1-4: L300, goals, roles, profile, prerequisites and guardrails | Specified/operational |
| Workshop DAT/discovery, Sections 7-9 | Sections 4-5, 9-10, 13: evidence, cost model, dates, privacy | Partial automation |
| Workshop AUT/Section 10 | Sections 8-13: modular read-only toolkit and output contracts | Working partial implementation |
| Workshop Modules A-I/Section 11 | Section 4.2 | All nine specified; automation varies |
| Workshop labs/Sections 12-13 | Sections 4.3-4.4 and 7 | Seven exercise requirements; bounded lab assets implemented |
| Workshop backlog/roadmap/Sections 14-17 | Sections 11-12, 16-17 | Generated proposals plus human process; benefits not realized |
| Workshop downstream assets/Sections 18-23 | Sections 4, 12, 16-17 | Some templates/docs exist; complete delivery assets/approval not proven |
| Workshop reference environment/Section 24 | Sections 6-7, 15, POST-03/04/10 | Deployment exists; larger lifecycle contract partial |
| Toolkit Sections 1-5 | Sections 1-3 and 8 | Boundary and UX implemented; broad scope schema partial |
| AZI-001 through AZI-010 | Sections 6 and 9.2/9.5 | Inventory, policies, diagnostics, quota; history/hierarchy incomplete |
| AZC-001 through AZC-010 | Sections 5, 9.2/9.5 and 10.3 | Actual/amortized collection; allocation/benefits/forecast incomplete |
| DBI-001 through DBI-010 | Sections 8-9 and 13 | Workspace/account/UC/settings subset; complete governance visibility not guaranteed |
| Toolkit Sections 6.4-6.16 | Section 9.3-9.5 | Every domain retained with its implemented/deferred boundary |
| Toolkit Section 7 | Sections 5 and 11 | Four official principles; six implemented rules/gates; rest explicitly deferred |
| Toolkit Sections 8-11 | Section 10 | 20 mappings versus 33 targets; financial and quality limitations explicit |
| Toolkit Sections 12-13 | Sections 12 and 16 | One report, machine/CSV evidence, human-review contract |
| Toolkit Sections 14-15 | Sections 9.6 and 13 | Guards/redaction/retries present; checkpoints/retention/global deadlines incomplete |
| Toolkit Sections 16-17 | Sections 15-16 | Dated tests/live evidence; no blanket full acceptance |
| Toolkit Sections 18-21 | Sections 9, 17-19 | Actual implementation layout, remaining phases, best-practice references |
| Later UX/scope requirements | Section 8, corrections, latest validation | Single command/report; selectable qualified scope; saved regeneration |

### 18.2 Repository deliverable map

| Path | Role |
|---|---|
| [This specification](AzureDatabricksCostOptimizationEndToEndSpecification.md) | Consolidated current-state and future requirement authority |
| [Workshop source requirements](L300AzureDatabricksCostOptimizationWorkshopRequirements.md) | Original granular workshop/reference-environment requirements |
| [Toolkit source requirements](AzureDatabricksAssessmentToolkitRequirements.md) | Original evidence/detector/model requirements |
| [Content guide](docs/AzureDatabricksCostOptimization.md) | Diagnostic/optimization reference framework |
| [Deployment plan](.azure/deployment-plan.md) | Historical Azure authorization, architecture, validation, deployment outcome |
| [Infrastructure runbook](infra/README.md) | Lab preparation, operation, and guarded cleanup |
| [Infrastructure reports](infra/reports) | Deployment/state/SQL/validation evidence |
| [Assessment user guide](assessment/USER-GUIDE.md) | Supported customer commands and scope-selection UX |
| [Assessment README](assessment/README.md) | Toolkit entry and documentation index |
| [Collector inventory](assessment/docs/collectors-and-outputs.md) | Source/output mappings |
| [Permissions](assessment/docs/permissions-and-authentication.md) | Read-access matrix |
| [Assessment test evidence](assessment/test-results.md) | Latest authoritative assessment counts and live-run limitations |
| [Human handoff gate](assessment/docs/human-handoff-gate.md) | Real-command validation and reviewer requirements |
| [Latest validated picker report](assessment/output/adb-cost-assessment-20260926T214949861Z-1e4e3e10/reports/assessment-report.md) | Persisted example of the final single-report format; partial telemetry |

<a id="references"></a>
## 19. Source references and technical currency

The supplied article and Microsoft guidance establish the discovery -> diagnosis -> optimization -> governance approach. This document summarizes them; it does not treat old release notes, blog defaults, or example sizes as universal production recommendations.

- [Microsoft Learn: cost-optimization best practices](https://learn.microsoft.com/en-us/azure/databricks/lakehouse-architecture/cost-optimization/best-practices) - reviewed during consolidation.
- [Azure Databricks pricing](https://azure.microsoft.com/en-us/pricing/details/databricks/) - price/SKU authority; record timestamp, region, currency, and contractual basis for any estimate.
- [Account usage reports](https://learn.microsoft.com/en-us/azure/databricks/admin/account-settings/usage).
- [Unity Catalog system tables](https://learn.microsoft.com/en-us/azure/databricks/admin/system-tables/).
- [Monitor costs using system tables](https://learn.microsoft.com/en-us/azure/databricks/admin/usage/system-tables).
- [Governance Hub](https://learn.microsoft.com/en-us/azure/databricks/admin/governance-hub/) - source article described beta status; recheck availability/status instead of asserting universal support.
- [Azure Cost Management analysis](https://learn.microsoft.com/en-us/azure/cost-management-billing/costs/quick-acm-cost-analysis).
- [Compute configuration best practices](https://learn.microsoft.com/en-us/azure/databricks/compute/cluster-config-best-practices).
- [Compute policies](https://learn.microsoft.com/en-us/azure/databricks/admin/clusters/policies).
- [SQL Warehouse types](https://learn.microsoft.com/en-us/azure/databricks/compute/sql-warehouse/warehouse-types).
- [Usage detail tags](https://learn.microsoft.com/en-us/azure/databricks/admin/account-settings/usage-detail-tags).
- [Serverless usage policies](https://learn.microsoft.com/en-us/azure/databricks/admin/usage/budget-policies).
- [Databricks budgets](https://learn.microsoft.com/en-us/azure/databricks/admin/account-settings/budgets).
- [Databricks workload optimization guide](https://www.databricks.com/discover/pages/optimize-data-workloads-guide#intro).

Technique-specific references are preserved in Section 5. Before each customer delivery, verify runtime/API compatibility, regional/serverless eligibility, preview state, pricing/commitment eligibility, and source retention. Record changes in this specification and rerun affected tests; do not silently change the evidence basis of an accepted report.
