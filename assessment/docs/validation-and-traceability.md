# Validation and requirement traceability

The [consolidated end-to-end specification](../../docs/AzureDatabricksCostOptimizationEndToEndSpecification.md) records requirements and implementation disposition. Assessment execution evidence is retained in [test-results.md](../test-results.md); later capability/UI evidence is in the [UI acceptance record](../../ui/docs/capabilities-test-plan.md).

Documentation checked against the implementation on **2026-09-29**. The execution
counts below remain dated records, not fresh results from this documentation check.

## Validated evidence

### Capability and workflow follow-ups: 2026-09-29

The [UI acceptance record](../../ui/docs/capabilities-test-plan.md) reports:

- Initial capability delivery: 474 tests across frontend, Python, and Pester suites,
  plus 18 grouped production-stack browser checks.
- Five-step workflow/review-export follow-up: 169 frontend tests across 20 files.
- Report-preview follow-up: 42 targeted tests across 5 files, plus 6 grouped browser checks.

These overlapping runs must not be added together. Optional asset collection and
publication were tested locally with mocked APIs; live dashboard rendering remains
unverified. Saved-native compatibility checks did not recollect cloud evidence.

### Historical scope-selection validation: 2026-09-26

| Evidence | Result |
| --- | --- |
| Documented `Invoke-Assessment.ps1 -Action Validate` | Exit 0 |
| Pester | 136 passed, 0 failed, 0 skipped |
| Python unittest | 40 passed, 0 failed |
| Total automated assessment tests | **176 passed** |
| Static read-only scan | `AssessmentReadOnlySafety=PASS` |
| Live picker-to-report run | `adb-cost-assessment-20260926T214949861Z-1e4e3e10`; final status `partial` |
| Scope checks | 15 normalized Azure resources, 76 cost rows, zero outside selected/managed groups |
| Output checks | One Markdown report; 63 JSON/NDJSON files parsed; snapshot regeneration byte-identical |
| SQL validation boundary | No SQL Warehouse configured for this picker run; post-run Warehouse GET was `STOPPED` |
| Multi-subscription coverage | Fixture/mocked validation, not a live customer-estate claim |

### Earlier live-run evidence

The following metrics describe an earlier run before the reporting and scope changes.
They are historical evidence, not the current test inventory.

| Evidence | Result |
| --- | --- |
| Static read-only scan | `AssessmentReadOnlySafety=PASS` |
| Live run | `adb-cost-assessment-20260926T034326949Z-54eb3631`, final status `partial` |
| Live collector results | 13 total: 3 passed, 8 partial, 0 failed, 1 pending telemetry, 1 skipped |
| Live outputs | 35 raw files, 11 normalized NDJSON datasets, 21 Markdown/CSV report files |
| Cost evidence | 5,084 Actual Cost rows; 2,642.122153 USD authoritative and collected total |
| Telemetry quality | Medium, score 0.836 |
| Findings | One medium-confidence `MON-MISSING-BUDGET`; no inferred savings |
| Safety observation | 0 Azure activity-log entries and 0 compute-start operations during the observed live-run interval; all 10 clusters terminated and both warehouses stopped |

The detailed evidence and root-cause fixes are recorded in [`test-results.md`](../test-results.md). The live result proves the tested scope and date only; it is not a claim that all customer configurations or permissions have been validated.

## Human validation

Every generated finding has `humanValidationRequired: true`. Use:

- `reports/assessment-report.md`, Section 17, for workshop review;
- `reports/human-validation-sign-off.csv` for an editable register;
- `optimization-candidates.json` and normalized evidence for source traceability.

Before acceptance, record:

- reviewer and role;
- UTC review time;
- accept, reject, defer, or needs-more-evidence decision;
- business/SLA context;
- performance and reliability risk;
- security/governance impact;
- validation experiment and success/rollback thresholds;
- accountable owner and approver;
- rationale.

Savings remain unknown until an approved change has comparable before/after evidence and workload normalization.

The UI provides a compact optional decision/reviewer/note form in **Review & export**.
Downloading is not approval. Richer handoff fields still belong in the review
process above; saving a UI decision preserves existing fields but does not require
every handoff field to be completed.

