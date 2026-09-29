# L300 Azure Databricks Cost Optimization Workshop Requirements

> **Consolidated specification:** Use [Azure Databricks Cost Optimization: End-to-End Specification and Post-Implementation Plan](AzureDatabricksCostOptimizationEndToEndSpecification.md) as the single current start-to-finish specification. It combines this workshop design with the implemented lab, assessment toolkit, final report contract, corrections, validation, and post-implementation plan. This document preserves the original granular requirements; a SHALL statement or unchecked acceptance item is not evidence that the capability was delivered.

## Document purpose

This document defines the requirements for an advanced, customer-specific Azure Databricks Cost Optimization Workshop. It is the source specification for creating the workshop deck, hands-on labs, facilitator guide, pre-work questionnaire, reusable assessment toolkit, executive readout, optimization backlog, and post-workshop action plan.

The workshop must help the customer answer three questions with evidence from its own Azure Databricks estate:

1. **Where is cost being generated?**
2. **Why are specific workloads expensive?**
3. **Which changes can reduce cost without unacceptable impact to performance, reliability, security, operability, or scalability?**

The primary content framework is [The Complete Guide to Azure Databricks Cost Optimization](./docs/AzureDatabricksCostOptimization.md). The workshop expands that framework into a repeatable assessment methodology and optimization operating model.

## 1. Requirement conventions

The following terms define requirement priority:

- **MUST / SHALL:** Mandatory for the workshop to meet this specification.
- **SHOULD:** Recommended unless a documented customer constraint justifies exclusion.
- **MAY:** Optional or customer-dependent.

Recommendations produced by the workshop SHALL be treated as optimization candidates until validated against customer telemetry, workload objectives, and controlled test results. The workshop SHALL NOT present theoretical savings as realized savings.

## 2. Workshop positioning and boundaries

### 2.1 Workshop level

| Requirement ID | Requirement |
|---|---|
| POS-001 | The workshop SHALL be delivered at L300 depth for experienced engineering, platform, architecture, analytics, and FinOps teams. |
| POS-002 | The workshop SHALL use the customer's actual estate, telemetry, workload configurations, and cost data as the primary evidence. |
| POS-003 | The workshop SHALL focus on diagnosis, trade-off analysis, validation design, and prioritized action planning rather than product orientation. |
| POS-004 | Every optimization recommendation SHALL identify its source evidence, expected cost mechanism, potential performance or reliability impact, implementation effort, confidence, and validation method. |
| POS-005 | The workshop SHALL distinguish consumption reduction, rate optimization, operational control, and architectural change. |
| POS-006 | The workshop SHALL preserve customer security, networking, compliance, data-governance, and service-level constraints. |

### 2.2 Explicit non-goals

The workshop SHALL NOT allocate core agenda time to:

- Introductory Databricks architecture or workspace navigation.
- Spark, Delta Lake, Unity Catalog, cluster, job, or SQL Warehouse fundamentals.
- Generic demonstrations that are not connected to a customer scenario.
- A complete platform migration or production remediation.
- Automatic modification of compute, jobs, policies, tables, warehouses, or Azure resources.
- Guaranteed savings percentages without a customer baseline and measured validation.
- Security, reliability, or performance reductions solely to achieve a lower bill.

### 2.3 Optimization guardrails

All findings SHALL be evaluated against:

- Business criticality and workload owner priorities.
- Runtime, latency, throughput, freshness, concurrency, and availability objectives.
- Recovery, retry, and failure-tolerance requirements.
- Data correctness and reproducibility.
- Security, privacy, networking, and regulatory controls.
- Peak, seasonal, month-end, and exceptional demand.
- Engineering effort, migration risk, operational complexity, and reversibility.
- Current and projected growth.

## 3. Configurable customer profile

The pre-work questionnaire and final requirements-derived assets SHALL include the following placeholders. Unknown values SHALL be marked `TBD` rather than inferred.

| Profile field | Customer value |
|---|---|
| Customer / business unit | `<CUSTOMER_OR_BUSINESS_UNIT>` |
| Industry and regulatory context | `<INDUSTRY_AND_REGULATIONS>` |
| Executive sponsor | `<EXECUTIVE_SPONSOR>` |
| Technical workshop owner | `<TECHNICAL_OWNER>` |
| FinOps / cost owner | `<FINOPS_OWNER>` |
| Azure tenant and billing scopes in assessment | `<AZURE_SCOPES>` |
| Databricks account(s) and workspace(s) in assessment | `<DATABRICKS_SCOPES>` |
| Regions and data residency constraints | `<REGIONS_AND_RESIDENCY>` |
| Environments | `<DEV_TEST_STAGE_PROD_ETC>` |
| Workspace organization model | `<WORKSPACE_TOPOLOGY>` |
| Primary workload categories | `<DATA_ENGINEERING_SQL_BI_ML_STREAMING_ETC>` |
| Classic Compute footprint | `<CLASSIC_COMPUTE_PROFILE>` |
| Serverless Compute footprint | `<SERVERLESS_PROFILE>` |
| SQL Warehouse footprint | `<SQL_WAREHOUSE_PROFILE>` |
| Monthly Azure Databricks-related spend | `<MONTHLY_SPEND_AND_CURRENCY>` |
| Cost growth or optimization target | `<FINANCIAL_TARGET>` |
| Critical SLAs, SLOs, and business windows | `<SERVICE_OBJECTIVES>` |
| Existing tagging and ownership model | `<TAGGING_AND_OWNERSHIP>` |
| Existing dashboards, alerts, and FinOps cadence | `<OBSERVABILITY_AND_FINOPS>` |
| Planned growth or architecture changes | `<FUTURE_STATE_PLANS>` |
| Known pain points | `<KNOWN_COST_OR_PERFORMANCE_ISSUES>` |
| Selected deep-dive workloads | `<WORKLOADS_FOR_DEEP_DIVE>` |

## 4. Workshop objectives and expected outcomes

### 4.1 Objectives

| Requirement ID | Objective |
|---|---|
| OBJ-001 | Establish a reconciled current-state cost baseline that separates Azure infrastructure cost, DBU usage/cost, and other attributable services without double counting. |
| OBJ-002 | Identify and rank the highest-cost workspaces, SKUs, jobs, clusters, SQL Warehouses, teams, and workloads. |
| OBJ-003 | Explain the technical drivers of high cost using utilization, configuration, execution, query, data-layout, and ownership evidence. |
| OBJ-004 | Evaluate compute suitability and right-sizing across job compute, all-purpose compute, Classic Compute, Serverless Compute, and SQL Warehouses. |
| OBJ-005 | Diagnose selected Spark and SQL workloads to root cause, not merely identify high spend. |
| OBJ-006 | Identify code, pipeline, and Delta optimization candidates that can reduce runtime, scan, shuffle, data movement, reprocessing, and storage overhead. |
| OBJ-007 | Assess cost attribution, tagging, policies, budgets, alerts, dashboards, governance, and FinOps operating practices. |
| OBJ-008 | Define a reusable, read-only assessment method and normalized evidence model for future assessments. |
| OBJ-009 | Produce a prioritized and owned backlog separated into quick wins, engineering changes, and architectural changes. |
| OBJ-010 | Agree a measurable 30/60/90-day roadmap and benefits-realization method. |

### 4.2 Expected customer outcomes

By the end of the workshop, the customer SHALL have:

- A shared, evidence-backed view of total Databricks-related cost and major cost drivers.
- A ranked list of workloads and resources requiring action.
- Root-cause findings for the agreed deep-dive workloads.
- A workload-to-compute suitability matrix.
- A SQL Warehouse efficiency assessment.
- A Spark/code/data optimization assessment.
- A cost attribution and governance gap analysis.
- A documented view of telemetry limitations and finding confidence.
- A prioritized optimization backlog with owners and validation steps.
- A 30/60/90-day roadmap with measurable checkpoints.
- A specification for repeatable assessment automation and benefits tracking.

## 5. Target audience and required skill level

### 5.1 Required participant roles

| Role | Required contribution |
|---|---|
| Databricks platform owner / administrator | Workspace topology, compute policies, system tables, budget policies, networking, governance, and operational constraints. |
| Data engineering lead | Job architecture, pipelines, CDC/incremental patterns, runtime behavior, failures, retries, and code ownership. |
| Spark performance engineer | Spark UI interpretation, partitioning, shuffle, skew, spill, memory, GC, and execution-plan analysis. |
| SQL / BI platform owner | SQL Warehouse configuration, query history, concurrency, queueing, dashboard behavior, and user expectations. |
| Data architecture / Delta owner | Table design, clustering, partitioning, file layout, retention, lifecycle, and data-access patterns. |
| Azure platform / cloud infrastructure owner | Azure compute charges, networking, storage, reservations, Savings Plans, quotas, and policy constraints. |
| FinOps / cost management lead | Billing scopes, cost exports, allocation, showback/chargeback, budgets, forecasts, and benefits realization. |
| Workload owners | Business criticality, SLAs/SLOs, release windows, validation, and acceptance of changes. |
| Security / governance representative | Access, audit, retention, redaction, residency, and change-control requirements. |
| Executive or product sponsor | Priorities, financial goals, organizational blockers, ownership, and roadmap endorsement. |

### 5.2 Required proficiency

Participants SHALL already be able to:

- Navigate and administer relevant Azure Databricks workspaces.
- Interpret Spark jobs, stages, tasks, executors, and query plans.
- Understand cluster and SQL Warehouse configuration and scaling.
- Query Unity Catalog system tables.
- Understand Delta Lake write/read behavior and table maintenance.
- Explain workload SLAs, data dependencies, and release processes.
- Interpret Azure Cost Management or equivalent billing data.

The facilitator SHALL not assume that one participant holds all expertise. The workshop SHALL be designed to bring the required roles together for joint decisions.

## 6. Assumptions and prerequisites

### 6.1 Technical prerequisites

| Requirement ID | Requirement |
|---|---|
| PRE-001 | Unity Catalog SHALL be enabled for system-table-based activities, or an alternative evidence path SHALL be documented. |
| PRE-002 | The customer SHALL provide read-only access to approved cost, configuration, usage, and performance evidence. |
| PRE-003 | The analysis period SHALL normally cover 30-90 days and include representative peak, month-end, or seasonal behavior. |
| PRE-004 | Cost currency, billing scope, time zone, pricing basis, and tax treatment SHALL be documented. |
| PRE-005 | Selected workload owners SHALL provide SLAs/SLOs, execution schedules, business criticality, and known incident context. |
| PRE-006 | Deep-dive workloads SHALL have sufficient job, Spark, SQL, or table evidence to support root-cause analysis. |
| PRE-007 | Any lab workspace SHALL be customer-approved and isolated from production changes. |
| PRE-008 | Production changes SHALL follow the customer's change-management and testing process after the workshop. |

### 6.2 Organizational prerequisites

- An executive sponsor SHALL define the optimization objective and constraints.
- A technical owner SHALL coordinate data collection and participant attendance.
- Workload owners SHALL attend the deep dives and backlog prioritization.
- The customer SHALL agree how potentially sensitive query text, notebook paths, user identities, table names, and tags will be redacted.
- The customer SHALL identify active commitments and procurement constraints before financial optimization is discussed.

### 6.3 Readiness decision

The facilitator SHALL issue one of three readiness states before delivery:

- **Ready:** Minimum evidence is available and selected workloads are analyzable.
- **Ready with limitations:** The workshop can proceed, but named modules or conclusions will have reduced confidence.
- **Not ready:** Critical cost or workload evidence is absent and would make the core assessment misleading.

## 7. Pre-workshop discovery and customer data requirements

### 7.1 Discovery domains

The pre-work questionnaire SHALL cover:

1. Environment and organization.
2. Workspaces, regions, tiers, and network architecture.
3. Workload inventory and business criticality.
4. Compute provisioning and cluster policies.
5. Job and pipeline scheduling.
6. SQL Warehouse and BI usage.
7. Serverless and Classic Compute adoption.
8. Data architecture and storage.
9. Performance monitoring and incident history.
10. Cost management, budgets, commitments, and forecasts.
11. Tagging, ownership, showback, and chargeback.
12. Governance, security, and compliance.
13. Planned growth and architecture changes.

### 7.2 Evidence requirements

| Evidence category | Minimum evidence | Preferred evidence | Purpose |
|---|---|---|---|
| Azure cost | Databricks-related cost by subscription/resource group/service for the analysis window | Cost export with resource IDs, meter, tags, reservation/Savings Plan context, and daily granularity | Establish Azure infrastructure and related-service cost. |
| Databricks billable usage | Usage by workspace, SKU, product, and date | `system.billing.usage` joined to list prices and workload metadata | Establish DBU usage/cost and attribution. |
| Workspace inventory | Workspace names, IDs, regions, environment, owner | Account-level inventory with tags and governance configuration | Define assessment scope. |
| Compute inventory | Cluster and policy configurations | Compute history, node timeline, events, autoscaling bounds, runtime, Photon, tags, pool, and spot settings | Right-size and identify idle or policy gaps. |
| Jobs | Job definitions and recent run history | Job/run/task timeline, retries, failures, cluster references, duration, owner, and schedule | Rank job cost and identify reprocessing or failure waste. |
| SQL Warehouses | Warehouse type, size, min/max clusters, autostop | Query history/profile, queue duration, execution duration, bytes read, spill, cache, user, and dashboard context | Analyze concurrency, scaling, and query efficiency. |
| Spark evidence | Spark UI export/screenshots for selected runs | Event logs or equivalent detailed stage/task/executor metrics | Diagnose shuffle, skew, spill, GC, CPU, memory, I/O, and long stages. |
| Delta/data | Selected table sizes and properties | File counts/sizes, history, clustering/partitioning, maintenance history, scan patterns, and retention settings | Assess layout, maintenance, skipping, and lifecycle. |
| Policies and governance | Existing compute/cluster policies and tag standards | Policy assignments, exceptions, serverless budget policies, audit evidence, and compliance coverage | Assess preventive controls. |
| Ownership | Named owner for selected workloads | Owner/team/cost-center mapping for all material usage | Enable accountability and backlog ownership. |
| Commitments | Known reservations, Savings Plans, or Databricks commitments | Coverage, utilization, term, renewal, and forecast data | Assess rate optimization. |
| Service objectives | SLA/SLO for selected workloads | Historical achievement, peak requirements, RTO/RPO, and business windows | Prevent harmful cost changes. |

