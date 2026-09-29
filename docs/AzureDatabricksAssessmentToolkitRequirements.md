# Azure Databricks Cost Optimization Assessment Toolkit Requirements

> **Consolidated specification:** Use [Azure Databricks Cost Optimization: End-to-End Specification and Post-Implementation Plan](AzureDatabricksCostOptimizationEndToEndSpecification.md) for the complete start-to-finish requirements, implemented behavior, corrections, final output, validation, and remaining work. This document is retained as the original detailed toolkit requirement catalog. Its historical gap descriptions and SHALL statements are not claims about current implementation completeness.

## Document purpose

This document defines the requirements for a reusable, read-only **Azure Databricks Cost Optimization Assessment Toolkit**.

The toolkit SHALL collect and aggregate the customer evidence that is not currently collected by the workshop deployment, configuration, workload-generation, and validation scripts. It SHALL support an end-to-end discovery of an Azure Databricks estate and generate evidence-backed inputs for:

- The L300 Azure Databricks Cost Optimization Workshop.
- Current-state cost and architecture assessment.
- Workload deep dives.
- Cost attribution and governance analysis.
- A prioritized optimization backlog.
- A 30/60/90-day roadmap.
- Post-change benefits realization.

This document complements:

- [The Complete Guide to Azure Databricks Cost Optimization](./docs/AzureDatabricksCostOptimization.md)
- [L300 Azure Databricks Cost Optimization Workshop Requirements](./L300AzureDatabricksCostOptimizationWorkshopRequirements.md)
- [Microsoft Learn: Best practices for cost optimization](https://learn.microsoft.com/en-us/azure/databricks/lakehouse-architecture/cost-optimization/best-practices)

## 1. Current-state gap

The existing implementation provides a reference lab and controlled telemetry generator:

- `infra/scripts/Configure-DatabricksWorkspace.ps1` configures the dedicated workshop workspace.
- `infra/scripts/Initialize-SampleData.ps1` creates bounded sample data.
- `infra/scripts/Invoke-WorkshopWorkloads.ps1` runs controlled Classic and serverless scenarios.
- `infra/scripts/Invoke-SqlWorkshop.ps1` runs controlled SQL Warehouse scenarios.
- `infra/scripts/Test-WorkshopEnvironment.ps1` validates the reference environment.

These scripts SHALL NOT be treated as customer-estate assessment collectors.

They do not currently:

- Discover all customer accounts, subscriptions, workspaces, or workloads.
- Query and reconcile Azure infrastructure cost with Databricks DBU cost.
- Rank the customer's highest-cost workloads.
- Aggregate historical utilization or performance.
- Export Spark execution evidence across selected customer runs.
- Inventory the customer's Delta tables and file layouts.
- Measure governance, ownership, policy, budget, or tag coverage.
- Generate evidence-backed optimization candidates.
- Produce a customer optimization backlog automatically.

## 2. Goals

The toolkit SHALL:

1. Discover the Azure and Databricks scope selected by the customer.
2. Collect cost, usage, configuration, utilization, performance, ownership, and governance evidence.
3. Normalize data from sources with different grains and identifiers.
4. Reconcile Azure charges and Databricks usage without double counting.
5. Rank material cost drivers.
6. Identify optimization candidates aligned with official Azure Databricks best practices.
7. Record evidence provenance, quality, limitations, and confidence.
8. Produce machine-readable datasets and human-readable workshop artifacts.
9. Support repeated assessment runs and before/after comparisons.
10. Remain read-only against customer production infrastructure and Databricks objects.
11. Restrict Azure resource and cost evidence to selected Azure Databricks workspace resource groups, their managed resource groups, and explicitly approved supporting resource groups.
12. Exclude unrelated subscription resources and costs from topology, reconciliation, cost drivers, attribution, findings, and reports while recording excluded row counts for auditability.

## 3. Non-goals and safety boundary

The toolkit SHALL NOT:

- Create, resize, start, stop, restart, or terminate compute.
- Create or edit jobs, pipelines, warehouses, policies, tags, budgets, catalogs, schemas, or tables.
- Execute `OPTIMIZE`, `VACUUM`, `ALTER TABLE`, `MERGE`, or other mutating SQL.
- Change runtime, Photon, autoscaling, auto-termination, or node types.
- Purchase or exchange Reservations, Savings Plans, or Databricks commitments.
- Automatically implement recommendations.
- Present estimated savings as realized savings.
- Infer missing cost as zero.
- Infer missing telemetry as healthy behavior.
- Collect notebook source, query text, table names, identities, or tags beyond the customer-approved data-handling scope.

Any future remediation component SHALL be a separate tool with independent approval and change-control requirements.

## 4. Required operating modes

| Mode | Purpose | Required behavior |
|---|---|---|
| Readiness | Determine whether required access and telemetry are available | No assessment conclusions; report source availability and gaps |
| Inventory | Collect estate configuration and ownership | No workload execution |
| Cost baseline | Collect Azure and Databricks cost/usage | Reconcile totals and report unmatched cost |
| Standard assessment | Collect all broadly available historical evidence | Generate estate-level findings |
| Deep dive | Collect detailed evidence for customer-selected workloads | Spark/query/table analysis only for approved targets |
| Benefits realization | Compare post-change evidence with an approved baseline | Preserve baseline version and workload normalization |
| Offline | Build reports from customer-provided exports | Never imply that export completeness equals live coverage |

## 5. Scope configuration requirements

Every assessment run SHALL require a versioned scope file containing:

- Customer or engagement identifier.
- Assessment run identifier.
- Azure tenant.
- Included and excluded subscriptions.
- Included and excluded resource groups.
- Databricks account identifier.
- Included and excluded workspaces.
- Included regions.
- Included environments.
- Analysis start and end timestamps.
- Time zone.
- Billing currency.
- Cost basis: actual, amortized, list price, negotiated, or combinations.
- Target business units, teams, products, projects, and cost centers.
- Selected workload deep dives.
- Approved identity and sensitive-data fields.
- Sampling limits.
- Customer-specific detector thresholds.
- Output location and retention.

The toolkit SHALL stop if the analysis window is invalid or if no scope is selected.

The simplified entry point SHALL offer interactive selection of one or more Azure
subscriptions and resource groups, plus equivalent noninteractive array parameters.
Resource-group selections SHALL preserve their subscription association; identical
names in different subscriptions SHALL never silently expand scope. Selection SHALL
discover Databricks workspaces, include their associated managed resource groups,
and preserve the existing Databricks-related reporting boundary. Inaccessible
selections and selections containing no Databricks workspaces SHALL stop before
collection rather than fall back to a broader scope.

The resolved configuration SHALL be saved with the assessment run and used by
default when recreating its consolidated report. Selection SHALL NOT overwrite
the base configuration or transfer SQL Warehouse/deep-dive identifiers to newly
discovered workspaces. A single invocation SHALL select, collect, analyze, and
open the report while retaining SQL auto-start approval controls.

## 6. Collection and aggregation inventory

Every capability in this section is currently absent or incomplete in the existing workshop scripts.

### 6.1 Azure scope and resource inventory

| Requirement ID | Data to collect | Preferred source | Required grain |
|---|---|---|---|
| AZI-001 | Tenant, management group, subscription, resource group, and resource hierarchy | Azure Resource Graph / ARM | Resource |
| AZI-002 | All Azure Databricks workspaces in scope | Azure Resource Graph / ARM | Workspace |
| AZI-003 | Workspace location, SKU, tags, managed resource group, networking, public access, encryption, and provisioning state | ARM | Workspace |
| AZI-004 | Resources in every Databricks managed resource group | Azure Resource Graph | Resource |
| AZI-005 | Storage accounts, disks, network interfaces, public IPs, NAT gateways, firewalls, private endpoints, DNS, monitoring, and security services attributable to Databricks | Azure Resource Graph | Resource |
| AZI-006 | Azure resource tags and tag history where available | ARM, Azure Resource Graph, activity logs | Resource/time |
| AZI-007 | Resource ownership metadata and support contacts | Tags plus customer mapping | Resource |
| AZI-008 | Policy assignments and effective policy state affecting Databricks or related resources | Azure Policy | Scope/resource |
| AZI-009 | Diagnostic settings and telemetry destinations | Azure Monitor / ARM | Resource |
| AZI-010 | Azure quotas relevant to Classic Compute and planned optimization tests | Azure quota CLI | Region/family |

### 6.2 Azure Cost Management

| Requirement ID | Data to collect | Preferred source | Required grain |
|---|---|---|---|
| AZC-001 | Actual cost | Azure Cost Management query/export | Daily resource/meter |
| AZC-002 | Amortized cost | Azure Cost Management query/export | Daily resource/meter |
| AZC-003 | Usage quantity, unit, meter, service, product, and SKU | Azure Cost Management | Daily meter/resource |
| AZC-004 | Subscription, resource group, resource ID, location, and tags | Azure Cost Management | Cost row |
| AZC-005 | Reservation and Savings Plan benefit, coverage, and unused commitment | Cost Management reservation/benefit data | Daily commitment/SKU |
| AZC-006 | Marketplace and supporting service charges related to Databricks | Azure Cost Management | Daily service/resource |
| AZC-007 | Network egress charges, including cross-region, cross-cloud, and OpenSharing-related cost where attributable | Azure Cost Management plus sharing evidence | Daily meter/workload |
| AZC-008 | Storage capacity, transactions, retrieval, and lifecycle charges | Azure Cost Management | Daily account/meter |
| AZC-009 | Log Analytics ingestion and retention cost attributable to Databricks | Azure Cost Management | Daily workspace/meter |
| AZC-010 | Budget, forecast, and variance data | Azure Cost Management | Scope/month |

Collection SHALL support pagination and large exports. It SHALL not assume that every Azure charge has a Databricks workspace identifier.

### 6.3 Databricks account and workspace inventory

| Requirement ID | Data to collect |
|---|---|
| DBI-001 | Account and workspace identifiers, names, URLs, regions, tiers, deployment type, and status |
| DBI-002 | Unity Catalog metastore assignments and workspace catalog bindings |
| DBI-003 | Workspace settings relevant to compute, security, networking, governance, and serverless |
| DBI-004 | Entitlements, groups, service principals, and owner mappings approved for collection |
| DBI-005 | Default and custom workspace tags |
| DBI-006 | Workspace IP access, private connectivity, serverless network connectivity, and egress configuration |
| DBI-007 | Enabled system tables and observed retention/earliest timestamp |
| DBI-008 | Account Console cost dashboard availability and scope |
| DBI-009 | Governance Hub availability and preview/beta status |
| DBI-010 | Workspace/account feature availability that constrains optimization recommendations |

### 6.4 Databricks billing and list prices

The toolkit SHALL collect:

- `system.billing.usage`.
- `system.billing.list_prices`.
- Applicable usage metadata for jobs, job runs, notebooks, pipelines, SQL Warehouses, model serving endpoints, and serverless workloads.
- Custom tags and identity metadata.
- Product features and SKU names.
- Usage start/end times, quantities, units, and billing origins.
- Corrections and restatements.

It SHALL calculate:

- DBU usage by date, workspace, SKU, product, workload, owner, team, and tag.
- List-price cost when list prices are applicable.
- Contract-adjusted cost only when the customer supplies approved contract logic.
- Job cost, serverless cost, model serving cost, SQL cost, and unattributed cost.
- Cost of failed and retried runs.
- Cost trends and anomalies.

### 6.5 Tags, ownership, and attribution

The official guidance recommends organization-wide tag conventions, including business unit, project, and environment. The toolkit SHALL collect and assess:

- Databricks default tags.
- Custom workspace tags.
- Classic cluster and pool tags.
- SQL Warehouse tags.
- Job and pipeline tags where supported.
- Serverless usage-policy/budget-policy tags.
- Azure resource tags.
- Owner, team, business unit, project, environment, product, service, cost center, and data-product identifiers.
- Tag propagation into Databricks billing records.
- Tag propagation into Azure cost rows.
- Missing, invalid, conflicting, renamed, or case-variant tags.
- Material cost without owner or cost center.
- Historical limitation: tags added now do not repair past usage.

The toolkit SHALL produce attribution coverage by both resource count and spend.

### 6.6 Classic Compute inventory and history

Collect for all approved clusters and historical compute:

- Cluster ID, name, source, creator, owner, state, and lifecycle timestamps.
- All-purpose versus job compute.
- Single-node, fixed-size, and autoscaling configuration.
- Driver and worker node types.
- Minimum and maximum workers.
- Runtime version and age.
- Photon setting.
- Data security mode.
- Policy ID and policy compliance.
- Pool usage.
- Spot/on-demand configuration and fallback.
- Auto-termination.
- Custom tags.
- Libraries and init scripts where approved.
- Start, ready, resize, termination, and failure events.
- Node timeline and worker-hour history.
- Startup, active, idle, scale-up, scale-down, and teardown time.
- Cloud-provider stockout, eviction, and quota failures.

Required aggregations:

- Provisioned worker-hours versus active worker-hours.
- Idle duration and estimated idle cost.
- Average and percentile cluster startup time.
- Autoscaling minimum/maximum occupancy.
- Percentage of time at minimum, maximum, and intermediate size.
- All-purpose cost used by scheduled workloads.
- Runtime and Photon adoption by cost.
- GPU usage by workload and evidence of GPU-accelerated libraries.
- Latest-generation versus legacy instance-family use.
- Instance-family fit: general, memory, compute, storage, or GPU optimized.
- Pool idle infrastructure cost. The report SHALL note that idle pool instances avoid DBU charges but still incur Azure infrastructure charges.

### 6.7 Jobs, tasks, pipelines, and run history

Collect:

- Job, task, and pipeline definitions.
- Owner/run-as identity.
- Schedule, trigger, pause state, and concurrency.
- Job compute and existing-cluster references.
- Task dependencies and shared job-cluster reuse.
- Timeouts, retries, retry-on-timeout, and repair runs.
- Run and task start/end time, setup duration, execution duration, cleanup duration, and queue duration.
- Lifecycle/result state and failure category.
- Input/output parameters excluding customer-restricted values.
- Pipeline mode, autoscaling, channel/runtime, target, and event history.
- Continuous versus triggered execution.
- Structured Streaming trigger mode.
- Checkpoint and state-store evidence where approved.

Required aggregations:

- Cost per successful run.
- Failure and retry cost.
- Long-running and high-frequency jobs.
- Schedule overlap and concurrency.
- Full reruns after partial failure.
- Non-interactive workloads using all-purpose compute.
- Tasks that could share job compute to amortize startup.
- Continuous streaming workloads whose freshness requirements may permit `AvailableNow`.
- Always-on compute with low event arrival or low useful processing.

### 6.8 SQL Warehouse inventory and query history

Collect:

- Warehouse ID, name, owner, tags, type, size, serverless status, and Photon.
- Minimum/maximum clusters.
- Autostop and auto-resume.
- Channel and configuration.
- State and cluster-count timeline.
- Query history and query profile identifiers.
- User/service principal, dashboard, alert, notebook, or application origin where available.
- Queue, compile, execute, fetch, and total durations.
- Rows and bytes read/written.
- Spill, cache, pruning, and I/O evidence.
- Query status, errors, cancellation, and retry.
- Query text only when approved; otherwise collect normalized fingerprint and restricted metadata.
- Statement type and query fingerprint.

Required aggregations:

- Warehouse cost and DBUs by hour/day.
- Queries per hour and concurrent queries.
- Queue duration percentiles.
- Execution duration percentiles.
- Cost per query and per dashboard refresh.
- Cost by user/team/dashboard/application.
- Idle and autostop behavior.
- Running cluster count versus query demand.
- Repeated query fingerprints.
- High scan-to-result ratios.
- Spill-heavy queries.
- Serverless Intelligent Workload Management evidence where exposed.
- SQL workloads running on general-purpose Spark compute instead of SQL Warehouses.

### 6.9 Spark execution evidence

Estate-wide Spark metrics may not be available at sufficient detail from a single system table. The toolkit SHALL support two levels:

#### Standard collection

- Job and task duration.
- Compute/runtime configuration.
- Input/output metrics exposed by system tables or job APIs.
- Failure/retry and executor-loss indicators.
- Workload candidates for deep dive.

#### Approved deep-dive collection

For selected job runs, collect Spark event-log or Spark UI equivalent evidence:

- Job, stage, task, executor, and SQL execution identifiers.
- Stage critical path.
- Task duration distribution.
- Input/output records and bytes.
- Shuffle read/write and fetch wait.
- Memory and disk spill.
- Garbage collection time.
- Executor CPU time and utilization.
- Peak executor memory.
- Disk and network I/O.
- Scheduler delay and serialization/deserialization.
- Failed/retried tasks.
- Executor loss.
- Cached RDD/dataframe storage.
- Driver-side gaps and non-Spark duration.
- AQE plan changes.

Required findings:

- Skew and stragglers.
- Excessive shuffle.
- Memory pressure and spill.
- Garbage collection overhead.
- Low CPU with high I/O.
- Driver bottlenecks.
- Excessive partitions or oversized partitions.
- Repeated computation.
- Failure/retry waste.

The toolkit SHALL report insufficient evidence when detailed Spark metrics are unavailable.

### 6.10 Delta, storage format, and data-layout inventory

Collect for approved catalogs/schemas/tables:

- Catalog, schema, table, owner, and table type.
- Storage location only when permitted.
- Format: Delta, Parquet, ORC, JSON, CSV, or other.
- Table size and row count where available.
- File count, average, median, percentile, minimum, and maximum file size.
- Partition columns and partition count.
- Liquid Clustering state and keys.
- ZORDER and `OPTIMIZE` history where observable.
- Table properties, including optimized writes and auto compaction.
- Data-skipping statistics and indexed/statistics columns where available.
- Deletion-vector setting and feature compatibility.
- Merge, update, and delete frequency.
- Write amplification.
- `VACUUM` and retention history.
- Time-travel, clone, streaming, audit, and recovery constraints.
- Access predicates, join predicates, and scan behavior for selected workloads.
- Storage tier and lifecycle settings for external Azure storage.

Required aggregations and detectors:

- Non-Delta data used by material Databricks workloads.
- Small-file conditions.
- Over-partitioned and under-partitioned tables.
- Layout misaligned with common predicates.
- ZORDER candidates.
- Liquid Clustering candidates.
- DFP/data-skipping limitations.
- Merge rewrite amplification and low-shuffle-merge candidates.
- Deletion-vector candidates and compatibility risks.
- Missing or excessive maintenance.
- Unsafe `VACUUM` recommendations.
- Cold data lifecycle opportunities.

The toolkit SHALL follow the official best practice to prefer performance-optimized formats, particularly Delta Lake, while treating conversion as a validated candidate rather than an automatic action.

### 6.11 Code and query-pattern evidence

For customer-approved repositories, notebooks, query plans, or exports, detect:

- Python/Scala UDF use.
- Native function alternatives.
- Driver loops and serial API calls.
- `collect`, `toPandas`, and large driver-side operations.
- Repeated actions and recomputation.
- Full-table reads and writes.
- Lack of incremental or CDC processing.
- Broadcast opportunities and oversized broadcasts.
- Join strategy and ordering.
- Stale/missing table and column statistics.
- Fixed legacy shuffle partition settings.
- Repartition/coalesce misuse.
- Cache/persist use and cleanup.
- Non-selective predicates.
- Expensive or unnecessary sorting.
- GPU configuration without GPU-accelerated code.

Source code collection SHALL be opt-in. If source is restricted, the toolkit SHALL use plans and runtime evidence and lower finding confidence.

### 6.12 Streaming assessment

The official best practices require balancing always-on streaming against triggered incremental processing.

Collect:

- Streaming job/pipeline identity and owner.
- Continuous, processing-time, once, or `AvailableNow` trigger.
- Required freshness SLA.
- Actual event arrival pattern.
- Input rows/bytes per trigger.
- Processing time and idle time.
- State-store size and checkpoint location.
- Backlog and late-data behavior.
- 24/7 infrastructure and DBU cost.

Detect:

- Continuous streaming without a low-latency business requirement.
- Long idle periods.
- Workloads suitable for `AvailableNow`.
- Structured Streaming scale-down limitations.
- Candidates for Lakeflow enhanced autoscaling.

### 6.13 GPU and model-serving assessment

Collect:

- GPU cluster and endpoint configuration.
- GPU type/count and runtime.
- Utilization evidence.
- Installed/used GPU-accelerated libraries where approved.
- Training/inference duration.
- Model serving endpoint scale, throughput, latency, and usage.
- Serverless model-serving cost and idle/scale behavior.

Detect:

- GPU resources used by CPU-only workloads.
- Oversized GPU types.
- Low accelerator utilization.
- Batch inference candidates.
- Model serving scale and cost anomalies.

### 6.14 Pools and spot instances

Collect:

- Pool definitions, node types, minimum idle instances, maximum capacity, and attached clusters.
- Pool instance timelines.
- Azure infrastructure cost for idle pool instances.
- Spot/on-demand mix.
- Driver spot status.
- Evictions, fallback, retries, and delays.
- Workload SLA and fault tolerance.

Detect:

- Pools with idle infrastructure cost exceeding startup benefit.
- Pools with no consumers.
- Driver configured on spot.
- Fault-tolerant workloads that may use spot.
- Critical/stateful workloads where spot risk is unacceptable.

### 6.15 Budgets, alerts, policies, and FinOps operations

Collect:

- Databricks account budgets.
- Budget filters and notification destinations.
- Serverless usage/budget policies and assignments.
- Azure budgets and alerts.
- Compute policy definitions and assignments.
- T-shirt size standards.
- Allowed node types and GPU restrictions.
- Autoscaling and worker-count enforcement.
- Auto-termination enforcement.
- Policy exceptions and expiration.
- Cost dashboards and refresh status.
- Monthly cost-report distribution.
- Cost-audit cadence and action records.
- Tag housekeeping process and audit log.
- FinOps and engineering ownership.

Detect:

- Missing account/workspace/team budgets.
- Budgets without active notifications.
- Serverless usage without attribution policy.
- Policies that allow excessive sizes or GPU use.
- Interactive compute without enforced auto-termination.
- Missing autoscaling controls.
- Missing or stale policy exceptions.
- Tag cleanup with no audit trail.
- No recurring cost audit or accountable action process.

### 6.16 Reservations, Savings Plans, and commitments

Collect:

- Azure Reservations inventory, scope, SKU, region, term, utilization, and coverage.
- Azure Savings Plan commitment, utilization, and coverage.
- Databricks commitment/reserved-capacity information supplied by the customer.
- Current contract rates where approved.
- Stable baseline demand after identified waste.
- Planned Classic-to-serverless migration.
- Forecast growth or decline.

Required analysis:

- Separate consumption reduction from rate optimization.
- Identify stable eligible demand only after right-sizing.
- Model coverage, utilization, break-even, and lock-in.
- Avoid applying customer-paid VM commitments to serverless charges when infrastructure is already included in the serverless DBU.
- Flag underused commitments.
- Record procurement owner and renewal date.

## 7. Best-practice detector catalog

The initial detector catalog SHALL align with the four principles in the official Microsoft guidance.

### 7.1 Choose optimal resources

| Detector | Required evidence | Candidate |
|---|---|---|
| Non-Delta material workload | Table format, workload cost, runtime | Evaluate Delta conversion |
| Scheduled workload on all-purpose compute | Job schedule, cluster source, cost | Move to job compute |
| SQL workload on general Spark compute | Query/workload type, compute source | Evaluate SQL Warehouse |
| Legacy runtime | Runtime version, release age, workload cost | Benchmark supported current/LTS runtime |
| GPU without GPU acceleration | GPU config, libraries, utilization | Move to CPU or prove GPU value |
| Bursty workload on persistent Classic compute | utilization, idle time, eligibility | Evaluate serverless |
| Legacy instance generation | node type, available alternatives | Benchmark newer generation |
| Instance-family mismatch | CPU, memory, spill, cache, workload type | Benchmark suitable family |
| Compute over/undersizing | cores, memory, local disk, demand, SLA | Right-size |
| Missing sizing standard | policies and resource distribution | Create T-shirt size policies |
| Photon opportunity | workload compatibility, runtime, cost | Benchmark Photon price-performance |

### 7.2 Dynamically allocate resources

| Detector | Required evidence | Candidate |
|---|---|---|
| Fixed-size variable workload | node timeline and stage demand | Enable/test autoscaling |
| Ineffective autoscaling bounds | occupancy and scale events | Adjust minimum/maximum |
| Interactive compute without termination | cluster config and idle intervals | Enforce auto-termination |
| Excessive termination interval | idle cost and user SLA | Reduce interval |
| Pool idle cost | pool timeline and Azure VM cost | Reduce idle instances or remove pool |
| Streaming scale-down limitation | trigger and worker timeline | Evaluate Lakeflow enhanced autoscaling |
| Missing compute guardrails | policy coverage | Add policy restrictions |

### 7.3 Monitor and control cost

| Detector | Required evidence | Candidate |
|---|---|---|
| Unowned material cost | billing plus ownership | Assign owner |
| Missing business unit/project/environment tags | tag coverage and cost | Remediate taxonomy prospectively |
| Tag propagation gap | Databricks tags versus Azure/billing rows | Correct propagation/configuration |
| Serverless unattributed usage | usage metadata and policy assignment | Assign usage policy |
| Missing budget | spend scope and budget inventory | Create budget |
| Alert without accountable recipient | notification config | Correct routing/escalation |
| Cost anomaly | time series and forecast | Investigate and assign |
| No recurring audit | operating-process evidence | Establish monthly audit |
| Tag housekeeping gap | stale tags and process | Implement resilient audited cleanup |
| Missing system-table observability | table availability/permissions | Enable/grant access |
| OpenSharing egress cost | sharing and network meters | Review sharing topology/controls |

### 7.4 Design cost-effective workloads

| Detector | Required evidence | Candidate |
|---|---|---|
| Always-on streaming without matching SLA | trigger, event pattern, freshness SLA | Evaluate `AvailableNow` |
| Spot-eligible fault-tolerant workload | retry/checkpoint/SLA evidence | Test spot workers with on-demand driver |
| Driver on spot | cluster config | Move driver to on-demand |
| Full reprocessing | input change rate and reads/writes | Implement incremental/CDC |
| Expensive join/shuffle | plans and Spark metrics | Broadcast/reorder/AQE/layout change |
| UDF bottleneck | plan/code and runtime | Replace with native function |
| Data-layout inefficiency | file/layout/query evidence | OPTIMIZE/clustering/ZORDER candidate |
| Repeated BI queries | fingerprints and frequency | Materialized view/cache/refresh change |

## 8. Common normalized assessment model

The toolkit SHALL produce a versioned common model with at least these entities:

1. `assessment_run`
2. `source_collection`
3. `scope`
4. `azure_resource`
5. `workspace`
6. `owner`
7. `tag`
8. `azure_cost`
9. `databricks_usage`
10. `list_price`
11. `commitment`
12. `compute`
13. `compute_event`
14. `node_timeline`
15. `pool`
16. `job`
17. `task`
18. `job_run`
19. `task_run`
20. `pipeline`
21. `warehouse`
22. `query`
23. `spark_application`
24. `spark_stage`
25. `spark_task_summary`
26. `table`
27. `table_file_summary`
28. `table_operation`
29. `policy`
30. `budget`
31. `finding`
32. `validation_experiment`
33. `benefit_measurement`

Every record SHALL carry:

- Assessment run ID.
- Source system.
- Source identifier.
- Source extraction timestamp.
- Effective start/end timestamps where applicable.
- Customer scope.
- Collection status.
- Quality flags.
- Sensitivity classification.

## 9. Correlation requirements

The toolkit SHALL preserve and use:

- Azure subscription/resource-group/resource IDs.
- Databricks account and workspace IDs.
- Managed resource group IDs.
- Cluster and warehouse IDs.
- Job, task, run, and pipeline IDs.
- Query and statement IDs.
- Notebook IDs/paths when approved.
- User and service-principal identifiers when approved.
- Catalog, schema, and table IDs.
- Tags and ownership mappings.

Correlation SHALL:

- Be versioned and reproducible.
- Use explicit matching rules.
- Report one-to-many, many-to-one, ambiguous, and unmatched records.
- Never force a match to improve apparent attribution coverage.
- Preserve raw source values separately from normalized values.

## 10. Cost-model and reconciliation requirements

The toolkit SHALL implement the following rules:

1. **Classic Compute:** Total workload cost may include Databricks DBUs plus customer-paid Azure VM, disk, and network cost.
2. **Serverless:** Serverless DBU cost includes underlying VM infrastructure. The toolkit SHALL not add a second VM estimate.
3. **Shared Azure resources:** Allocate only through documented customer-approved rules.
4. **Actual versus amortized:** Preserve both and label the selected reporting basis.
5. **List versus contract price:** Preserve each separately.
6. **Corrections:** Respect billing corrections and restatements.
7. **Currency:** Do not aggregate different currencies without a documented conversion source and date.
8. **Tax:** State whether tax is included.
9. **Time:** Normalize billing and telemetry time zones.
10. **Tolerance:** Reconcile against an authoritative billing view within a configurable tolerance.

Required reconciliation outputs:

- Authoritative total.
- Collected total.
- Variance amount and percentage.
- Matched cost.
- Unmatched cost.
- Allocated shared cost.
- Excluded cost.
- Duplicate/double-count prevention checks.

## 11. Telemetry quality and confidence

For each source and finding, calculate:

- Coverage.
- Freshness.
- Completeness.
- Consistency.
- Attribution quality.
- Sample adequacy.
- Source authority.

Confidence levels:

| Level | Meaning |
|---|---|
| High | Authoritative, current, complete, representative, and reproducible |
| Medium | Actionable with a named material limitation |
| Low | Preliminary; requires more evidence before prioritization |
| Insufficient | Do not recommend; create an evidence-gap action |

No detector SHALL return a positive optimization recommendation when its minimum evidence contract is not satisfied.

## 12. Required toolkit outputs

### 12.1 Machine-readable outputs

- `assessment-manifest.json`
- `source-inventory.json`
- `collection-status.json`
- `normalized/*.parquet` or equivalent open format
- `cost-reconciliation.json`
- `telemetry-quality.json`
- `attribution-coverage.json`
- `optimization-candidates.json`
- `backlog-import.json`
- `benefits-baseline.json`
- `errors.json`

### 12.2 Human-readable outputs

- One consolidated `reports/assessment-report.md` containing:
  - Executive summary.
  - Estate topology and scope map.
  - Current-state cost baseline.
  - Top cost drivers and unattributed cost.
  - Compute and right-sizing assessment.
  - SQL Warehouse and query assessment.
  - Job/pipeline assessment.
  - Spark deep-dive evidence.
  - Delta/data-layout assessment.
  - Governance, policy, budget, and FinOps assessment.
  - Commitment-readiness assessment.
  - Telemetry quality and limitations.
  - Prioritized optimization backlog.
  - 30/60/90-day roadmap.
  - Benefits realization.
  - Human validation and sign-off.
- Optional CSV exports for cost drivers, backlog import, and human sign-off.

## 13. Human validation requirements

Automated candidates SHALL require human review before acceptance.

Every human review record SHALL include:

- Reviewer and role.
- Review timestamp.
- Finding ID and evidence links.
- Decision: accept, reject, defer, or needs more evidence.
- Business/SLA context.
- Performance and reliability risk.
- Security/governance impact.
- Validation experiment.
- Owner and approver.
- Rejection or deferral rationale.

The toolkit SHALL support sign-off by:

- Databricks platform owner.
- Workload owner.
- Data engineering or SQL owner.
- FinOps owner.
- Security/governance reviewer where applicable.
- Executive sponsor for commitment or architecture decisions.

## 14. Security and permissions

### 14.1 Azure roles

Minimum expected roles, scoped only to approved assessment scopes:

- Reader.
- Cost Management Reader.
- Monitoring Reader.
- Policy Reader where policy collection is enabled.

Additional billing roles MAY be required for reservation, Savings Plan, or billing-account data.

### 14.2 Databricks permissions

The toolkit SHALL document the least permissions required for:

- Account/workspace inventory.
- System table reads.
- Jobs and run history.
- Cluster/policy/pool reads.
- SQL Warehouse and query-history reads.
- Unity Catalog metadata.
- Audit/system tables.
- Spark event evidence for selected runs.

The toolkit SHALL report missing permission separately from absent data.

### 14.3 Data protection

- Use customer-controlled execution and storage.
- Use managed identity, Azure CLI identity, or approved OAuth flow.
- Do not persist access tokens.
- Redact sensitive query text, notebook paths, identities, table names, and tags according to configuration.
- Encrypt outputs at rest and in transit.
- Define retention and deletion.
- Maintain an access and collection audit log.

## 15. Collector behavior

Each collector SHALL:

- Be idempotent.
- Support pagination.
- Support retry with bounded exponential backoff.
- Respect API limits.
- Use checkpoints for large exports.
- Support incremental collection.
- Emit progress and elapsed time.
- Enforce configurable collection timeouts.
- Support cancellation without corrupting completed partitions.
- Write partial success explicitly.
- Never emit a success-shaped empty dataset after failure.
- Preserve raw responses or hashes when permitted.
- Produce row/item counts.
- Produce start/end timestamps.
- Record exclusions and sampling.

## 16. Testing requirements

### 16.1 Unit tests

- Source-to-model mapping.
- Cost calculation.
- Serverless double-count prevention.
- Tag normalization.
- Correlation.
- Confidence scoring.
- Detector thresholds.
- Pagination.
- Retry and timeout.
- Redaction.
- Schema evolution.

### 16.2 Contract tests

- Azure Cost Management response shapes.
- Azure Resource Graph.
- Databricks system tables.
- Jobs, clusters, warehouses, policies, and query APIs.
- Missing-field and empty-list API behavior.
- Permission denied.
- Throttling.
- Delayed telemetry.

### 16.3 Reconciliation tests

- Actual cost.
- Amortized cost.
- DBU/list-price joins.
- Serverless bundled infrastructure.
- Shared-resource allocation.
- Corrections.
- Currency and date boundary.

### 16.4 Detector tests

Every detector SHALL include:

- Positive case.
- Negative case.
- Boundary case.
- Insufficient-evidence case.
- False-positive exclusion.
- Human-validation example.

### 16.5 End-to-end tests

- Single workspace.
- Multiple workspaces in one subscription.
- Multiple subscriptions.
- Classic-only.
- Serverless-only.
- Mixed Classic/serverless.
- Missing system tables.
- Restricted query text.
- Delayed billing.
- Partial collector failure.
- Large-volume pagination.
- Repeated assessment and benefits comparison.

## 17. Acceptance criteria

The toolkit is acceptable only when:

- It runs read-only against customer scope.
- It inventories all selected workspaces or reports why each could not be inventoried.
- Azure cost reconciles within the agreed tolerance or variance is fully explained.
- Classic and serverless cost are treated according to their billing boundaries.
- Top-cost workspaces, products, jobs, clusters, and SQL Warehouses are ranked where evidence supports them.
- Unattributed cost remains visible.
- Every finding links to evidence and analysis window.
- Every finding includes confidence and limitations.
- Missing data produces an evidence-gap result.
- Official best-practice detectors in Section 7 are implemented or explicitly deferred.
- Machine-readable outputs validate against versioned schemas.
- Human reports can be reproduced from machine-readable outputs.
- No production resource is changed.
- Automated and human validation pass.
- No Azure resource or cost row outside the derived Azure Databricks resource-group boundary appears in normalized assessment data or human reports.
- Duplicate records collected through both selected and managed resource-group paths are removed by canonical Azure resource ID.
- Cost rankings, attribution, and findings use only the configured reporting basis and do not sum Actual and Amortized rows together.

## 18. Recommended implementation structure

```text
assessment/
├── README.md
├── config/
│   ├── assessment-scope.example.json
│   ├── tag-taxonomy.example.json
│   ├── allocation-rules.example.json
│   └── detector-thresholds.example.json
├── collectors/
│   ├── azure-resource-inventory.ps1
│   ├── azure-cost-management.ps1
│   ├── azure-commitments.ps1
│   ├── databricks-account.ps1
│   ├── databricks-billing.sql
│   ├── databricks-compute.sql
│   ├── databricks-jobs.sql
│   ├── databricks-sql.sql
│   ├── databricks-governance.sql
│   ├── delta-inventory.sql
│   └── spark-deep-dive.ps1
├── model/
│   ├── schemas/
│   ├── normalization/
│   └── correlation/
├── detectors/
│   ├── resources/
│   ├── dynamic-allocation/
│   ├── monitoring-governance/
│   └── workload-design/
├── reports/
│   ├── templates/
│   └── render/
├── tests/
│   ├── unit/
│   ├── contract/
│   ├── reconciliation/
│   └── e2e/
└── Collect-CostOptimizationAssessment.ps1
```

The assessment toolkit SHALL remain separate from `infra/`, because `infra/` creates and operates the workshop reference environment while `assessment/` must be read-only against customer estates.

## 19. Implementation phases

These phases describe the original target sequence. The [consolidated post-implementation plan](AzureDatabricksCostOptimizationEndToEndSpecification.md#post-implementation) now records the completed baseline, partial capabilities, dependencies, accountable roles, and exit evidence for the remaining work. Do not infer that all five phases are complete from the existence of generated reports.

### Phase 1: Foundation

- Scope and configuration.
- Run manifest.
- Azure and Databricks authentication.
- Source status and error model.
- Normalized core entities.

### Phase 2: Cost and inventory

- Azure resources and Azure costs.
- Workspace/account inventory.
- Databricks billing/list prices.
- Cost reconciliation.
- Cost-driver reports.

### Phase 3: Workload telemetry

- Compute, jobs, pipelines, SQL Warehouses, and query history.
- Attribution and policy coverage.
- Standard optimization detectors.

### Phase 4: Deep dives

- Spark execution evidence.
- Delta/file-layout evidence.
- Code/query-pattern evidence.
- Streaming, GPU, model serving, pools, spot, and OpenSharing.

### Phase 5: Operating model

- Human review workflow.
- Backlog and roadmap export.
- Benefits realization.
- Recurring assessment and audit cadence.

## 20. Traceability to official best practices

| Microsoft best-practice principle | Toolkit requirements |
|---|---|
| Use performance-optimized formats | Sections 6.10 and 7.1 |
| Use job compute | Sections 6.6, 6.7, and 7.1 |
| Use SQL Warehouses for SQL | Sections 6.8 and 7.1 |
| Use current runtimes | Sections 6.6 and 7.1 |
| Use GPUs only when appropriate | Sections 6.13 and 7.1 |
| Use serverless for suitable workloads | Sections 6.6, 6.8, and 7.1 |
| Select the right instance type and size | Sections 6.6 and 7.1 |
| Use Photon where price-performance improves | Sections 6.6 and 7.1 |
| Use autoscaling | Sections 6.6 and 7.2 |
| Use auto-termination | Sections 6.6 and 7.2 |
| Use compute policies | Sections 6.15 and 7.2 |
| Establish tagging for attribution | Sections 6.5 and 7.3 |
| Set budgets and alerts | Sections 6.15 and 7.3 |
| Monitor account/workspace usage | Sections 6.3, 6.4, and 7.3 |
| Use system billing tables | Sections 6.4 and 7.3 |
| Use Azure Cost Management | Sections 6.2 and 10 |
| Monitor OpenSharing egress | Sections 6.2 and 7.3 |
| Maintain tag housekeeping and audit logs | Sections 6.15 and 7.3 |
| Conduct recurring cost audits | Sections 6.15 and 19 |
| Balance continuous and triggered streaming | Sections 6.12 and 7.4 |
| Use spot for suitable fault-tolerant workloads | Sections 6.14 and 7.4 |

## 21. Source references

- [Microsoft Learn: Best practices for cost optimization](https://learn.microsoft.com/en-us/azure/databricks/lakehouse-architecture/cost-optimization/best-practices)
- [Azure Databricks system tables](https://learn.microsoft.com/en-us/azure/databricks/admin/system-tables/)
- [Monitor costs using system tables](https://learn.microsoft.com/en-us/azure/databricks/admin/usage/system-tables)
- [Azure Databricks account usage reports](https://learn.microsoft.com/en-us/azure/databricks/admin/account-settings/usage)
- [Azure Cost Management cost analysis](https://learn.microsoft.com/en-us/azure/cost-management-billing/costs/quick-acm-cost-analysis)
- [Azure Databricks compute configuration best practices](https://learn.microsoft.com/en-us/azure/databricks/compute/cluster-config-best-practices)
- [Azure Databricks compute policies](https://learn.microsoft.com/en-us/azure/databricks/admin/clusters/policies)
- [Azure Databricks SQL Warehouses](https://learn.microsoft.com/en-us/azure/databricks/compute/sql-warehouse/warehouse-types)
- [Azure Databricks Photon](https://learn.microsoft.com/en-us/azure/databricks/compute/photon)
- [Azure Databricks usage detail tags](https://learn.microsoft.com/en-us/azure/databricks/admin/account-settings/usage-detail-tags)
- [Attribute serverless usage with usage policies](https://learn.microsoft.com/en-us/azure/databricks/admin/usage/budget-policies)
- [Azure Databricks budgets](https://learn.microsoft.com/en-us/azure/databricks/admin/account-settings/budgets)
- [AvailableNow incremental processing](https://learn.microsoft.com/en-us/azure/databricks/structured-streaming/triggers#available-now)

## Appendix A. Implementation status and traceability

### Current post-implementation disposition

The [master specification](AzureDatabricksCostOptimizationEndToEndSpecification.md#traceability) is the current disposition register. The latest recorded assessment validation passed **136 Pester and 40 Python tests (176 total)**. A real picker-to-report run produced one report, saved qualified scope, 76 Azure cost rows, and 15 normalized Azure resource records with zero outside-scope rows. It remained **partial**, with SQL-backed evidence intentionally omitted in that validation.

Implemented additions include the single-command wrapper, one consolidated Markdown report, readiness SQL omission, persisted Run approval, subscription/resource-group picker and explicit arrays, all selected subscription cost scopes, exact group identity, workspace discovery, and snapshot-based report regeneration.

The full detector catalog, detailed Spark/code/streaming/GPU analysis, complete financial allocation/commitment model, all normalized entities, checkpointed collection, and automated cross-run benefits comparison remain partial or deferred. Human approval and measured savings remain separate gates. See the [validation record](assessment/test-results.md) and [remaining-work register](AzureDatabricksCostOptimizationEndToEndSpecification.md#post-implementation).

### Earlier implementation summary

Implementation status was validated on **2026-09-26 UTC**. The operator guide is [assessment/README.md](./assessment/README.md), detailed requirement traceability is in [assessment/docs/validation-and-traceability.md](./assessment/docs/validation-and-traceability.md), and the evidence record is [assessment/test-results.md](./assessment/test-results.md).

The current toolkit is a working **partial implementation** of this target specification:

- Implemented: read-only Azure and Databricks request guards; configuration validation; unique manifests; bounded pagination/retry; Azure inventory, policy, diagnostics, cost, budget/commitment, and quota collection; core Databricks workspace, compute, workload, SQL, Unity Catalog, governance, and selected deep-dive collection; schema 1.0 normalization; conservative correlation/reconciliation; six detectors/evidence gates; deterministic machine outputs, 17 reports, three CSV exports, and human sign-off templates.
- Validated: 46 Pester tests and 27 Python tests (**73 total**) passed; the static read-only scan passed; a live run completed `partial` with no failed collector and no observed compute start or Azure mutation.
- Partial/deferred: the complete 33-entity model, full detector catalog, first-class mode selector, incremental checkpoints, whole-run cancellation/timeouts, full Spark UI/event-log ingestion, code scanning, streaming/GPU/model-serving analysis, contract pricing/shared allocation, automated cross-run benefits comparison, output retention/deletion, and several account/system-table sources.

Requirements in this document remain the target contract. A requirement is not satisfied merely because a report placeholder exists; the implementation matrix names the actual evidence and limitations.