## Implementation traceability

Status meanings:

- **Implemented**: present and covered by automated tests.
- **Partial**: implemented for a bounded subset or with named gaps.
- **Deferred**: required design exists, but implementation is absent.
- **Operational**: fulfilled by customer procedure rather than automated code.

| Requirement area | Status | Evidence and boundary |
| --- | --- | --- |
| Sections 2-3: goals and read-only boundary | Partial | End-to-end collection/model/report flow and method allowlists are implemented. Broad catalog goals remain incomplete. |
| Section 4: operating modes | Partial | Native collection, bounded-cost readiness, domain skips, direct-Python offline analysis, UI raw import, child re-analysis, saved snapshots, and repeated runs are supported. No automated cross-run benefits comparator exists. |
| Section 5: scope configuration | Implemented/Partial | Interactive/explicit multi-subscription/group selection, qualified IDs, workspace discovery, all selected cost scopes, SQL identifier isolation, and run config snapshots are implemented. Exclusion lists, management groups, business scopes, sampling contracts, retention, and config schema version remain incomplete. |
| Sections 6.1-6.2: Azure inventory/cost | Partial | Resource Graph, ARM workspace detail, managed resources, tags, policy, diagnostics, quota, Actual/Amortized query, budgets, reservations, and Savings Plans are collected. Forecast, tag history, commitment utilization/coverage, detailed storage/network allocation, and checkpoints are deferred. |
| Sections 6.3-6.5: account/workspace, billing, attribution | Partial | Workspace/account inventory, settings, metastore, IP lists, optional groups, billing/list prices, selected tags, and audit SQL exist. Live system-table collection requires a configured warehouse; normalized attribution currently uses Azure cost tags. |
| Sections 6.6-6.9: compute, jobs, SQL, Spark | Partial | Inventory plus observed utilization, sizing candidates, job failure/routing, query/user/warehouse summaries, and node-network metrics are implemented. Sample coverage remains explicit. Spark stage/task/event-log analysis and authoritative per-query costs remain unsupported. |
| Sections 6.10-6.11: Delta and code/query patterns | Partial/Deferred | UC tables, information schema, and hashed table detail/history files are collected and normalized. Fine-grained file-distribution analysis and notebook source scanning are deferred; optional notebooks are metadata only. |
| Sections 6.12-6.14: streaming, GPU/model serving, pools/spot | Deferred/Partial | Pool inventory, a driver-on-spot detector, and optional serving-endpoint metadata exist. Dedicated streaming, GPU, serving-performance, eviction, and pool-cost analysis is deferred. |
| Sections 6.15-6.16: FinOps and commitments | Partial | Budget normalization, governance evidence, and explicit-input hourly commitment scenarios are available. Native financial eligibility, sustained-demand derivation, contract-term economics, forecast collection, renewal, and purchase automation are not provided. |
| Section 7: detector catalog | Partial | Six base rules/evidence gates plus versioned capability findings for sizing, jobs, queries, and two posture checks. The full requirements catalog is not implemented; no inferred finding savings or automatic remediation. |
| Sections 8-9: model and correlation | Partial | Schema 1.0 envelopes, 30 mapped entity types, raw provenance, canonical Azure IDs, scope filtering, workspace/cost rules, and unmatched/ambiguous behavior are implemented. This is not full coverage of the requirements' 33-entity model. |
| Section 10: cost/reconciliation | Partial | Actual/amortized separation, corrections, effective-price dates, currency guard, tolerance, list-price join, and serverless duplicate prevention are tested. Contract price, tax input, approved shared allocation, and commitment-adjusted cost are deferred. |
| Section 11: quality/confidence | Partial | Per-source/overall metrics and detector confidence are implemented. Current freshness/source-authority metrics are coarse and not source-age-aware. |
| Section 12: outputs | Implemented/Partial | Core machine outputs, scope filter, capability analysis, and 17 report subjects are generated. The UI renders Markdown as HTML and can generate full-run XLSX and scenario artifacts. Not every raw source maps to a normalized entity. |
| Section 13: human validation | Implemented | Markdown/CSV register, saved per-finding decisions, and mandatory human-validation flags exist. Review is optional for download, not optional before implementing recommendations. |
| Section 14: security/permissions | Partial/Operational | CLI OAuth, method/SQL guards, recursive redaction, and explicit snapshot deletion exist. Permission setup and coverage-count publication are separately confirmed operations. Encryption, automatic retention, and external audit remain customer controls. |
| Section 15: collector behavior | Partial | Bounded paging/retries, SQL deadline, live progress/counts, optional assets, 1-4 Databricks workers, and bounded audit splitting exist. UI cancellation terminates the tracked live process. Incremental checkpoints, whole-collector timeout, and cancellable local re-analysis remain absent. |
| Section 16: tests | Validated/Partial | Dated assessment and UI records cover contracts, safety, scope, capabilities, reports, snapshots, and browser workflows. Totals are tied to those executions, not maintained as a current suite count. Live optional assets, concurrency performance, and publication rendering remain unverified. |
| Section 17: acceptance | Partial | Read-only safety and bounded live collection are validated. Full selected-estate coverage, full detector catalog, complete normalized schema set, and human sign-off remain scope-dependent or deferred. |