### 7.3 Analysis-window requirements

- The workshop SHALL use a documented start and end date.
- The window SHALL include at least one representative business cycle.
- Exceptional events, migrations, incidents, and load tests SHALL be annotated.
- Data with different time zones or aggregation grain SHALL be normalized.
- Comparative periods MAY be included to identify growth, regressions, and seasonality.
- If a 30-90 day window is unavailable, the limitation and confidence impact SHALL be recorded.

### 7.4 Data handling and access

| Requirement ID | Requirement |
|---|---|
| DAT-001 | Collection SHALL use least-privilege, read-only access. |
| DAT-002 | Credentials SHALL remain in customer-approved secret stores and SHALL NOT be embedded in notebooks, exports, or workshop materials. |
| DAT-003 | Customer-identifying and workload-sensitive fields SHALL be redacted when required. |
| DAT-004 | Storage location, encryption, retention, deletion, and export rules SHALL be agreed before collection. |
| DAT-005 | The assessment SHALL record the identity, time, scope, and version of each collection run. |
| DAT-006 | Missing, stale, partial, sampled, or conflicting evidence SHALL be visible in outputs. |
| DAT-007 | The workshop SHALL use synthetic or sanitized fallback data when production evidence cannot be used in a lab. |

### 7.5 Workload deep-dive selection

The customer and facilitator SHALL select three to five representative workloads before the workshop. Selection SHOULD include:

- At least one top-cost workload.
- At least one performance-sensitive workload.
- At least one SQL/BI workload when SQL Warehouses are material.
- At least one ETL or streaming pipeline.
- At least one workload with an attribution, reliability, or ownership concern.

Selection SHALL consider cost concentration, optimization potential, business value, evidence availability, owner participation, and transferability of findings to other workloads.

## 8. Current-state cost and environment assessment

### 8.1 Assessment outputs

The assessment SHALL produce:

- Estate inventory and scope map.
- Daily and monthly cost baseline.
- Cost by workspace, SKU, product, team, owner, environment, and workload where evidence permits.
- Top-cost jobs, clusters, SQL Warehouses, queries, and workload families.
- Cost concentration and Pareto analysis.
- Idle, failed, retry, and non-production cost.
- Utilization and rightsizing opportunities.
- Attribution and ownership coverage.
- Policy and governance coverage.
- Telemetry quality and confidence summary.

### 8.2 Ranking and normalization

Raw spend SHALL be supplemented with unit measures where available:

- Cost per successful job or pipeline run.
- Cost per TB read, written, or processed.
- Cost per table refresh or data product.
- Cost per query or dashboard refresh.
- Cost per active user or team.
- Cost per model execution or endpoint request.
- Cost per business transaction or customer-facing outcome.

Rankings SHALL not combine incomparable workloads without describing the normalization method.

### 8.3 Baseline quality

The baseline SHALL:

- Reconcile to authoritative customer billing data within an agreed tolerance.
- Identify costs that cannot be attributed.
- Avoid double counting Azure and DBU charges.
- Separate list-price estimates from invoiced or amortized cost.
- Identify whether commitment discounts are represented.
- Record currency and tax treatment.
- Explain exclusions.

## 9. Databricks cost model requirements

### 9.1 Total-cost model

The workshop SHALL present the conceptual model:

> **Total Azure Databricks-related cost = Azure infrastructure and related-service cost + Databricks usage/DBU cost**

The facilitator SHALL explain that the applicable billing boundary varies by compute and product. The model SHALL be applied using actual billing evidence rather than assuming every workload exposes separate customer-paid VM charges.

### 9.2 Azure infrastructure and related-service cost

The assessment SHALL consider, where applicable:

- VM and VM scale set compute.
- Managed disks and temporary/local storage implications.
- ADLS and other storage accounts.
- Network egress, NAT Gateway, public IP, private endpoints, and firewall services.
- Log Analytics, monitoring, diagnostic, and security services.
- Supporting services and shared platform costs.
- Azure Reservations and Savings Plan benefits or exclusions.

### 9.3 DBU and Databricks usage cost

The assessment SHALL consider:

- Product and SKU.
- Workspace tier.
- Cluster, warehouse, or Serverless size.
- Runtime duration and scaling behavior.
- Photon.
- Jobs, all-purpose, SQL, streaming/DLT/Lakeflow, model serving, and other material products in customer scope.
- Query concurrency and workload execution pattern.
- Usage attribution to workspace, job, run, warehouse, endpoint, owner, or tag.
- Applicable list price, contract price, or committed-use treatment.

### 9.4 Required cost-analysis views

The workshop materials SHALL include requirements for:

- Cost trend over time.
- Cost by workspace and environment.
- Cost by product/SKU.
- Cost by workload type.
- Cost by job, cluster, SQL Warehouse, and owner where supported.
- Cost by tag and untagged cost.
- Cost of failures and retries.
- Cost of idle or low-utilization compute.
- Cost and runtime before/after a validated change.
- Forecast versus budget.

## 10. Assessment Automation and Aggregation Requirements

The detailed implementation requirements for collection, normalization, reconciliation, detectors, outputs, testing, and human validation are defined in [Azure Databricks Cost Optimization Assessment Toolkit Requirements](./AzureDatabricksAssessmentToolkitRequirements.md).

The implemented toolkit operator guide is [assessment/README.md](./assessment/README.md). Its [implementation traceability](./assessment/docs/validation-and-traceability.md) and [validated test/live-run evidence](./assessment/test-results.md) identify which requirements are implemented, partial, or deferred.

### 10.1 Purpose

A reusable, read-only **Databricks Cost Optimization Assessment Toolkit** SHALL aggregate cost, configuration, utilization, performance, ownership, and governance telemetry from approved Azure and Databricks sources.

The toolkit SHALL:

- Normalize evidence into a common assessment model.
- Identify evidence-backed optimization candidates.
- Record source provenance, telemetry quality, and confidence.
- Generate inputs for the workshop cost baseline, workload deep dives, optimization backlog, and benefits-realization tracking.
- Support repeatable assessments across multiple workspaces and assessment periods.

The toolkit SHALL NOT automatically implement recommendations or modify production resources.

### 10.2 Toolkit operating boundaries

| Requirement ID | Requirement |
|---|---|
| AUT-001 | Collection and analysis SHALL be read-only. |
| AUT-002 | The toolkit SHALL NOT resize, start, stop, terminate, create, delete, or reconfigure Azure or Databricks resources. |
| AUT-003 | The toolkit SHALL NOT execute `OPTIMIZE`, `VACUUM`, table-property changes, policy changes, or workload code changes. |
| AUT-004 | A human reviewer SHALL validate each candidate before it enters an approved implementation backlog. |
| AUT-005 | Production changes SHALL require workload-owner approval, testing, and customer change control. |
| AUT-006 | The toolkit SHALL distinguish observed evidence, inferred candidates, validated opportunities, implemented changes, and realized benefits. |

### 10.3 Collector requirements

Collectors SHALL be modular and configuration-driven. Applicable collectors SHOULD include:

1. Azure Cost Management cost/usage export or query.
2. Azure resource inventory, tags, configuration, and scope hierarchy.
3. Azure commitment coverage and utilization context.
4. Databricks account/workspace inventory.
5. Unity Catalog billing and list-price system tables.
6. Job, task, and run history.
7. Compute configuration, event, and node timeline evidence.
8. SQL Warehouse configuration and query history/profile evidence.
9. Audit, access, policy, budget-policy, tag, and ownership evidence.
10. Spark event/UI evidence for selected workloads.
11. Delta table metadata, history, file statistics, and maintenance evidence.

Each collector SHALL record:

- Source system and endpoint/table.
- Source scope.
- Collection time and requested analysis window.
- Collector version.
- Success, partial success, or failure.
- Rows/items collected and exclusions.
- Paging, sampling, truncation, and freshness information.
- Error details that enable remediation.

### 10.4 Common assessment model

The normalized model SHALL support the following entities and relationships.

| Domain | Required normalized fields |
|---|---|
| Assessment run | Run ID, toolkit version, customer scope, time window, time zone, currency, initiated by, collection status, and manifest URI. |
| Scope | Azure billing scope, subscription, resource group, Databricks account, workspace, region, environment, and inclusion/exclusion status. |
| Ownership | User/service principal, workload owner, technical owner, team, business unit, cost center, product, and escalation contact. |
| Workload | Workload ID/type, job, run, task, pipeline, query, dashboard, warehouse, endpoint, notebook, schedule, and criticality. |
| Compute | Compute ID/type, Classic/Serverless, job/all-purpose, node type, workers, autoscaling bounds, runtime, Photon, policy, pool, spot/on-demand mix, and termination settings. |
| Cost | Azure infrastructure cost, DBU quantity, DBU/list-price cost, invoiced/amortized cost when available, total attributed cost, currency, pricing source, commitment treatment, and allocation method. |
| Utilization | Runtime, idle time, worker hours, CPU, memory, disk, I/O, network, active versus provisioned capacity, and coverage. |
| Performance | Duration, queue time, startup time, stages/tasks, shuffle, skew, spill, GC, retries, failures, bytes read/written, scan selectivity, and throughput. |
| SQL | Warehouse size/type, cluster count, concurrency, queueing, autostop, query duration, rows/bytes scanned, spill, cache, and query fingerprint. |
| Delta/data | Table ID, size, file count/distribution, partitioning, clustering, properties, maintenance history, retention, scan pattern, and write pattern. |
| Governance | Tags, policy assignment/compliance, budget policy, owner coverage, exception, audit coverage, and control status. |
| Evidence | Source reference, collection timestamp, effective timestamp, lineage, freshness, completeness, quality flags, and confidence contribution. |
| Finding | Detector/rule ID and version, observed condition, affected assets, evidence references, baseline, proposed action, benefit mechanism, risk, effort, confidence, validation plan, owner, and lifecycle state. |

### 10.5 Correlation and reconciliation

| Requirement ID | Requirement |
|---|---|
| COR-001 | The toolkit SHALL preserve source identifiers needed to correlate workspace, resource, job, run, compute, warehouse, query, table, owner, and cost evidence. |
| COR-002 | Correlation logic SHALL be documented and versioned. |
| COR-003 | The toolkit SHALL not imply false one-to-one precision when Azure charges and Databricks usage have different billing grain or timing. |
| COR-004 | Assessment totals SHALL be reconciled to authoritative billing views within a customer-agreed tolerance. |
| COR-005 | Unmatched, multiply matched, stale, and conflicting records SHALL be reported. |
| COR-006 | Allocation rules for shared resources SHALL be explicit and reproducible. |
| COR-007 | List-price estimates SHALL be distinguishable from invoiced, negotiated, amortized, or commitment-adjusted cost. |

### 10.6 Telemetry quality and confidence

The toolkit SHALL calculate and retain separate measures for:

- **Coverage:** How much of the scoped estate and time window has evidence.
- **Freshness:** Whether evidence reflects the target period.
- **Completeness:** Whether required fields are populated.
- **Consistency:** Whether sources agree within expected tolerance.
- **Attribution quality:** Whether usage maps to an owner and workload.
- **Sample adequacy:** Whether the observation period captures normal and peak behavior.
- **Source authority:** Whether evidence comes from a billing/system source, operational metric, customer declaration, or inference.

Confidence SHALL be represented using a documented scale such as:

| Confidence | Required interpretation |
|---|---|
| High | Authoritative sources, representative coverage, reproducible correlation, and no material conflict. |
| Medium | Useful evidence with a named coverage, freshness, attribution, or consistency limitation. |
| Low | Partial or inferred evidence; candidate requires additional collection before prioritization. |
| Insufficient | Evidence does not support a recommendation; record the gap instead. |

The toolkit SHALL NOT silently replace missing data with assumptions. Defaults used for calculation SHALL be visible and configurable.

### 10.7 Optimization-candidate contract

Every generated candidate SHALL contain:

- Candidate ID.
- Detector ID and version.
- Category and affected assets.
- Observed condition.
- Evidence references.
- Analysis window.
- Baseline cost and technical metrics.
- Proposed action.
- Expected benefit mechanism.
- Expected performance, reliability, security, and scalability implications.
- Estimated effort and dependencies.
- Confidence and quality limitations.
- Validation experiment and success threshold.
- Required owner and approver.
- Lifecycle state.

Candidate lifecycle states SHALL include:

`observed -> candidate -> validated -> accepted/rejected -> implemented -> measured`

The toolkit SHALL preserve rejected candidates and rejection rationale to avoid repeated, context-free recommendations.

### 10.8 Detector requirements

Detectors SHALL:

- Be versioned, testable, and explainable.
- Use measurable thresholds or comparative evidence.
- Identify required inputs and minimum evidence.
- Return `insufficient evidence` rather than a success-shaped fallback.
- Support customer-specific thresholds.
- Identify false-positive risks and exclusions.
- Produce evidence references and validation steps.

Initial detector families SHOULD include:

- Untagged or unowned material spend.
- Idle or low-utilization compute.
- Missing or ineffective auto-termination.
- Fixed-size or poorly bounded autoscaling.
- All-purpose compute used for scheduled production jobs.
- Runtime or Photon upgrade candidates.
- Spot-eligible fault-tolerant workloads.
- SQL Warehouse queueing, oversizing, undersizing, or ineffective autostop.
- High failure/retry cost.
- Long-running stages, skew, shuffle, spill, or GC.
- UDF or non-native execution candidates.
- Full reprocessing where incremental/CDC patterns may apply.
- Small-file and inefficient layout conditions.
- Missing maintenance or unsafe retention practices.
- Policy, budget, tag, and alert coverage gaps.

### 10.9 Toolkit outputs

The toolkit SHALL generate:

1. Run manifest and source inventory.
2. Collection error and limitation report.
3. Normalized machine-readable assessment dataset.
4. Cost baseline and reconciliation report.
5. Ranked cost-driver datasets.
6. Telemetry quality and attribution coverage report.
7. Workload evidence packs.
8. Optimization-candidate inventory.
9. Governance and policy gap report.
10. Backlog-import dataset.
11. Benefits-realization baseline.
12. Human-readable assessment summary.

