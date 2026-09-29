# Validation and requirement traceability

The [consolidated end-to-end specification](../../AzureDatabricksCostOptimizationEndToEndSpecification.md) is the current requirements and post-implementation disposition. Detailed execution evidence is retained in [test-results.md](../test-results.md).

## Validated evidence

Validation date: **2026-09-26 UTC**

### Latest scope-selection validation

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

The following metrics describe an earlier run before the final reporting and scope changes. Older test-count summaries are superseded by the current totals above.

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

## Implementation traceability

Status meanings:

- **Implemented**: present and covered by automated tests.
- **Partial**: implemented for a bounded subset or with named gaps.
- **Deferred**: required design exists, but implementation is absent.
- **Operational**: fulfilled by customer procedure rather than automated code.

| Requirement area | Status | Evidence and boundary |
| --- | --- | --- |
| Sections 2-3: goals and read-only boundary | Partial | End-to-end collection/model/report flow and method allowlists are implemented. Broad catalog goals remain incomplete. |
| Section 4: operating modes | Partial | Standard, collection-only readiness approximation, domain skips, direct-Python offline analysis, and repeated independent runs are supported. No first-class mode selector or automated cross-run benefits comparator exists. |
| Section 5: scope configuration | Implemented/Partial | Interactive/explicit multi-subscription/group selection, qualified IDs, workspace discovery, all selected cost scopes, SQL identifier isolation, and run config snapshots are implemented. Exclusion lists, management groups, business scopes, sampling contracts, retention, and config schema version remain incomplete. |
| Sections 6.1-6.2: Azure inventory/cost | Partial | Resource Graph, ARM workspace detail, managed resources, tags, policy, diagnostics, quota, Actual/Amortized query, budgets, reservations, and Savings Plans are collected. Forecast, tag history, commitment utilization/coverage, detailed storage/network allocation, and checkpoints are deferred. |
| Sections 6.3-6.5: account/workspace, billing, attribution | Partial | Workspace/account inventory, settings, metastore, IP lists, optional groups, billing/list prices, selected tags, and audit SQL exist. Live system-table collection requires a configured warehouse; normalized attribution currently uses Azure cost tags. |
| Sections 6.6-6.9: compute, jobs, SQL, Spark | Partial | Cluster/policy/pool/event, Jobs/runs/pipelines, SQL Warehouse, query history, node timeline, and selected-run metadata collectors exist. Full utilization, Spark UI/event-log metrics, cost-per-workload, and many required aggregations are deferred. |
| Sections 6.10-6.11: Delta and code/query patterns | Partial/Deferred | UC tables, information schema, and selected table detail/history collection exist. File-distribution normalization and code/notebook scanning are deferred. |
| Sections 6.12-6.14: streaming, GPU/model serving, pools/spot | Deferred/Partial | Pool inventory and a driver-on-spot detector exist. Dedicated streaming, GPU, model-serving, eviction, and pool-cost analysis is deferred. |
| Sections 6.15-6.16: FinOps and commitments | Partial | Azure budgets/reservations/Savings Plans, compute policies, optional account budgets, and governance evidence are collected. Forecast, notifications, assignment modeling, utilization, break-even, renewal, and contract logic are deferred. |
| Section 7: detector catalog | Partial | Six conservative rules/evidence gates are implemented. Remaining catalog entries are deferred and reports state insufficient evidence where appropriate. |
| Sections 8-9: model and correlation | Partial | Schema 1.0 envelopes, 20 mapped entities, raw provenance, canonical Azure IDs, workspace/cost rules, unmatched and ambiguous behavior are implemented. Full 33-entity model and broader identifiers are deferred. |
| Section 10: cost/reconciliation | Partial | Actual/amortized separation, corrections, effective-price dates, currency guard, tolerance, list-price join, and serverless duplicate prevention are tested. Contract price, tax input, approved shared allocation, and commitment-adjusted cost are deferred. |
| Section 11: quality/confidence | Partial | Per-source/overall metrics and detector confidence are implemented. Current freshness/source-authority metrics are coarse and not source-age-aware. |
| Section 12: outputs | Implemented/Partial | All named top-level machine files and 17 report subjects are generated. NDJSON is the open normalized format; not every raw source maps to a normalized entity. |
| Section 13: human validation | Implemented | Markdown/CSV sign-off register and mandatory human-validation finding flag are generated; completing sign-off is operational. |
| Section 14: security/permissions | Partial/Operational | Azure CLI OAuth, token non-persistence, method/SQL guards, recursive Databricks redaction, and documented least privilege are present. Output encryption, retention deletion, and external access audit are customer controls. |
| Section 15: collector behavior | Partial | Pagination, bounded retry, Databricks request timeout, SQL deadline, counts, timestamps, explicit partial results, and no success-shaped failure are implemented. Incremental checkpoints, full cancellation, whole-collector timeout, and complete elapsed-time progress are deferred. |
| Section 16: tests | Validated/Partial | 176 assessment tests cover contracts, paging, retries/timeouts, redaction, reconciliation, detectors, report generation, wrapper behavior, SQL bodies, timestamps, scope selection, qualified boundaries, snapshots, and repeated runs. Live multi-subscription collection and every possible telemetry combination remain unvalidated. |
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

## Revalidation commands

```powershell
Invoke-Pester -Path .\assessment\tests -PassThru -Output Normal
python -m unittest -v `
  assessment.tests.test_assessment_contracts `
  assessment.tests.model.test_model_pipeline `
  assessment.tests.reports.test_reports
.\assessment\scripts\Test-AssessmentReadOnly.ps1 -Path .\assessment
```

For a live revalidation, use the reviewed customer scope and:

```powershell
.\assessment\Collect-CostOptimizationAssessment.ps1 `
  -ConfigPath .\scope.json `
  -ContinueOnCollectorError
```

Record the run ID, date, source statuses, activity-log/compute-start review, and test counts in a new evidence record. Do not overwrite the historical validated result.