## Test coverage map

| Test suite | Primary coverage |
| --- | --- |
| `Assessment.Foundation.Tests.ps1` | Config rejection, mutation opt-ins, unique manifests, status propagation, retries, Databricks token/request timeout. |
| `Azure.AssessmentCollectors.Tests.ps1` | Azure allowlist, temp request body, pagination, cost mapping/windowing, explicit failure. |
| `DatabricksCollectors.Tests.ps1` | Entry points, method/SQL safety, pagination, redaction, status combinations, empty files, SQL polling/chunks/timeouts, partial preservation. |
| `test_assessment_contracts.py` | Fixtures, schema envelopes, cost edge cases, quality, detectors, repeated/synthetic end-to-end behavior. |
| `test_model_pipeline.py` | Parsing, provenance, correlation, reconciliation, confidence, detector boundaries, pipeline outputs. |
| `test_reports.py` | Deterministic report set, evidence links, unknown savings, pipeline integration. |
| `Assessment.Scope.Tests.ps1`, `InvokeAssessment.Scope.Tests.ps1`, `InvokeAssessment.Tests.ps1` | Scope selection, saved configuration, wrapper actions, approvals, and report regeneration. |
| `Azure.CostThrottling.Tests.ps1`, `Azure.Governance.Tests.ps1` | Cost pacing/cooldowns, readiness probe, budgets, and diagnostic applicability. |
| `Capabilities.Tests.ps1`, `PartialCollectorRecovery.Tests.ps1` | Optional assets, concurrency initialization, notification redaction, audit splitting, and partial recovery. |
| `ui/server/test_capabilities.py` | Rules, metrics, import, paging, child re-analysis, workbook, scenarios, and mocked publication. |
| UI frontend and browser suites | Five-step navigation, review/export, report preview, saved snapshots, and source outcomes; see the [UI test record](../../ui/docs/capabilities-test-plan.md). |

## Revalidation commands

```powershell
Invoke-Pester -Path .\assessment\tests -PassThru -Output Normal
python -m unittest -v `
  assessment.tests.test_assessment_contracts `
  assessment.tests.model.test_model_pipeline `
  assessment.tests.reports.test_reports
.\assessment\scripts\Test-AssessmentReadOnly.ps1 -Path .\assessment
```

Run UI/server suites separately as described in the
[UI reproduction commands](../../ui/docs/capabilities-test-plan.md#reproduce).
For an authorized live revalidation, use the reviewed customer scope and:

```powershell
.\assessment\Invoke-Assessment.ps1 -Action Run `
  -ConfigPath .\scope.json `
  -ContinueOnCollectorError
```

If the scope includes warehouse SQL, supply approved persisted consent or explicitly
add `-ApproveSqlWarehouseAutoStart`. Record the run ID, date, source statuses,
activity-log/compute-start review, and test counts in a new evidence record. Do not
overwrite historical results or treat a documentation check as a live validation.