Machine-readable outputs SHALL have versioned schemas. Human-readable outputs SHALL link findings back to evidence without exposing restricted fields.

### 10.10 Security and operational requirements

- Use customer-controlled identities, execution environments, and storage.
- Support least-privilege access and managed identity/service principal patterns approved by the customer.
- Keep secrets out of code, logs, exports, and reports.
- Support configurable scope, exclusions, redaction, and retention.
- Support pagination, rate limits, incremental collection, retries, and checkpointing.
- Make partial failure explicit by source and scope.
- Make runs idempotent for the same inputs and analysis window.
- Create audit logs and a reproducible run manifest.
- Version schemas, collectors, correlation logic, and detectors.
- Scale across multiple workspaces without combining incompatible data silently.
- Permit extension for new system tables, workload types, and metrics.

### 10.11 Toolkit validation and acceptance

The toolkit specification SHALL require:

- Source-to-model mapping tests.
- Schema and contract validation.
- Billing reconciliation tests.
- Correlation tests.
- Detector positive, negative, boundary, and insufficient-evidence tests.
- Confidence-scoring tests.
- Redaction and authorization tests.
- Partial-failure and recovery tests.
- Idempotency tests.
- Synthetic fixtures for workshop and development use.
- Customer sign-off on scope, reconciliation tolerance, known limitations, and candidate-versus-realized-savings semantics.

Actual toolkit implementation is a separately estimable downstream workstream unless explicitly commissioned. This workshop requirements document SHALL define the product backlog, data contracts, acceptance criteria, and integration points needed for that implementation.

## 11. Major workshop module requirements

Every module SHALL be facilitated as a customer scenario, not as a generic feature presentation. The facilitator SHALL connect each topic to customer evidence, document assumptions, and record decisions or follow-up evidence needs.

## Module A: Estate discovery, cost model, and cost-driver prioritization

### 1. Objective

Establish a shared and reconciled view of where Azure Databricks-related cost is generated, how Azure infrastructure cost and DBU cost interact, and which workspaces, products, resources, owners, and workloads deserve detailed investigation.

### 2. Topics to cover

- Assessment scope, period, currency, pricing basis, exclusions, and reconciliation tolerance.
- Azure infrastructure and related-service costs versus Databricks DBU/usage costs.
- Differences in billing boundaries for Classic, Serverless, SQL, and other products in scope.
- Product/SKU, workspace, environment, team, owner, and workload attribution.
- Highest-cost jobs, clusters, SQL Warehouses, queries, and pipelines.
- Cost concentration, Pareto analysis, seasonality, anomalies, growth, and forecast.
- Idle cost, failed-run cost, retry cost, and cost without ownership.
- Unit cost and business-relevant normalization.
- List price versus negotiated, invoiced, amortized, or commitment-adjusted cost.

### 3. Customer discovery questions

1. Which billing scopes and Databricks accounts/workspaces are in scope?
2. What financial target or cost-growth concern initiated the assessment?
3. Which workloads generate direct business value or have non-negotiable service objectives?
4. Which cost views are considered authoritative by Finance and FinOps?
5. Are tags, job metadata, or ownership mappings reliable enough for allocation?
6. Which cost increases are expected because of growth, and which are unexplained?
7. Are shared platform costs allocated, and if so, by what rule?
8. Which commitments or contract rates affect the effective price?
9. Which period best represents normal, peak, and exceptional demand?
10. What unit metrics are meaningful to the business?

### 4. Required telemetry or evidence

- Azure Cost Management export/query for the approved scope and time window.
- Databricks billable usage and price evidence.
- Workspace, SKU, product, resource, tag, owner, and workload mappings.
- Job/run, compute, warehouse, and query inventory.
- Budget, forecast, and commitment context.
- Business volume metrics where unit cost is required.
- Toolkit reconciliation, quality, and attribution reports.

### 5. Hands-on activity or analysis

Participants SHALL:

1. Review toolkit scope and reconciliation.
2. Build a cost bridge from total Azure/Databricks spend to major categories.
3. Rank workspaces, SKUs, jobs, compute, warehouses, and owners.
4. Perform a Pareto analysis and identify unallocated cost.
5. Normalize selected workloads using agreed unit metrics.
6. Mark anomalies, exceptional periods, and evidence limitations.
7. Select or confirm the workloads for later deep dives.

### 6. Expected findings

- A small number of workspaces, SKUs, or workloads account for material spend.
- Some high spend is justified by business volume or service requirements.
- Material cost lacks reliable tags or ownership.
- Failures, retries, idle time, or duplicate processing create avoidable cost.
- List-price estimates differ from actual financial treatment.
- Current reporting cannot connect cost to an actionable workload owner.

### 7. Resulting customer deliverable

A **Current-State Cost Baseline and Cost-Driver Map** containing reconciled totals, allocation coverage, top-cost rankings, unit metrics, anomalies, selected deep dives, and documented limitations.

## Module B: Cost observability, attribution, ownership, and governance

### 1. Objective

Evaluate whether the customer can continuously attribute, govern, forecast, and act on Azure Databricks cost after the workshop.

### 2. Topics to cover

- Unity Catalog billing and operational system tables.
- `system.billing.usage`, pricing data, workload metadata, and applicable job/compute/query system tables.
- Account usage reports and governance views.
- Custom tags, default tags, tag inheritance, and serverless attribution.
- Compute/cluster policies and serverless budget policies.
- Required owner, team, product, environment, cost-center, and data-product metadata.
- Showback, chargeback, shared-cost allocation, and exception management.
- Cost dashboards, budgets, alerts, forecasts, anomaly detection, and escalation.
- FinOps cadence, engineering accountability, and policy-as-code opportunities.
- Telemetry quality, lineage, and confidence.

### 3. Customer discovery questions

1. What percentage of material spend has a valid owner and cost center?
2. Which tags are mandatory, and where are they enforced?
3. How are Serverless workloads attributed?
4. Which policies restrict node types, sizes, autoscaling, runtimes, and auto-termination?
5. Who reviews cost, at what cadence, and what actions follow?
6. Are budgets informative only, or do they trigger accountable remediation?
7. How are shared workspaces and shared SQL Warehouses allocated?
8. How are policy exceptions approved and expired?
9. Which cost and performance signals are retained long enough for trend analysis?
10. Can a finding be traced from a dashboard to a workload owner and source evidence?

### 4. Required telemetry or evidence

- System-table availability, schema access, and retention.
- Tag inventory and coverage by cost.
- Owner/team/cost-center mapping.
- Compute/cluster policies, policy assignments, and exceptions.
- Serverless budget policies and assignments.
- Dashboards, budget definitions, alerts, recipients, and escalation records.
- Cost-review cadence, showback/chargeback reports, and action logs.
- Toolkit attribution, governance, and telemetry-quality outputs.

### 5. Hands-on activity or analysis

Participants SHALL:

1. Calculate spend coverage by required attribution fields.
2. Identify material unowned, untagged, or ambiguously allocated usage.
3. Map current controls to lifecycle stages: provision, run, observe, alert, review, remediate.
4. Review sample system-table queries or toolkit outputs for job, warehouse, and Serverless attribution.
5. Define minimum dashboard views and alert thresholds.
6. Design an exception and ownership-escalation workflow.

### 6. Expected findings

- Tags exist but are inconsistent or not enforced.
- Ownership is available at workspace level but not workload level.
- Serverless attribution requires budget-policy or usage-metadata improvements.
- Dashboards show spend but do not connect it to operational action.
- Policies permit unnecessary sizes, runtimes, or idle duration.
- FinOps and engineering teams use different numbers or review cadences.

### 7. Resulting customer deliverable

A **Cost Observability and Governance Control Model** with attribution gaps, required metadata, policy recommendations, dashboard/alert requirements, ownership workflow, exception process, and FinOps cadence.

## Module C: Compute portfolio, utilization, and right-sizing

### 1. Objective

Determine whether each material workload uses an appropriate compute model and configuration while maintaining required performance and reliability.

### 2. Topics to cover

- Job clusters versus all-purpose clusters.
- Classic Compute versus Serverless workload suitability.
- Cluster/node types, worker counts, autoscaling bounds, and driver sizing.
- CPU, memory, I/O, disk, network, and active-versus-provisioned utilization.
- Startup, idle, teardown, and auto-termination behavior.
- Autoscaling lag, oscillation, minimum workers, maximum workers, and workload parallelism.
- Cluster pools where used, including startup benefit and idle infrastructure cost.
- Photon suitability and price-performance validation.
- Runtime age, support status, and performance improvements.
- Spot VM applicability, interruption risk, fallback capacity, retries, and SLA implications.
- Cluster policies, permitted sizes, defaults, and exception handling.
- Workload isolation, concurrency, and noisy-neighbor considerations.

### 3. Customer discovery questions

1. Which scheduled workloads still use all-purpose compute, and why?
2. Which workloads have stable demand versus bursty/on-demand demand?
3. What minimum and maximum workers are configured, and how were they selected?
4. Do clusters reach their maximum, remain near minimum, or oscillate?
5. How much runtime is startup, idle, useful work, retry, and teardown?
6. Which workloads are CPU-bound, memory-bound, I/O-bound, or driver-bound?
7. Which workloads can tolerate interruption and checkpoint/retry safely?
8. Are spot evictions measured, and is on-demand fallback configured?
9. Which workloads cannot use Serverless because of networking, libraries, governance, or feature constraints?
10. Has Photon or a newer runtime been benchmarked on representative data?
11. Are all-purpose clusters shared to reduce sprawl, or oversized to avoid contention?
12. Which policy constraints prevent or enable rightsizing?

### 4. Required telemetry or evidence

- Compute definitions, policies, runtime, Photon, node types, and worker bounds.
- Job-to-compute mappings and all-purpose attachment history.
- Compute events and node timelines.
- CPU, memory, disk, I/O, network, and executor evidence.
- Startup, active, idle, termination, and failure intervals.
- Autoscaling transitions and workload concurrency.
- Spot/on-demand configuration, eviction history, retry behavior, and SLA.
- Classic and Serverless cost/performance evidence for candidate workloads.
- Toolkit compute candidates and confidence.

### 5. Hands-on activity or analysis

Participants SHALL:

1. Segment workloads by scheduled/interactive, stable/bursty, critical/fault-tolerant, and constrained/unconstrained.
2. Calculate active-to-provisioned ratios and idle intervals.
3. Compare worker bounds with observed demand and stage parallelism.
4. Identify scheduled jobs on all-purpose compute.
5. Evaluate Classic versus Serverless using a documented decision matrix.
6. Select candidates for Photon/runtime benchmark.
7. Evaluate spot eligibility using checkpoint, retry, interruption, and SLA evidence.
8. Define a controlled right-sizing test with rollback thresholds.

### 6. Expected findings

- Oversized minimum worker counts or drivers.
- Auto-termination is missing, too long, or ineffective.
- Autoscaling bounds do not reflect observed workload demand.
- Scheduled production jobs use persistent all-purpose compute.
- A Serverless candidate exists, but requires validation of feature, network, or governance constraints.
- Photon or runtime modernization may reduce runtime but needs price-performance measurement.
- Spot is appropriate for some fault-tolerant tasks but unsafe for critical or stateful workloads.
- Policies permit resource shapes inconsistent with workload needs.

### 7. Resulting customer deliverable

A **Workload-to-Compute Decision Matrix and Right-Sizing Plan** with current/target configuration, evidence, test method, guardrails, rollback criteria, and owner for each candidate.

## Module D: SQL Warehouse sizing, concurrency, and query efficiency

### 1. Objective

Determine whether SQL Warehouse type, size, scaling, and query behavior deliver appropriate price-performance for BI and analytical workloads.

### 2. Topics to cover

- Warehouse type and workload suitability.
- Serverless versus non-serverless SQL considerations.
- Warehouse size, minimum/maximum clusters, autoscaling, and autostop.
- Startup, resume, idle, and recycle behavior.
- Query concurrency, queue duration, execution duration, throughput, and peak patterns.
- Query failures, cancellations, retries, and dashboard refresh storms.
- Query profile, scan volume, selectivity, pruning, join strategy, spill, and remote I/O.
- Photon, result/cache behavior, materialized views, and repeated query patterns.
- Workload isolation versus consolidation.
- User experience and latency SLOs.

### 3. Customer discovery questions

1. Which warehouses support dashboards, ad hoc analytics, ETL, or mixed workloads?
2. What latency and concurrency targets apply?
3. When do queues form, and are they caused by concurrency, query inefficiency, or startup?
4. Are warehouses oversized to compensate for inefficient queries?
5. How often do warehouses sit idle before autostop?
6. Are dashboard refresh schedules synchronized unnecessarily?
7. Which queries dominate duration, scan, spill, or aggregate cost?
8. Are workloads isolated for governance or merely because of historical growth?
9. Are users sensitive to cold-start latency?
10. Have Serverless SQL and Photon been benchmarked for representative workloads?

### 4. Required telemetry or evidence

- Warehouse type, size, scaling range, autostop, tags, and owner.
- Query history with queue, compile, execute, and total duration.
- Query profiles for selected expensive queries.
- Concurrency and cluster-count timelines.
- Bytes read, rows read/returned, spill, cache, failures, and cancellations.
- Dashboard schedules and query fingerprints where available.
- SQL workload SLOs and user-impact records.
- Warehouse and query cost allocation.

### 5. Hands-on activity or analysis

Participants SHALL:

1. Plot concurrency, queueing, running clusters, and throughput over time.
2. Separate startup/queue delay from execution inefficiency.
3. Rank queries by duration, frequency, scan, spill, and attributable cost.
4. Inspect query profiles for two or more representative expensive queries.
5. Test sizing hypotheses using concurrency and service objectives.
6. Identify refresh staggering, query rewrite, layout, cache, or materialization candidates.
7. Define an A/B or canary benchmark for warehouse/type/size changes.

### 6. Expected findings

- A warehouse is oversized during normal demand or undersized during peaks.
- Queueing is driven by a few inefficient queries rather than insufficient capacity.
- Autostop is too long, or frequent cold starts conflict with user SLOs.
- Mixed workloads create contention and unpredictable scaling.
- Repeated dashboard queries are candidates for refresh changes or materialization.
- Large scans indicate poor selectivity or data layout.
- Serverless/Photon may improve price-performance for eligible workloads.

### 7. Resulting customer deliverable

A **SQL Warehouse and Query Optimization Plan** with sizing, scaling, autostop, workload isolation, expensive-query actions, benchmark design, and user-experience guardrails.

## Module E: Spark execution and performance-cost diagnosis

### 1. Objective

Use Spark execution evidence to explain why selected jobs are expensive and identify changes that reduce resource-time without masking root causes through larger compute.

### 2. Topics to cover

- Jobs timeline, stages, tasks, executors, and storage views.
- Long-running stages and critical path.
- Input/output volume and scan selectivity.
- Shuffle read/write and exchange behavior.
- Data skew and straggler tasks.
- Memory pressure, spill, caching, and storage levels.
- Garbage collection and executor loss.
- CPU utilization and task efficiency.
- Disk and network I/O.
- Driver bottlenecks, collect operations, and non-Spark work.
- Partition counts, file counts, task size, and AQE behavior.
- Failure, retry, speculation, and recomputation.

### 3. Customer discovery questions

1. Which run is representative: median, p95, peak, failed, or anomalous?
2. Which stage dominates wall-clock time and cost?
3. Are a small number of tasks much slower than the median?
4. Is time spent on CPU, I/O, shuffle, spill, GC, scheduling, or driver work?
5. Do executor losses or retries cause material recomputation?
6. Is cache reuse intentional and effective?
7. Are partition counts fixed from legacy tuning?
8. Does AQE coalesce partitions or mitigate skew?
9. Does input growth explain the regression?
10. Are upstream file layout or downstream write patterns the root cause?

### 4. Required telemetry or evidence

- Spark UI or event evidence for representative runs.
- Job/run/task timing and cluster configuration.
- Stage/task distributions, input/output, shuffle, spill, GC, CPU, and executor metrics.
- Physical plan and AQE changes where available.
- Failure, retry, and executor-loss records.
- Input data size, file counts, and table layout.
- Comparison run or historical baseline where possible.

### 5. Hands-on activity or analysis

Participants SHALL:

1. Identify the critical path and longest stages.
2. Compare median and maximum task duration to quantify skew.
3. Attribute stage time to CPU, I/O, shuffle, spill, GC, or scheduling.
4. Inspect executor utilization and loss.
5. Correlate execution symptoms with code and data layout.
6. Estimate the cost mechanism using runtime and provisioned resources.
7. Define one or more measurable experiments rather than immediately increasing cluster size.

### 6. Expected findings

- Skew creates stragglers and underutilized executors.
- Shuffle or spill dominates despite high provisioned capacity.
- GC indicates memory pressure, object-heavy code, or poor partition sizing.
- Low CPU with high I/O indicates scan, file-layout, or storage bottlenecks.
- Driver-side logic or collection serializes execution.
- Retry or executor loss materially increases cost.
- Legacy partition settings conflict with current data size or AQE.

### 7. Resulting customer deliverable

A **Spark Root-Cause Evidence Pack** for each deep-dive workload, including the critical path, quantified symptoms, likely causes, candidate experiments, success thresholds, and confidence.

## Module F: Code, join, and pipeline optimization

### 1. Objective

Identify code and pipeline patterns that cause unnecessary compute, data movement, serialization, retries, or full reprocessing, and define safe engineering changes.

### 2. Topics to cover

- Incremental processing and change data capture.
- Avoiding unnecessary full-table or full-history reprocessing.
- Idempotency, checkpoints, watermarking, and late-arriving data.
- Join strategy: broadcast hash, shuffle hash, sort-merge, and join ordering.
- AQE and cost-based optimization statistics.
- Native Spark/SQL functions versus Python/Scala UDFs.
- Vectorized/Pandas UDF trade-offs where native functions are unavailable.
- Parallelism, partition control, repartition/coalesce, and file-read settings.
- Driver loops, repeated actions, collect/toPandas, and serial API calls.
- Caching/persistence scope and cleanup.
- Failure/retry behavior and task granularity.
- Benchmarking, correctness checks, and regression thresholds.

### 3. Customer discovery questions

1. Which pipelines re-read unchanged historical data?
2. What source change signals or CDC feeds are available?
3. How are late, duplicate, or corrected records handled?
4. Which joins dominate shuffle, and are table statistics current?
5. Which UDFs appear in expensive stages, and why are they required?
6. Are repeated actions or notebook cells recomputing the same lineage?
7. Are loops issuing many small Spark jobs or external calls?
8. How are failures retried: task, stage, job, or complete pipeline?
9. What data-correctness tests protect an optimization change?
10. Which code is shared across the workload portfolio?

### 4. Required telemetry or evidence

- Source code/notebooks for selected workloads.
- Logical and physical plans.
- Spark evidence from Module E.
- Input/output volume and change-rate evidence.
- Table statistics and join cardinality.
- Job retry/failure history.
- Pipeline schedules, dependencies, and checkpoints.
- Data-quality and regression tests.

### 5. Hands-on activity or analysis

Participants SHALL:

1. Trace the selected workload from source read to final write.
2. Mark full scans, repeated actions, wide transformations, joins, UDFs, and driver operations.
3. Compare processed volume with changed/business-relevant volume.
4. Evaluate join alternatives using actual table sizes and plans.
5. Select native-function or SQL replacements for candidate UDFs.
6. Design an incremental/CDC path where source semantics permit it.
7. Define a before/after benchmark covering correctness, runtime, cost, and reliability.

### 6. Expected findings

- Full reprocessing is used despite a small daily change rate.
- A non-selective join or stale statistics produces excessive shuffle.
- UDFs prevent optimizer improvements or add serialization overhead.
- Repartitioning creates unnecessary exchanges or tiny tasks.
- Repeated actions recompute the same lineage.
- Failure handling reruns successful work.
- Incremental design is possible but requires state, data-quality, or replay controls.

### 7. Resulting customer deliverable

A **Code and Pipeline Engineering Change Set** with code-level candidates, expected mechanism, dependencies, correctness tests, benchmark plan, rollout strategy, and rollback criteria.

## Module G: Delta and data-layout optimization

### 1. Objective

Determine whether table design, file layout, clustering, maintenance, and retention support efficient reads and writes for the customer's actual access patterns.

### 2. Topics to cover

- File size distribution and small-file conditions.
- Optimized writes, auto compaction, and target file size.
- `OPTIMIZE` scheduling and cost-benefit.
- Liquid Clustering suitability and key selection.
- ZORDER for existing eligible designs and access patterns.
- Partition design and over/under-partitioning.
- Data skipping and statistics.
- Dynamic File Pruning.
- Low-shuffle merge.
- Deletion vectors.
- Merge/upsert and CDC write patterns.
- `VACUUM`, retention, time travel, streaming, shallow clones, and recovery constraints.
- Lifecycle and storage-tier considerations.
- Migration and compatibility constraints.

### 3. Customer discovery questions

1. Which tables dominate bytes scanned, files opened, write amplification, or maintenance cost?
2. What are the common filter, join, merge, and update predicates?
3. How large are files, and how does distribution vary by partition?
4. Is current partitioning aligned with access patterns and cardinality?
5. Are ZORDER and Liquid Clustering being combined or migrated appropriately?
6. How frequently is `OPTIMIZE` run, and is its benefit measured?
7. Are merge operations rewriting large unaffected regions?
8. Are deletion vectors and low-shuffle merge available and appropriate?
9. What retention, audit, recovery, clone, and streaming dependencies constrain `VACUUM`?
10. Is old or cold data retained in an unnecessarily expensive tier?

### 4. Required telemetry or evidence

- Table metadata, properties, size, row count where available, and history.
- File counts and size distribution.
- Partition or clustering definitions.
- Query predicates and scan metrics.
- Merge/update/delete history and write volumes.
- `OPTIMIZE` and `VACUUM` history.
- Runtime/feature compatibility.
- Retention, recovery, streaming, and compliance requirements.

### 5. Hands-on activity or analysis

Participants SHALL:

1. Select high-impact tables using scan, write, and cost evidence.
2. Profile file counts/sizes and data layout.
3. Compare common predicates with partition/clustering keys.
4. Evaluate Liquid Clustering, ZORDER, or no-layout-change options.
5. Identify DFP and data-skipping opportunities.
6. Review merge write amplification and deletion-vector/low-shuffle options.
7. Validate `VACUUM` safety against retention and dependent consumers.
8. Define a benchmark and maintenance-cost measurement.

### 6. Expected findings

- Small files increase listing, scheduling, and scan overhead.
- Partitioning reflects ingestion rather than query access.
- ZORDER is applied without measured benefit or to unsuitable columns.
- Liquid Clustering is a candidate for new or evolving access patterns.
- Merge predicates or layout cause excessive rewriting.
- Data skipping/DFP is limited by data layout or query predicates.
- `VACUUM` is absent, overly conservative, or unsafe without dependency review.
- Maintenance cost is not compared with downstream query savings.

### 7. Resulting customer deliverable

A **Table-Level Data Optimization Plan** listing candidate tables, current evidence, target layout or maintenance change, compatibility constraints, benchmark method, retention safety checks, and owner.

## Module H: Financial optimization, Reservations, and commitment strategy

### 1. Objective

Evaluate rate-optimization opportunities only after workload demand and architecture are understood, and prevent commitments from masking avoidable consumption.

### 2. Topics to cover

- Consumption optimization versus rate optimization.
- Stable baseline versus variable/bursty demand.
- Applicable Azure Reservations for customer-paid infrastructure.
- Azure Savings Plan applicability and flexibility.
- Databricks reserved capacity/commit constructs where applicable.
- Coverage, utilization, term, break-even, growth, and renewal.
- Serverless and Classic billing differences.
- Procurement, cancellation/exchange, and accounting considerations.
- Risk of committing before rightsizing or migration.
- Combining baseline commitments with flexible coverage where valid.

### 3. Customer discovery questions

1. Which costs are eligible for each commitment mechanism?
2. What portion of demand is stable after removing waste and planned migrations?
3. What commitments already exist, and what are their utilization and coverage?
4. Are workloads expected to move between Classic and Serverless?
5. Are region, VM family, term, or contract constraints material?
6. What forecast and growth assumptions have been approved?
7. Who owns procurement and commitment decisions?
8. What break-even and risk criteria does Finance require?

### 4. Required telemetry or evidence

- Historical and forecast usage.
- Azure reservation/Savings Plan coverage and utilization.
- Databricks commitment/contract information where approved.
- Rightsizing and migration roadmap.
- Eligible service/SKU mapping.
- Procurement and accounting constraints.
- Baseline versus peak-demand decomposition.

### 5. Hands-on activity or analysis

Participants SHALL:

1. Remove or separately model identified avoidable consumption.
2. Identify stable eligible baseline demand.
3. Compare commitment options by coverage, utilization, flexibility, and risk.
4. Stress-test growth, decline, migration, and region-change scenarios.
5. Define decision gates and owners.

### 6. Expected findings

- Existing commitments are underutilized or poorly aligned.
- Stable baseline exists, but only after rightsizing.
- Planned Serverless migration makes some infrastructure commitments risky.
- Savings Plan flexibility may be more valuable than maximum discount.
- Databricks and Azure commitment models are being conflated.
- Procurement decisions lack a recurring usage review.

### 7. Resulting customer deliverable

A **Commitment Readiness and Rate-Optimization Assessment** with eligible baseline, scenarios, prerequisites, exclusions, risks, decision owner, and review cadence.

## Module I: Customer workload deep dives, prioritization, and operating model

### 1. Objective

Synthesize cost, compute, SQL, Spark, code, data, governance, and financial evidence into owned actions and a repeatable optimization operating model.

### 2. Topics to cover

- Three to five customer-selected workload deep dives.
- Evidence triangulation and confidence.
- Cost-performance-reliability trade-offs.
- Quick wins, engineering changes, and architectural changes.
- Impact, effort, risk, confidence, reversibility, and dependency scoring.
- Experiment design and benefits realization.
- 30/60/90-day sequencing.
- Owners, approvals, governance cadence, and reporting.
- Reassessment and toolkit rerun cadence.

### 3. Customer discovery questions

1. Which findings have enough evidence for immediate controlled validation?
2. Which actions depend on better attribution or telemetry?
3. Which changes are reversible and low risk?
4. Which require code release, data migration, architecture review, or procurement?
5. What performance and reliability thresholds must not regress?
6. Who owns each action and who approves production rollout?
7. How will benefit be measured and sustained?
8. How often should the assessment be rerun?
9. What governance forum will resolve blocked or cross-team actions?

### 4. Required telemetry or evidence

- Outputs from Modules A-H.
- Toolkit candidate inventory and evidence packs.
- Workload owner input and service objectives.
- Engineering capacity and release calendars.
- Architecture, security, and procurement dependencies.
- Baseline and target metrics.

### 5. Hands-on activity or analysis

Participants SHALL:

1. Review each candidate's evidence, quality, and confidence.
2. Reject, defer, validate, or accept candidates with rationale.
3. Score accepted candidates using the agreed prioritization model.
4. Assign category, owner, approver, dependencies, and target metric.
5. Sequence work into 30/60/90-day horizons.
6. Define toolkit reruns and before/after measurement.
7. Agree governance and executive reporting cadence.

### 6. Expected findings

- Several configuration or ownership quick wins can proceed rapidly.
- High-value engineering candidates require controlled benchmarks.
- Architectural changes have larger potential but depend on platform or governance work.
- Some candidates are rejected because risk or effort exceeds likely benefit.
- Telemetry improvements are prerequisites for credible savings measurement.
- Cross-team ownership is the primary blocker for some opportunities.

### 7. Resulting customer deliverable

A **Prioritized Cost Optimization Backlog and 30/60/90-Day Roadmap** with evidence, confidence, category, owner, dependencies, validation, target metrics, and governance cadence.

## 12. Advanced hands-on exercise requirements

### 12.1 General lab requirements

| Requirement ID | Requirement |
|---|---|
| LAB-001 | Labs SHALL use customer evidence or toolkit-generated evidence packs whenever approved and available. |
| LAB-002 | A sanitized synthetic dataset SHALL be available as a fallback and SHALL preserve the analytical complexity of the exercise. |
| LAB-003 | Every lab SHALL define purpose, prerequisites, inputs, permissions, setup, participant tasks, expected outputs, validation criteria, cleanup, and facilitator troubleshooting. |
| LAB-004 | Labs SHALL be read-only unless a customer-approved isolated lab explicitly permits controlled experiments. |
| LAB-005 | Production resources SHALL NOT be modified during a workshop lab. |
| LAB-006 | Each lab SHALL require participants to assess evidence quality and confidence before accepting a finding. |
| LAB-007 | Each optimization lab SHALL produce a measurable validation plan, not an unsupported savings claim. |
| LAB-008 | Lab outputs SHALL feed the customer backlog and roadmap. |

### 12.2 Exercise 1: Cost attribution and top-cost-driver analysis

**Scenario:** Finance reports accelerating Databricks cost, but platform teams cannot identify which workloads and owners are responsible.

**Inputs:**

- Normalized Azure cost and Databricks usage datasets.
- Workspace, SKU, job, compute, warehouse, owner, and tag mappings.
- Reconciliation and telemetry-quality reports.

**Participant tasks:**

1. Confirm assessment scope and reconciliation tolerance.
2. Rank cost by workspace, SKU, workload, and owner.
3. Quantify unallocated or low-confidence cost.
4. Calculate a unit metric for one workload.
5. Select three high-priority investigation targets.

**Expected outputs:**

- Top-cost-driver table.
- Attribution coverage metric.
- Cost anomalies and evidence limitations.
- Deep-dive shortlist.

**Validation criteria:**

- Totals reconcile within the agreed tolerance.
- Rankings link to source evidence.
- List-price and actual-cost measures are not mixed.
- Unallocated cost remains visible.

### 12.3 Exercise 2: Cluster utilization and right-sizing

**Scenario:** A scheduled job meets its SLA but uses persistent or oversized compute.

**Inputs:**

- Cluster configuration and policy.
- Node timeline and utilization.
- Job/run duration, failures, and retries.
- Service objectives.

**Participant tasks:**

1. Separate startup, useful work, idle, retry, and teardown.
2. Compare provisioned workers with observed active demand.
3. Review autoscaling bounds and auto-termination.
4. Evaluate job compute versus all-purpose compute.
5. Evaluate Classic versus Serverless suitability.
6. Define a right-sizing experiment and rollback conditions.

**Expected outputs:**

- Current/target compute hypothesis.
- Risk and constraint list.
- Benchmark and rollback plan.

**Validation criteria:**

- Recommendation accounts for peak demand.
- SLA and reliability thresholds are explicit.
- Spot or Serverless is not recommended without eligibility evidence.

### 12.4 Exercise 3: SQL Warehouse concurrency and expensive-query analysis

**Scenario:** BI users experience intermittent queueing while warehouse cost remains high.

**Inputs:**

- Warehouse configuration.
- Concurrency and cluster-count timeline.
- Query history and selected query profiles.
- Dashboard refresh schedule.

**Participant tasks:**

1. Correlate queues, concurrency, scaling, and query duration.
2. Separate capacity shortage from query inefficiency.
3. Rank query fingerprints by frequency, duration, scan, spill, and cost.
4. Propose sizing, scaling, autostop, scheduling, or query changes.
5. Define a benchmark that includes user latency.

**Expected outputs:**

- Queueing root cause.
- Warehouse and query candidate list.
- A/B benchmark design.

**Validation criteria:**

- Recommendation considers concurrency and query efficiency together.
- Cold-start and user-experience implications are documented.

### 12.5 Exercise 4: Spark UI root-cause analysis

**Scenario:** A high-cost pipeline has a long p95 runtime and engineering proposes a larger cluster.

**Inputs:**

- Representative Spark UI/event evidence.
- Job and cluster configuration.
- Input size, file layout, and historical runtime.

**Participant tasks:**

1. Identify the critical path.
2. Quantify skew using task-duration distribution.
3. Analyze shuffle, spill, GC, CPU, memory, and I/O.
4. Determine whether the bottleneck is code, data layout, compute, or failure/retry.
5. Define experiments in priority order.

**Expected outputs:**

- Root-cause evidence pack.
- Experiment sequence.
- Success and rollback thresholds.

**Validation criteria:**

- A larger cluster is not accepted as the default remedy.
- Findings cite stages/tasks/executors and relevant metrics.

### 12.6 Exercise 5: Code and incremental-processing design

**Scenario:** A pipeline repeatedly processes a large historical table despite a small change rate.

**Inputs:**

- Pipeline code and physical plan.
- Input/change volumes.
- Source change semantics.
- Checkpoint, retry, and data-quality requirements.

**Participant tasks:**

1. Identify full scans and repeated work.
2. Evaluate CDC/incremental patterns.
3. Review joins, UDFs, actions, and partition changes.
4. Design correctness and replay controls.
5. Define a before/after benchmark.

**Expected outputs:**

- Engineering change proposal.
- Correctness, replay, and test plan.
- Runtime/cost measurement plan.

### 12.7 Exercise 6: Delta layout and maintenance assessment

**Scenario:** Queries scan too much data and merge operations rewrite excessive files.

**Inputs:**

- Table metadata and history.
- File count/size distribution.
- Query predicates and scan metrics.
- Merge/update patterns.
- Retention constraints.

**Participant tasks:**

1. Diagnose small files and layout alignment.
2. Compare Liquid Clustering, ZORDER, partitioning, and no-change options.
3. Evaluate `OPTIMIZE`, DFP, deletion vectors, and low-shuffle merge.
4. Review `VACUUM` safety.
5. Define a table benchmark and maintenance-cost comparison.

**Expected outputs:**

- Table-level optimization candidate.
- Compatibility and retention checklist.
- Benchmark and rollout plan.

### 12.8 Exercise 7: Candidate validation and roadmap construction

**Scenario:** The assessment produces more candidates than the customer can execute.

**Inputs:**

- Toolkit candidate inventory.
- Evidence and confidence reports.
- Engineering capacity and release constraints.

**Participant tasks:**

1. Validate evidence and confidence.
2. Reject or defer unsupported candidates.
3. Score accepted candidates.
4. Classify them as quick win, engineering change, or architectural change.
5. Assign owners and dependencies.
6. Place them in the 30/60/90-day roadmap.

**Expected outputs:**

- Approved prioritized backlog.
- Roadmap and benefits-realization plan.

## 13. Recommended delivery format and agenda

### 13.1 Recommendation

The recommended format is a **two-day workshop**.

This format is required to preserve:

- Customer-specific cost baseline review.
- Cross-functional discovery and decision-making.
- Multiple hands-on technical analyses.
- Spark, SQL, code, and Delta deep dives.
- Evidence validation and confidence review.
- Collaborative prioritization and roadmap ownership.

A single full day or two half-days MAY be used only when scope is reduced. A compressed format SHALL move detailed workload analysis, one or more labs, and backlog refinement into pre-work or follow-up sessions. The workshop SHALL not claim equivalent outcomes if those activities are removed.

### 13.2 Required pre-work outside the two workshop days

- Kickoff and scope confirmation.
- Customer profile and discovery questionnaire.
- Access and data-handling approval.
- Toolkit collection or manual evidence preparation.
- Billing reconciliation and telemetry-quality review.
- Selection of three to five deep-dive workloads.
- Facilitator preparation of evidence packs.
- Participant readiness confirmation.

### 13.3 Proposed two-day agenda

Times are illustrative and SHALL be adjusted to customer time zone and break requirements without removing required outcomes.

#### Day 1: Cost baseline, governance, compute, and SQL

| Time | Session | Activities | Output |
|---|---|---|---|
| 09:00-09:30 | Executive and technical alignment | Confirm objectives, scope, guardrails, service objectives, and success measures. | Agreed workshop decision frame. |
| 09:30-10:30 | Module A: Cost model and baseline | Review reconciliation, total-cost model, top workspaces/SKUs/workloads, unit costs, and anomalies. | Validated baseline and deep-dive priorities. |
| 10:30-10:45 | Break |  |  |
| 10:45-12:00 | Module B: Observability and governance | Analyze system-table coverage, attribution, tags, owners, policies, budgets, dashboards, and alerts. | Governance and attribution gap list. |
| 12:00-13:00 | Lunch |  |  |
| 13:00-14:45 | Module C + Exercise 2: Compute portfolio | Analyze job/all-purpose, Classic/Serverless, right-sizing, autoscaling, auto-termination, Photon/runtime, and spot suitability. | Compute decision matrix and experiments. |
| 14:45-15:00 | Break |  |  |
| 15:00-16:30 | Module D + Exercise 3: SQL Warehouses | Analyze sizing, concurrency, queueing, scaling, autostop, Photon, and expensive queries. | SQL optimization plan. |
| 16:30-17:00 | Day 1 synthesis | Confirm findings, evidence gaps, decisions, and Day 2 focus. | Day 1 findings register. |

#### Day 2: Spark, code, data, deep dives, and roadmap

| Time | Session | Activities | Output |
|---|---|---|---|
| 09:00-09:15 | Day 1 recap | Resolve overnight evidence questions and confirm deep-dive sequence. | Updated issue list. |
| 09:15-10:45 | Module E + Exercise 4: Spark diagnosis | Analyze long stages, shuffle, skew, spill, GC, CPU, memory, I/O, and retries. | Spark root-cause evidence pack. |
| 10:45-11:00 | Break |  |  |
| 11:00-12:00 | Module F + Exercise 5: Code/pipeline | Analyze joins, UDFs, incremental/CDC design, parallelism, and reprocessing. | Engineering change candidates. |
| 12:00-13:00 | Lunch |  |  |
| 13:00-14:00 | Module G + Exercise 6: Delta/data | Analyze file size, layout, OPTIMIZE, Liquid Clustering, ZORDER, DFP, deletion vectors, merge, and VACUUM. | Table-level optimization plan. |
| 14:00-14:30 | Module H: Financial optimization | Review eligible stable baseline, Reservations, Savings Plans, and Databricks commitments. | Commitment-readiness findings. |
| 14:30-14:45 | Break |  |  |
| 14:45-16:15 | Module I + Exercise 7: Prioritization | Validate candidates, score impact/effort/risk/confidence, assign owners, and sequence actions. | Prioritized backlog and roadmap. |
| 16:15-17:00 | Executive readout and close | Review decisions, 30/60/90-day plan, measures, risks, and governance cadence. | Agreed action plan and sponsor decisions. |

### 13.4 Post-workshop activities

For the implemented solution's completed work, remaining capabilities, owners, dependencies, and acceptance evidence, use the [consolidated post-implementation plan](AzureDatabricksCostOptimizationEndToEndSpecification.md#post-implementation). The activities below remain the customer workshop follow-through requirements.

- Finalize evidence references and action owners.
- Publish the workshop deliverables.
- Resolve open evidence gaps.
- Hold a technical checkpoint after initial experiments.
- Hold an executive benefits review at the agreed roadmap cadence.
- Rerun the assessment toolkit after validated changes.

## 14. Prioritized optimization backlog requirements

### 14.1 Required backlog fields

| Field | Requirement |
|---|---|
| Backlog ID | Stable unique identifier. |
| Finding / candidate | Concise evidence-backed problem statement. |
| Category | Quick win, engineering change, or architectural change. |
| Domain | Cost, compute, SQL, Spark, code, Delta/data, governance, or commitment. |
| Affected assets | Workspace/job/cluster/warehouse/query/table/owner identifiers. |
| Evidence | Source references and analysis window. |
| Telemetry quality | Coverage, freshness, completeness, consistency, and attribution quality. |
| Confidence | High, medium, low, or insufficient with rationale. |
| Current baseline | Cost and relevant technical metrics. |
| Proposed action | Specific action to validate or implement. |
| Benefit mechanism | How the action is expected to reduce cost or improve unit economics. |
| Performance/reliability impact | Expected positive and negative implications. |
| Security/governance impact | Required review or control changes. |
| Effort | Agreed relative estimate. |
| Risk | Agreed relative risk and rollback complexity. |
| Dependencies | Technical, organizational, procurement, or evidence prerequisites. |
| Validation | Experiment, comparison method, success threshold, and rollback threshold. |
| Owner / approver | Named accountable roles. |
| Target horizon | 30, 60, 90 days, or later. |
| Lifecycle state | Observed, candidate, validated, accepted/rejected, implemented, or measured. |
| Realized result | Measured cost and technical outcome after implementation. |

### 14.2 Classification

#### Quick wins

Changes that are low risk, reversible, and require limited engineering effort, such as:

- Correcting missing or excessive auto-termination.
- Updating policy defaults and permitted ranges.
- Removing obsolete compute after owner confirmation.
- Adding required tags and owners.
- Staggering avoidably synchronized dashboard refreshes.
- Correcting budget/alert routing.

Quick wins SHALL still have validation and change control.

#### Engineering changes

Changes requiring code, query, pipeline, or table testing, such as:

- Join or query rewrites.
- UDF replacement.
- Incremental/CDC conversion.
- Partition or parallelism changes.
- Delta layout and maintenance changes.
- Runtime or Photon benchmark and rollout.

#### Architectural changes

Changes requiring broader design and migration decisions, such as:

- Classic-to-Serverless migration.
- Workspace or workload isolation changes.
- SQL Warehouse consolidation or separation.
- Major table-layout migration.
- New cost allocation and governance operating model.
- Commitment strategy changes tied to platform direction.

### 14.3 Prioritization model

Each candidate SHALL be scored against:

- Cost or unit-cost impact.
- Performance or reliability benefit.
- Strategic/customer value.
- Evidence confidence.
- Engineering effort.
- Operational and migration risk.
- Reversibility.
- Time to validate.
- Dependencies and organizational complexity.

The scoring formula SHALL be documented. High estimated savings SHALL not outweigh low confidence or unacceptable reliability risk without additional validation.

## 15. 30/60/90-day roadmap requirements

### First 30 days: establish control and validate quick wins

- Close critical ownership and tagging gaps.
- Finalize baseline and evidence gaps.
- Implement approved low-risk policy/configuration changes.
- Run controlled rightsizing, Photon/runtime, SQL, and query experiments.
- Establish dashboard, budget, alert, and review cadence.
- Confirm benefits measurement and backlog governance.

### Days 31-60: execute engineering optimizations

- Implement validated code, join, UDF, incremental, and retry improvements.
- Test selected Delta layout and maintenance changes.
- Adjust SQL Warehouse sizing/scaling based on benchmarks.
- Expand compute changes to similar workloads after successful pilots.
- Improve toolkit collectors, mappings, and confidence where evidence was weak.

### Days 61-90: progress architecture and operating model

- Execute approved Serverless, compute-isolation, or major data-layout migrations.
- Make commitment decisions using post-rightsizing baseline demand.
- Institutionalize showback/chargeback and policy exception management.
- Rerun the assessment toolkit.
- Measure realized benefits and identify regressions.
- Refresh backlog and next-quarter roadmap.

Every roadmap item SHALL have an owner, approver, target date, dependency, success metric, and validation status.

## 16. Workshop deliverables

| Deliverable | Required content |
|---|---|
| Customer profile and discovery record | Scope, estate, stakeholders, constraints, goals, service objectives, and selected workloads. |
| Evidence inventory | Source, owner, access, analysis window, collection status, retention, sensitivity, and limitations. |
| Toolkit requirements package | Collector requirements, normalized model, correlation, confidence, detector contract, output schemas, security, operations, and acceptance tests. |
| Toolkit run manifest | Run scope, versions, timestamps, collection status, exclusions, and errors. |
| Telemetry quality report | Coverage, freshness, completeness, consistency, attribution, sample adequacy, and source authority. |
| Current-state cost baseline | Reconciled Azure/DBU cost, rankings, trends, unit metrics, anomalies, and exclusions. |
| Cost-driver map | Highest-cost workspaces, jobs, clusters, warehouses, queries, workloads, owners, and unallocated cost. |
| Compute assessment | Utilization, right-sizing, autoscaling, auto-termination, job/all-purpose, Classic/Serverless, Photon/runtime, and spot findings. |
| SQL assessment | Warehouse sizing, concurrency, queueing, scaling, autostop, and query findings. |
| Workload evidence packs | Spark/code/data root cause, evidence, candidate actions, trade-offs, and validation plans. |
| Governance assessment | Tags, owners, policies, budget policies, dashboards, alerts, FinOps cadence, and gaps. |
| Commitment assessment | Eligible baseline, coverage/utilization, options, risks, and decision gates. |
| Optimization backlog | Prioritized candidates with evidence, confidence, category, owner, and validation. |
| 30/60/90-day roadmap | Sequenced actions, dependencies, owners, approvals, and checkpoints. |
| Benefits-realization plan | Baselines, target metrics, comparison method, reporting cadence, and realized-results fields. |
| Executive readout | Decisions, top opportunities, risks, ownership, and requested sponsor actions. |

## 17. Measurable success criteria

### 17.1 Workshop completion criteria

The workshop is complete only when:

- Cost baseline totals reconcile within the agreed tolerance or the unresolved variance is documented.
- Top-cost assets and workloads are identified for the agreed scope.
- Material findings trace to source evidence.
- Every deep-dive workload has a root-cause evidence pack or a clearly documented evidence gap.
- Every accepted candidate has an owner and validation method.
- Quick wins, engineering changes, and architectural changes are separated.
- The 30/60/90-day roadmap is approved by accountable participants.
- Performance, reliability, security, and scalability guardrails are recorded.
- Candidate savings and realized savings are clearly distinguished.

### 17.2 Post-workshop outcome measures

The customer SHOULD select relevant measures from:

- Percentage of total cost attributable to an owner/team/workload.
- Percentage of material compute governed by approved policies.
- Idle compute hours and cost.
- Cost of failed and retried work.
- Cost per successful job/pipeline run.
- Cost per TB processed or data product refresh.
- SQL queue p50/p95 and query runtime p50/p95.
- Job runtime p50/p95 and SLA achievement.
- Provisioned-to-active compute ratio.
- Shuffle, spill, GC, scan, or file-count reduction for optimized workloads.
- Percentage of selected workloads using validated compute configuration.
- Percentage of backlog candidates validated.
- Percentage of implemented actions with measured benefits.
- Commitment coverage and utilization after rightsizing.
- Budget variance and cost anomaly response time.

Targets SHALL be customer-specific and SHALL be set only after baseline validation.

## 18. Downstream asset requirements

### 18.1 Workshop deck

The deck SHALL:

- Use the module sequence in this document.
- Lead with customer evidence and decisions.
- Separate facts, hypotheses, recommendations, and decisions.
- Include source and analysis-window references on evidence slides.
- Include trade-offs and confidence on recommendation slides.
- End each module with its customer deliverable and decisions required.

### 18.2 Facilitator guide

The guide SHALL include:

- Session objectives and timing.
- Required participants and evidence.
- Discovery prompts and decision questions.
- Expected patterns and false-positive risks.
- Lab setup and troubleshooting.
- Escalation for missing or conflicting evidence.
- Parking-lot and action-capture process.
- Criteria for stopping an unsupported analysis.

### 18.3 Pre-work questionnaire

The questionnaire SHALL map directly to:

- Customer profile fields.
- Scope and time window.
- Technical and organizational prerequisites.
- Evidence inventory.
- Workload selection.
- Security and data-handling approval.
- Known constraints, commitments, and future plans.

### 18.4 Lab guide

The lab guide SHALL include:

- Scenario and learning objective.
- Customer or synthetic dataset description.
- Access and setup.
- Step-by-step analytical tasks.
- Expected outputs, not predetermined customer conclusions.
- Evidence-quality checks.
- Validation and rollback design.
- Facilitator answer guide for synthetic data.
- Cleanup and retention instructions.

### 18.5 Post-workshop action plan

The action plan SHALL include:

- Approved backlog.
- 30/60/90-day roadmap.
- Owners and approvers.
- Architecture/security/procurement dependencies.
- Experiment and rollout schedules.
- Benefit metrics and reporting.
- Toolkit rerun dates.
- Governance meeting cadence.

### 18.6 Assessment Toolkit implementation backlog

The downstream toolkit backlog SHALL include:

- Collector epics by source.
- Normalized model and schema versioning.
- Correlation and reconciliation.
- Detector framework and initial detector catalog.
- Evidence and confidence model.
- Machine-readable and human-readable outputs.
- Security, redaction, and deployment model.
- Test fixtures and contract tests.
- Operational monitoring and partial-failure handling.
- Documentation and customer configuration.

## 19. Roles and decision responsibilities

| Decision / activity | Accountable role | Required contributors |
|---|---|---|
| Scope and financial objective | Executive sponsor | FinOps, platform owner |
| Evidence access and retention | Customer technical owner | Security, data owners |
| Billing baseline approval | FinOps lead | Azure platform, Databricks platform |
| Workload selection | Technical workshop owner | Workload owners, FinOps |
| Technical finding validation | Workload owner | Platform/Spark/SQL/data engineers |
| Production change approval | Customer change authority | Workload owner, security, architecture |
| Commitment purchase | Finance/procurement owner | FinOps, Azure platform, architecture |
| Backlog prioritization | Executive/technical sponsor | All module owners |
| Benefits sign-off | FinOps lead | Workload and platform owners |

## 20. Risks and required mitigations

| Risk | Required mitigation |
|---|---|
| Incomplete cost attribution | Quantify unallocated cost and add telemetry/ownership work to the backlog. |
| Short or unrepresentative time window | Mark reduced confidence and collect additional peak/seasonal evidence. |
| Double-counting Azure and DBU cost | Reconcile by billing boundary, meter, time, and product; document allocation. |
| Optimization harms SLA | Require benchmark, guardrails, canary, and rollback criteria. |
| Larger compute masks inefficient code/data | Complete Spark/code/data root-cause analysis before scaling by default. |
| Spot interruption causes production instability | Restrict to fault-tolerant workloads with measured fallback and retry behavior. |
| Serverless recommendation ignores constraints | Validate feature, network, governance, region, and workload eligibility. |
| `VACUUM` removes required history | Review retention, streaming, clones, recovery, and compliance before change. |
| Commitments lock in avoidable demand | Rightsize and account for planned migrations before procurement. |
| Toolkit partial failure appears successful | Emit explicit collection status, missing scopes, errors, and confidence impact. |
| Savings are estimated but not realized | Track lifecycle through implemented and measured states using baseline comparison. |
| Recommendations lack ownership | Do not accept backlog items without an accountable owner and approver. |

## 21. Requirements traceability matrix

| Requested capability | Requirements location | Primary output |
|---|---|---|
| Objectives and outcomes | Sections 4 and 17 | Success and outcome model |
| Audience and skill | Section 5 | Participant requirements |
| Assumptions and prerequisites | Section 6 | Readiness decision |
| Discovery and customer data | Section 7 | Questionnaire and evidence inventory |
| Current-state assessment | Section 8 | Cost baseline |
| Azure cost + DBU cost | Section 9, Module A | Cost model and cost-driver map |
| Highest-cost assets/workloads | Module A, Exercise 1 | Ranked cost drivers |
| Cluster utilization/right-sizing | Module C, Exercise 2 | Compute plan |
| Autoscaling/auto-termination | Module C | Compute plan |
| Job vs all-purpose | Module C | Compute decision matrix |
| Classic vs Serverless | Module C | Suitability matrix |
| Photon/runtime | Module C | Benchmark candidates |
| Spot VM risk | Module C | Spot eligibility findings |
| SQL Warehouse analysis | Module D, Exercise 3 | SQL plan |
| Spark UI analysis | Module E, Exercise 4 | Root-cause evidence pack |
| Code/CDC/joins/UDFs | Module F, Exercise 5 | Engineering change set |
| Delta/data optimization | Module G, Exercise 6 | Table-level plan |
| System tables | Module B, Section 10 | Observability model |
| Tags/policies/ownership | Module B | Governance control model |
| Dashboards/budgets/alerts/FinOps | Module B | FinOps operating model |
| Reservations/Savings Plans | Module H | Commitment assessment |
| Actual workload deep dives | Module I | Evidence packs |
| Advanced labs | Section 12 | Lab specifications |
| Prioritized backlog | Section 14 | Optimization backlog |
| Quick/engineering/architecture | Section 14 | Classified actions |
| 30/60/90-day roadmap | Section 15 | Action roadmap |
| Deliverables/success criteria | Sections 16-17 | Acceptance model |
| Automation and aggregation | Section 10 | Toolkit specification |
| Deck/labs/guide/questionnaire/plan | Section 18 | Downstream asset contracts |

## 22. Source and technical currency requirements

The workshop content owner SHALL validate links, feature status, regional availability, pricing behavior, and preview/beta status during asset creation and before each delivery.

Primary and supporting references include:

- [The Complete Guide to Azure Databricks Cost Optimization](./docs/AzureDatabricksCostOptimization.md)
- [Azure Databricks pricing](https://azure.microsoft.com/en-us/pricing/details/databricks/)
- [Azure Databricks account usage reports](https://learn.microsoft.com/en-us/azure/databricks/admin/account-settings/usage)
- [Azure Databricks system tables](https://learn.microsoft.com/en-us/azure/databricks/admin/system-tables/)
- [Monitor costs using system tables](https://learn.microsoft.com/en-us/azure/databricks/admin/usage/system-tables)
- [Monitor the cost of Serverless Compute](https://learn.microsoft.com/en-us/azure/databricks/admin/system-tables/serverless-billing)
- [Azure Databricks architecture best practices: Cost Optimization](https://learn.microsoft.com/en-us/azure/well-architected/service-guides/azure-databricks#cost-optimization)
- [Azure Databricks compute policies](https://learn.microsoft.com/en-us/azure/databricks/admin/clusters/policies)
- [Azure Cost Management cost analysis](https://learn.microsoft.com/en-us/azure/cost-management-billing/costs/quick-acm-cost-analysis)
- [Azure Databricks reserved capacity](https://learn.microsoft.com/en-us/azure/cost-management-billing/reservations/prepay-databricks-reserved-capacity)
- The optimization, Delta, SQL, AQE, DFP, deletion-vector, merge, clustering, file-sizing, and `VACUUM` references linked from the primary source article.

The content owner SHALL:

- Avoid presenting preview or beta behavior as generally available.
- Verify feature and pricing applicability for the customer's region, SKU, tier, and workspace configuration.
- Distinguish Azure Reservations, Azure Savings Plans, and Databricks reserved capacity/commit constructs.
- Update toolkit source mappings when system-table schemas or APIs change.
- Record the validation date and source version in the facilitator guide.

## 23. Final acceptance checklist

- [ ] The document remains L300 and excludes introductory Databricks content.
- [ ] Customer placeholders are explicit and no customer facts are fabricated.
- [ ] All requested technical topics are mapped in Section 21.
- [ ] Every major module contains all seven required fields.
- [ ] The workshop uses customer telemetry and includes a synthetic fallback.
- [ ] Azure infrastructure and DBU cost are separated without double counting.
- [ ] The toolkit is read-only and cannot perform production remediation.
- [ ] Toolkit provenance, quality, confidence, reconciliation, and failure semantics are defined.
- [ ] Recommendations require evidence, owner review, validation, and change control.
- [ ] Cost, performance, reliability, security, and scalability trade-offs are explicit.
- [ ] Quick wins, engineering changes, and architectural changes are separated.
- [ ] The two-day agenda produces the required outputs.
- [ ] Deliverables support deck, labs, guide, questionnaire, action plan, and toolkit implementation planning.
- [ ] Success criteria distinguish candidates, validated opportunities, implemented changes, and realized benefits.

## 24. Reference environment implementation and validation requirements

**Post-implementation reconciliation:** The [master specification's reference-environment sections](AzureDatabricksCostOptimizationEndToEndSpecification.md#reference-environment) distinguish the deployed sample-based lab from the more extensive target contract below. Serverless jobs and SQL were validated; Classic live execution remains capacity-blocked in the recorded evidence. The proposed seeded retail generator, complete ownership manifest/reset/expiration lifecycle, and verified dependency-aware teardown are not fully delivered. The current assessment has one-command scope selection and one consolidated report, but is not a complete implementation of all workshop discovery requirements.

### 24.1 Purpose, scope, and operating principles

The workshop asset package SHALL include an implementable reference environment that allows facilitators to demonstrate and test the requirements in this document without modifying a customer production workspace. The reference environment is a controlled synthetic lab, not a production architecture recommendation and not evidence of customer savings.

The implementation SHALL:

- Create one new, isolated Azure Databricks **Premium** workspace in **East US**.
- Deploy into the Azure subscription selected as the operator's current/default subscription after an explicit preflight confirmation; subscription IDs SHALL NOT be hard-coded.
- Use a uniquely named, workshop-owned resource group and a separately named Azure Databricks managed resource group.
- Use Bicep for Azure control-plane resources and PowerShell plus documented Azure Databricks REST APIs for workspace objects.
- Include Classic compute, Serverless Compute for jobs and notebooks, and a Serverless SQL warehouse, subject to preflight confirmation of regional and workspace eligibility.
- Generate only synthetic, non-sensitive data.
- Bound every workload by rows, bytes, runs, concurrency, wall-clock duration, and/or spend controls.
- Default to stopped or absent compute, aggressive autostop, and no recurring schedules.
- Treat telemetry that has not arrived yet as **pending telemetry**, never as zero usage, zero cost, successful attribution, or failed collection.
- Be idempotent for create/update operations and exact-scope for reset and teardown operations.

The reference implementation SHALL NOT:

- Reuse an existing workspace, resource group, metastore schema, catalog, cluster, warehouse, job, notebook folder, or service principal unless it was created for the same recorded deployment ID.
- Deploy customer data, production credentials, unrestricted recurring jobs, or unbounded load generators.
- Claim realized savings from list prices, synthetic runs, incomplete billing data, or a single non-representative execution.
- Delete resources based only on a name prefix, wildcard, tag query, current resource group, or current workspace.

### 24.2 Repository implementation contract

The downstream implementation SHALL keep Azure and Databricks provisioning boundaries explicit.

| Component | Required implementation | Required behavior |
|---|---|---|
| Subscription-scope entry point | Bicep | Resolve the confirmed default subscription, create the exact workshop resource group in East US, and call resource-group-scoped modules. |
| Azure resource modules | Bicep | Create the Premium Azure Databricks workspace, its distinct managed resource group reference, required telemetry resources, diagnostic settings supported by the selected API version, tags, and optional resource-group budget. |
| Parameterization | Bicep parameter file plus PowerShell-generated deployment values | Require deployment ID, environment name, location fixed to `eastus`, unique-name suffix, owner, expiration timestamp, allowed budget contacts, and feature flags. Do not store secrets. |
| Workspace bootstrap | PowerShell calling Azure Databricks REST APIs | Create only manifest-owned workspace folders, notebooks, jobs, policies, warehouse, catalog/schema/tables, queries, and permissions. |
| Scenario runner | PowerShell calling jobs, command/notebook, and SQL APIs | Start named scenarios, enforce run limits, wait with finite timeouts, record run/query IDs, and fail explicitly on terminal errors or timeout. |
| Validation | PowerShell and notebook/SQL assertions | Produce machine-readable results and a human-readable summary for every validation stage. |
| Reset | PowerShell calling Azure Databricks REST APIs | Cancel active manifest-owned runs, stop manifest-owned compute, delete/recreate mutable synthetic data, and restore scenario parameters without deleting the workspace. |
| Teardown | PowerShell plus Azure resource deployment operations | Delete only the exact manifest-owned Databricks objects and exact recorded Azure resource group after guard checks and explicit confirmation. |

The implementation SHOULD use the following top-level commands or equivalent clearly named entry points:

- `Test-ReferenceEnvironmentPrerequisites`
- `Deploy-ReferenceEnvironment`
- `Initialize-DatabricksWorkshop`
- `Test-ReferenceEnvironment`
- `Invoke-WorkshopScenario`
- `Reset-ReferenceEnvironment`
- `Remove-ReferenceEnvironment`

Each command SHALL support non-interactive execution with explicit parameters. Destructive commands SHALL require an additional confirmation switch or an interactive typed deployment ID; a generic `-Force` flag alone is insufficient.

### 24.3 Deployment identity, manifest, and ownership

Every deployment SHALL have an immutable, globally unique deployment ID. The same value SHALL be written to:

- Azure resource tags.
- The deployment manifest.
- The Azure Databricks workspace folder path.
- Databricks object names or descriptions where supported.
- Synthetic table properties or comments.
- Test evidence and scenario result records.

At minimum, Azure resources SHALL carry these tags:

| Tag | Required value |
|---|---|
| `workshop` | `adb-cost-optimization` |
| `deploymentId` | Exact immutable deployment ID |
| `environment` | `reference` |
| `owner` | Confirmed accountable owner |
| `expiresOn` | UTC ISO 8601 expiration timestamp |
| `managedBy` | `bicep-powershell` |
| `costCenter` | Supplied workshop cost center or `workshop` |

The local deployment manifest SHALL be generated only after Azure deployment succeeds and SHALL be updated after each successful Databricks object creation. It SHALL contain:

- Tenant ID, confirmed subscription ID, resource group name and resource ID.
- Azure deployment name and deployment ID.
- Databricks workspace resource ID, workspace URL, workspace ID when available, and managed resource group name.
- Exact IDs and canonical paths of every created Databricks object.
- Bicep template/version identifier and bootstrap script version.
- Creation and expiration timestamps.
- Feature eligibility results for Classic, serverless jobs/notebooks, Serverless SQL, Unity Catalog, and system tables.
- Reset generation and last successful validation stage.
- Teardown status and any retained evidence location.

The manifest SHALL NOT contain access tokens, refresh tokens, client secrets, SQL results containing credentials, or customer data. Writes SHALL be atomic so an interrupted update does not replace a valid manifest with a partial file.

### 24.4 Preflight and authorization requirements

Before deployment, `Test-ReferenceEnvironmentPrerequisites` SHALL:

1. Resolve the current Azure context and display tenant, subscription name, and subscription ID.
2. Require explicit confirmation that the resolved subscription is the intended default subscription.
3. Verify permission to create a resource group, Azure Databricks workspace, managed resource group, telemetry resources, diagnostic settings, role assignments if required, and an optional budget.
4. Confirm that the intended resource group and managed resource group names are absent, or are owned by the same deployment ID recorded in the supplied manifest.
5. Check East US availability and current eligibility for the requested Azure Databricks Premium workspace capabilities.
6. Verify quotas for the parameterized Classic node type and maximum worker count.
7. Verify Serverless Compute eligibility for jobs and notebooks and Serverless SQL eligibility independently; one successful check SHALL NOT imply the others.
8. Verify Azure Databricks authentication without persisting a personal access token. Microsoft Entra ID/OAuth credentials SHOULD be used.
9. Verify workspace administrator or delegated permissions needed to create the scoped objects.
10. Verify Unity Catalog/metastore assignment and permissions. If a metastore is unavailable, stop with a documented prerequisite failure rather than silently substituting workspace-local or legacy objects.
11. Validate unique-name constraints, expiration timestamp, budget values, and allowed notification recipients.
12. Produce a preflight report with `pass`, `fail`, or `not-applicable` for each check.

Deployment SHALL stop before creating resources if a mandatory preflight check fails. Unsupported serverless capability SHALL be reported as a blocking readiness gap because all three compute surfaces are required by this reference environment.

### 24.5 Azure resources implemented with Bicep

The Bicep implementation SHALL use current, supported API versions verified at implementation time and SHALL create:

1. One uniquely named resource group in East US.
2. One Azure Databricks workspace with `sku.name` set to `premium`, a separately named managed resource group ID, and the minimum configuration required by the lab.
3. One Log Analytics workspace when required for selected Azure control-plane diagnostics.
4. Supported diagnostic settings for the Azure Databricks workspace and other created resources, with categories selected from runtime discovery rather than assumed categories.
5. An optional resource-group-scoped Azure Cost Management budget with conservative thresholds and approved notification recipients.
6. Any minimal storage or telemetry resource explicitly required by the chosen lab implementation; optional resources SHALL be feature-flagged and documented.

The Bicep implementation SHALL:

- Keep `location` fixed to `eastus` for this reference profile.
- Emit workspace resource ID, workspace URL where available, resource group resource ID, managed resource group name, and telemetry resource IDs as outputs.
- Use deterministic names derived from the deployment ID plus a collision-resistant suffix.
- Avoid broad subscription-scope role assignments. Any required assignment SHALL use the narrowest supported scope and a named principal parameter.
- Avoid private networking, customer-managed keys, or enhanced compliance add-ons unless a separate profile explicitly enables and validates them; the baseline reference environment is intentionally minimal and isolated.
- Preserve Azure Databricks-managed resources as opaque implementation details and SHALL NOT deploy directly into or individually modify the managed resource group.
- Pass Bicep build/lint and deployment `what-if` before create/update.

### 24.6 Databricks objects implemented with PowerShell and REST

After the Azure workspace reaches a successful terminal provisioning state, the bootstrap SHALL use PowerShell with documented REST API versions to create the following exact-scope objects:

| Object | Required reference implementation |
|---|---|
| Workspace folder | `/Shared/adb-cost-optimization/<deployment-id>` or an equivalently isolated manifest-recorded path. |
| Notebooks | Setup/data generation, Classic baseline, Classic optimized, serverless job baseline/optimized, serverless notebook baseline/optimized, SQL setup/queries, telemetry checks, validation, and reset helpers. |
| Catalog and schema | A uniquely named Unity Catalog catalog and schema dedicated to the deployment; no default catalog/schema mutation. |
| Tables/views | Synthetic source, dimension, fact, skew, change-feed, baseline output, optimized output, SQL aggregate, expected-results, and scenario-run metadata objects. |
| Classic compute policy | A deployment-owned policy restricting node types, runtime range, maximum workers, autotermination, tags, and prohibited local overrides. |
| Classic job compute | One job cluster definition; no persistent interactive cluster is required. |
| Serverless jobs | Separate bounded baseline and optimized tasks, or one parameterized job with immutable run records that distinguish variants. |
| Serverless notebook | A facilitator-invoked notebook using serverless notebook compute, with explicit maximum input and run guidance. |
| Serverless SQL warehouse | Smallest supported serverless size appropriate for the lab, aggressive autostop, bounded cluster scaling, and no automatic start outside an invoked scenario. |
| SQL artifacts | Parameterized queries for attribution, expensive-query analysis, correctness comparison, and telemetry-readiness checks. |
| Jobs/workflows | No recurring schedule by default; every task SHALL have a finite timeout and a maximum-concurrent-runs value of one unless a bounded SQL concurrency test explicitly requires otherwise. |
| Permissions | Least-privilege facilitator manage/run access and participant read/run access as supported; no account-wide grants. |

REST calls SHALL:

- Use finite connection and operation timeouts.
- Implement bounded retries only for documented transient status codes, honoring server retry guidance.
- Fail on non-success responses with the method, endpoint class, correlation/request ID when available, and a redacted response body.
- Record created object IDs immediately in the manifest.
- Detect same-deployment objects and converge them to the declared configuration.
- Reject same-name objects that are not proven to belong to the manifest's deployment ID.
- Avoid logging authorization headers or bearer tokens.

### 24.7 Synthetic sample-data specification

The reference dataset SHALL be deterministic from a recorded random seed and SHALL contain no copied customer records. It SHALL model a retail order pipeline with enough structure to exercise attribution, Spark, SQL, incremental processing, and Delta layout analysis.

| Dataset | Required characteristics | Default bound |
|---|---|---|
| `customers` | Stable dimension, region and segment columns, deterministic keys | At most 100,000 rows |
| `products` | Stable dimension with category and price bands | At most 10,000 rows |
| `orders_history` | Date-distributed fact data with filterable fields and intentionally non-optimal baseline layout | At most 5,000,000 rows or 1 GiB, whichever occurs first |
| `order_lines` | Join-intensive fact data with controlled key skew | At most 10,000,000 rows or 2 GiB, whichever occurs first |
| `orders_changes` | Inserts, updates, duplicates, late arrivals, and corrections for incremental tests | At most 2 percent of history rows |
| `query_concurrency` | Parameter table for bounded dashboard-like SQL requests | At most 8 concurrent requests for at most 10 minutes |

Data generation SHALL stop at the first configured row, byte, or duration limit. The seed, generated row counts, approximate bytes, file counts, checksums, and generation duration SHALL be recorded.

The expected-results table SHALL include invariant business measures used for baseline/optimized comparison, including row count, distinct business keys, gross sales, net sales, tax, quantity, late-arrival count, duplicate-resolution count, and a deterministic hash over canonicalized aggregate results.

### 24.8 Bounded baseline and optimized scenarios

Each scenario SHALL run only on demand and SHALL accept a `small` default profile. A larger profile MAY exist for facilitator preparation but SHALL require an explicit opt-in parameter, a cost estimate, and a lower environment expiration window.

| Scenario | Baseline | Optimized | Hard execution bounds | Evidence produced |
|---|---|---|---|---|
| Classic job compute | Fixed, intentionally overprovisioned worker count within the policy; full scan and avoidable shuffle; autotermination enabled | Autoscaling with lower minimum/maximum, Photon/runtime candidate when eligible, filtered reads, improved join/partition strategy | Maximum 4 workers, one run per variant by default, 20-minute task timeout, 45-minute scenario timeout | Cluster spec, run timeline, Spark stages/tasks, utilization, shuffle/spill, runtime, output invariants |
| Serverless job | Full-history processing and repeated action within the bounded dataset | Incremental change processing, reused result, native expression/join improvement | One concurrent run, one baseline and one optimized run, 15-minute task timeout each | Run IDs, processed rows/bytes, duration, retries, DBU/billing records when available, correctness |
| Serverless notebook | Facilitator executes a bounded exploratory aggregation with a deliberately broad scan | Predicate/column pruning and reusable aggregate on identical business logic | `small` profile only, one facilitator session, stop after 15 minutes, no loop exceeding three actions | Query plans, scan metrics, notebook assertions, session timestamps |
| Serverless SQL warehouse | Broad scan plus bounded concurrent dashboard queries | Pruned/materialized aggregate or query rewrite with identical outputs | Smallest supported size, maximum cluster count 1 unless the concurrency lab explicitly sets 2, 5-minute autostop where supported, at most 8 clients for 10 minutes | Query history/profile, queue time, duration, bytes scanned, spill, warehouse events, correctness |
| Delta/incremental | Reprocess history and write intentionally small bounded files | Merge only changes and compare a justified layout/maintenance option | One baseline and one optimized write, no `VACUUM`, no data beyond deployment schema | Table history, file count/size, bytes read/written, merge metrics, invariants |

Intentional inefficiencies SHALL be safe, documented, and bounded. They SHALL NOT include infinite loops, Cartesian joins without a strict input cap, uncontrolled repartition counts, recursive job submission, unrestricted streaming, deliberately failing retry storms, or disabled termination controls.

An optimized result SHALL be accepted only when:

- All declared correctness invariants match.
- Runtime and cost-related metrics are compared for equivalent logical work.
- Reliability signals do not regress beyond the declared threshold.
- The evidence window and telemetry status are recorded.
- Any improvement is described as an observed lab result, not a guaranteed customer saving.

### 24.9 Telemetry-readiness and delayed-billing handling

The implementation SHALL distinguish operational telemetry, Databricks usage telemetry, Azure billing telemetry, and calculated estimates. Each source SHALL have its own readiness state:

`not-requested -> requested -> pending -> available | partial | timed-out | failed`

The telemetry readiness report SHALL include:

- Source, table/API/query, workspace and Azure scope.
- Scenario run/query/cluster/warehouse IDs needed for correlation.
- Event time, collection time, expected availability window, and last poll time.
- Rows found, minimum/maximum event times, completeness checks, and known exclusions.
- Currency and price source for financial values.
- Whether the value is observed usage, list-price estimate, Azure billed cost, amortized cost, or an allocation.
- Readiness state and the reason for `partial`, `timed-out`, or `failed`.

Operational validation MAY complete before billing records arrive. When system billing tables, account usage, or Azure Cost Management data have not yet materialized:

- The test SHALL return `pending telemetry`, not `0`, `pass`, or `fail`.
- Scenario execution SHALL remain successful if its technical assertions passed.
- Cost-attribution acceptance SHALL remain incomplete.
- The manifest SHALL retain correlation IDs and the earliest safe retry time.
- A resumable telemetry validation command SHALL recheck without rerunning paid workloads.
- Polling SHALL use bounded attempts and backoff and SHALL stop at a configured deadline.

Estimated DBUs or list-price cost MAY be shown for immediate facilitation only when clearly labeled `estimate`, with method, assumptions, and pricing timestamp. Estimated values SHALL NOT be substituted into billing reconciliation acceptance tests.

### 24.10 Validation stages and test evidence

Validation SHALL be staged so failures identify the affected boundary.

| Stage | Required tests | Exit evidence |
|---|---|---|
| V0 - Static | PowerShell parse/analysis, Bicep build/lint, parameter schema, REST payload contract tests, no-secret scan | Versioned static-test report |
| V1 - Preflight | Azure context confirmation, permissions, East US capability/quotas, serverless eligibility, Unity Catalog, naming, budget inputs | Signed or timestamped preflight report |
| V2 - What-if | Subscription/resource-group deployment `what-if`; no resources outside exact target scope | Reviewed change summary |
| V3 - Azure deployment | Resource group/workspace/telemetry provisioning states, Premium SKU, East US, tags, outputs, diagnostics | Azure deployment IDs and assertions |
| V4 - Workspace bootstrap | Object existence/configuration, permissions, policy enforcement, no schedules, IDs match manifest | Bootstrap result and object inventory |
| V5 - Smoke | Synthetic data generation, one minimal Classic task, one serverless job task, one serverless notebook assertion, one SQL query | Run/query IDs and correctness assertions |
| V6 - Scenario | Baseline/optimized pairs meet bounds, outputs match, metrics captured, timeouts enforced | Scenario evidence packs |
| V7 - Telemetry | Operational sources available; billing sources available or explicitly pending; correlations tested | Telemetry readiness report |
| V8 - Reset rehearsal | Active work cancelled, compute stopped, mutable data restored, smoke test can rerun | Reset report and incremented reset generation |
| V9 - Teardown rehearsal or execution | Exact-scope plan, guard checks, protected-scope negative tests, deletion/post-deletion verification | Teardown plan/result and retained evidence index |

Every test record SHALL include deployment ID, test version, timestamp, actor, input profile, result, duration, evidence references, and redacted error details. A stage SHALL not be marked passed when a mandatory assertion is skipped.

Before workshop delivery, V0 through V6 and V8 SHALL pass. V7 SHALL be either passed or explicitly `pending telemetry` with correlation evidence and a scheduled recheck. V9 SHALL at minimum pass a non-destructive plan and negative guard tests; full teardown SHALL be proven in a disposable rehearsal deployment before first use.

### 24.11 Cost-control and runtime safety requirements

The reference environment SHALL apply defense-in-depth cost controls:

- The default data profile SHALL be `small`.
- Classic worker and autoscaling maxima SHALL be enforced by policy and payload validation.
- Classic compute SHALL use autotermination of 10 minutes or the lowest supported safe value.
- The Serverless SQL warehouse SHALL use 5-minute autostop where supported, otherwise the lowest supported value, with the deviation reported.
- Jobs SHALL have task/run timeouts, maximum concurrency one by default, no retries for intentionally expensive tasks, and no recurring schedules.
- SQL concurrency tests SHALL enforce client, query, and wall-clock limits.
- Serverless notebook instructions SHALL include a facilitator stop time and prohibit unattended sessions.
- A scenario runner SHALL refuse execution after `expiresOn`, when a prior run is active, or when the requested profile exceeds policy bounds.
- The implementation SHALL include a post-scenario stop sweep for manifest-owned clusters, warehouses, and active runs.
- Budget notifications SHOULD be configured at conservative forecast/actual thresholds when permitted, but SHALL be treated as delayed alerts rather than real-time kill switches.
- A pre-run estimate SHALL list configured compute surfaces, maximum duration, and pricing timestamp without presenting the amount as a guaranteed charge.
- A daily facilitator check SHALL list running manifest-owned compute and environment age.

The environment SHALL default to an expiration of no more than seven days. Extensions SHALL update both the manifest and Azure tag, identify the approver, and retain the prior expiration in the audit record.

### 24.12 Facilitator reset requirements

`Reset-ReferenceEnvironment` SHALL return the deployment to a known workshop-ready state without recreating Azure infrastructure. It SHALL:

1. Validate the manifest, deployment ID, subscription ID, resource group resource ID, and workspace ID.
2. Refuse to run if any identity differs from the live resource.
3. Cancel active manifest-owned job runs and wait for a terminal state with a finite timeout.
4. Stop manifest-owned Classic compute and the Serverless SQL warehouse.
5. Restore job definitions, compute policy, warehouse bounds/autostop, and notebook parameters to the declared configuration.
6. Remove only scenario outputs and checkpoints inside the deployment-owned catalog/schema.
7. Rebuild deterministic synthetic tables from the recorded seed or restore a deployment-owned baseline copy.
8. Clear deployment-owned query artifacts or run metadata needed for a clean participant experience while retaining the immutable facilitator evidence archive.
9. Reapply least-privilege participant permissions.
10. Run correctness, object-inventory, no-active-compute, and minimal smoke checks.
11. Increment the reset generation and write a reset report.

Reset SHALL NOT delete the workspace, resource group, catalog outside the deployment-owned catalog, external locations, metastore, users, groups, or account-level objects. A partial reset SHALL fail explicitly and list remaining actions; it SHALL NOT report `ready`.

### 24.13 Guarded exact-scope teardown

`Remove-ReferenceEnvironment` SHALL use the manifest as the primary allowlist and Azure resource IDs as the authority. Teardown SHALL have a plan phase and an execute phase.

The plan phase SHALL:

- Validate the manifest schema and signature/hash if implemented.
- Resolve live tenant, subscription, resource group, workspace, and deployment ID.
- Require exact equality with the manifest and matching Azure tags.
- Inventory all manifest-owned Databricks objects and all Azure resources in the exact resource group.
- Identify unrecorded objects/resources as blockers requiring review.
- Confirm the resource group is not protected by a delete lock; the tool SHALL NOT remove locks automatically.
- Confirm the operator supplied the exact deployment ID and an explicit destroy switch.
- Export the final object inventory, scenario evidence index, telemetry status, and teardown plan to the approved retention location.

The execute phase SHALL:

1. Cancel manifest-owned active runs and stop manifest-owned Classic compute and SQL warehouses.
2. Delete Databricks objects in dependency order using exact IDs and paths.
3. Verify that no manifest-owned active compute remains.
4. Delete the exact recorded workshop resource group by full Azure resource ID.
5. Poll to a finite deadline for resource-group deletion.
6. Verify that the resource group no longer exists and that no deployment-owned object remains addressable.
7. Mark the local manifest `destroyed` with timestamp and retained-evidence location rather than deleting the audit record.

Teardown SHALL refuse to proceed when:

- The current subscription or tenant differs from the manifest.
- The resource group or workspace resource ID differs.
- Required ownership tags are absent or have a different deployment ID.
- The target is a subscription, management group, tenant, default metastore, shared catalog/schema, or Azure Databricks managed resource group by itself.
- The plan contains a resource outside the exact recorded workshop resource group.
- Wildcards, prefix-only selection, or an unresolved variable is present.
- Unmanifested resources exist and have not been explicitly adjudicated.

Cleanup of a failed partial deployment SHALL use the last valid manifest plus Azure deployment outputs. If neither can prove exact ownership, the script SHALL stop and emit a manual review inventory rather than attempt deletion.

### 24.14 Evidence mapping to workshop modules and labs

| Reference-environment evidence | Workshop use | Module/lab mapping |
|---|---|---|
| Deployment manifest, Azure tags, object inventory, telemetry readiness | Defines scope, provenance, ownership, and evidence limitations | Modules A-B; Exercise 1; Sections 7-10 |
| Classic and serverless run records with bounded cost estimates | Separates infrastructure, DBU, list-price estimate, and pending billed cost | Modules A, C, H; Exercises 1-2 |
| Policy, node timeline, run phases, utilization, and termination events | Supports right-sizing, idle-time, autoscaling, Classic/Serverless, and control analysis | Module C; Exercise 2 |
| SQL warehouse configuration, events, query history/profile, queues, scan, and spill | Supports sizing, concurrency, autostop, and expensive-query diagnosis | Module D; Exercise 3 |
| Spark plans, stages, task distributions, shuffle, spill, GC, and skew fixture | Supports execution root-cause analysis without defaulting to larger compute | Module E; Exercise 4 |
| Full-history versus incremental outputs, join/UDF/native-expression comparisons, invariants | Supports code and pipeline change design with correctness evidence | Module F; Exercise 5 |
| Delta history, file distribution, merge metrics, scan metrics, and bounded maintenance comparison | Supports layout and maintenance assessment without unsafe `VACUUM` | Module G; Exercise 6 |
| Estimate labels, delayed billing state, pricing timestamp, and no-realized-savings guard | Supports financial interpretation and commitment decision discipline | Module H; Exercises 1 and 7 |
| Candidate records generated from scenario evidence, validation outcomes, reset proof | Supports prioritization, ownership, roadmap, and repeatable operation | Module I; Exercise 7; Sections 14-17 |
| Reset and teardown reports | Supports lab guide cleanup, facilitator operations, and environment governance | Section 18.2-18.4; LAB-003 |

The facilitator guide SHALL identify the exact evidence files, queries, and object IDs used in each module. Participants SHALL still evaluate evidence quality and SHALL not be told that the optimized variant is automatically the correct customer recommendation.

### 24.15 Reference-environment acceptance criteria

The reference environment is accepted only when all of the following are evidenced:

- [ ] A fresh deployment creates exactly one isolated Premium Azure Databricks workspace in East US in the explicitly confirmed default subscription.
- [ ] Azure resources are created from Bicep after successful build/lint and reviewed `what-if`.
- [ ] Workspace objects are created through PowerShell/REST and every created object is recorded by exact ID or canonical path.
- [ ] The environment includes a bounded Classic job, serverless job, serverless notebook, and Serverless SQL warehouse path.
- [ ] No job or SQL artifact has an enabled recurring schedule.
- [ ] Classic autotermination, SQL warehouse autostop, worker/cluster caps, concurrency limits, and task/scenario timeouts are enforced and tested.
- [ ] Synthetic data is deterministic, non-sensitive, within row/byte bounds, and has recorded correctness invariants.
- [ ] Each baseline/optimized pair performs equivalent logical work and either matches invariants or fails visibly.
- [ ] The Classic, serverless job/notebook, SQL, Spark, code/incremental, and Delta scenarios produce the evidence mapped in Section 24.14.
- [ ] Operational telemetry is queryable and correlated to run/query/resource IDs.
- [ ] Delayed billing is represented as `pending telemetry`; no missing record is converted to zero usage or zero cost.
- [ ] Immediate financial outputs clearly distinguish estimates/list price from billed or amortized cost.
- [ ] V0 through V6 and V8 pass; V7 passes or has an approved pending-telemetry recheck; V9 guard tests pass.
- [ ] Reset returns the environment to a validated ready state without affecting objects outside the deployment scope.
- [ ] Teardown refuses mismatched tenant, subscription, resource IDs, tags, wildcards, managed-resource-group-only targets, and unreviewed unmanifested resources.
- [ ] A disposable rehearsal proves exact resource-group teardown and post-deletion verification.
- [ ] Test and evidence records contain no secrets or customer data.
- [ ] All environment-specific claims record their validation date, API/runtime versions, region, and feature eligibility.
- [ ] Workshop outputs continue to distinguish synthetic observations, candidates, validated opportunities, implemented customer changes, and realized customer benefits.
