# Assessment toolkit test results

## Manual repair commands and permission-to-run navigation - 2026-09-29 UTC

- **69 targeted UI tests passed** across manual commands, permission setup, validation
  progress/guards, local configuration checks, and historical snapshot isolation.
  TypeScript and the self-contained production build passed. The existing bundle-size
  advisory remains non-blocking.
- An isolated Playwright test copied all three command blocks and verified clipboard
  content against displayed commands, accounting for Windows CRLF line endings. Light
  and dark layouts passed at 1440, 768, and 390 pixels.
- The displayed administrator PowerShell parsed successfully and passed **10 native
  PowerShell mock scenarios**: success, already assigned, existing other administrator,
  wrong identity, missing account-admin role, wrong workspace, canceled confirmation,
  changed owner, interrupted PUT, and unverified ownership. The success path used exactly
  one PUT with `metastore_info.owner`; failures did not automatically retry.
- Browser navigation verified green access does not bypass full validation, active
  validation prevents duplicates, canceled reruns preserve results, and Continue opens
  Run analysis with a separate Start read-only assessment action. Zero browser errors.
- **No live Azure/Databricks requests, grants, role assignments, or assessments were made
  by these UI tests.** Cloud and SQL clients were mocked, validation responses were
  intercepted, and unintended mutation endpoints were blocked. The running production
  host serves the rebuilt guide and next-step controls without a server restart.

## Explicitly approved East US permission repair - 2026-09-29 UTC

- Read-only inspection confirmed the two denied workspaces shared one East US metastore
  owned by `System user`; the assessment identity had the Databricks account-admin role.
- After separate explicit user approval covering the broad persistent role, the verified
  identity was assigned as that metastore's administrator. No other metastore was changed.
  The three exact read grants then succeeded once each.
- Live SELECT and explicit grant inspection succeeded from both affected workspaces
  (`...0779` and `...5468`), returning zero rows. Isolated live Playwright checks showed
  **Already accessible - no grants needed** for both, with zero browser errors and no full
  validation/assessment starts. The approved administrator assignment remains in place.
- The local [remediation audit](output/.ui-server/permission-remediation/eastus-20260929-approved.json)
  records the assignment, SQL statement IDs, grant outcomes, and verification. This was a
  separately authorized operator repair, not automatic elevation by the assessment UI.

## Access-first permission setup and live Playwright verification - 2026-09-29 UTC

- Reproduced the grant-first defect with failing regression tests: an already-readable
  table incorrectly offered grants, and table/query failures were never checked first.
  The fix now verifies identity and runs a bounded pipeline SELECT before offering any grants.
- **47 targeted UI tests and 67 server tests passed.** TypeScript, production build, and
  read-only safety scan passed. Two isolated Playwright suites passed access-first behavior,
  empty-table success, denial previews, missing-table/timeouts, target changes, grant
  confirmation, replay protection, identity changes, rerun confirmation, and restart recovery.
  Light/dark layouts passed at 1440, 768, and 390 pixels with zero browser runtime errors.
- With explicit user approval for live read-only queries, Playwright exercised the rebuilt
  UI on host `2026.09.28.9` using the existing three workspace/warehouse selections:

  | Workspace ID suffix | Live pipeline-table access | UI outcome |
  | --- | --- | --- |
  | `...7016` | SELECT succeeded | Already accessible; no grants offered |
  | `...5468` | SELECT denied | Exact grant preview; confirmation unchecked |
  | `...0779` | SELECT denied | Exact grant preview; confirmation unchecked |

- **Zero live grant requests, zero full validation/run requests, and zero browser runtime
  errors.** Browser routing explicitly blocked mutation endpoints other than the read-only
  preview/check action. Denied previews were canceled without granting. Live queries used
  approved SQL Warehouses and could incur DBU charges; this was not a zero-cost fixture run.
- At this stage, the two real SELECT denials remained unresolved and required an authorized
  administrator; the later explicitly approved repair is recorded above.
  No account/metastore roles were elevated, no real grants were applied, and no unsupported
  evidence was marked green. Switching targets does not reuse another workspace's success.
- The independent host was updated only after checking for active work. Health and rebuilt
  UI checks passed. Local setup audits and the session's live-test results preserve the
  recorded outcomes; the previously shared browser page was not navigated or reset.

## Validation rerun confirmation and permission recovery - 2026-09-29 UTC

- **51 targeted UI tests and 65 server tests passed.** The UI verification comprised
  49 tests across five files, followed by a 21-test rerun including two additional cases.
  TypeScript, production build, and the read-only safety scan passed.
- Re-running existing validation results now requires confirmation. Cancel preserves the
  report and Continue to run without any request; confirmation starts exactly one new
  validation. Returning from unchanged Configure opens the existing report.
- The reported stale apply returned HTTP 404, but the old UI treated every apply error as
  unknown and rendered a spinner from its safety-lock flag. HTTP status is now preserved;
  stale rejected requests allow fresh previews, while transport loss after an accepted
  apply stays unknown. Spinner rendering follows actual status-request activity.
- Setup previews and outcomes are persisted. Read-only recovery after a host restart
  restores terminal results, invalidates unused previews, and labels interrupted submitted
  grants unknown without resubmission. Missing/corrupt audits never become success.
- The reported `MANAGE` denial is a genuine Unity Catalog authorization failure. New
  explicit SQL failures mark the rejected grant failed and later grants not attempted.
  The UI names the administrator action instead of suggesting the same identity can
  elevate itself. Existing audit history is preserved, not retroactively rewritten.
- Playwright exercised native confirmation cancel/accept, unchanged Configure navigation,
  successful fixture grants, identity changes, partial denial, missing previews, and
  restart recovery against isolated real server routes with a fake SQL client.
  Unknown outcomes stopped spinning and remained safely blocked. Both themes passed
  layout checks at 1440, 768, and 390 pixels, with **zero browser runtime errors**.
- **No live grants, identity queries, warehouse starts, or validation reruns were issued
  during these fixes.** After verifying validation was complete and no child work or
  recorded grant operation was active, the independent host was updated to `2026.09.28.8`.
  Health and rebuilt UI checks passed. The user's existing failed setup was recovered
  through a status GET from its unchanged audit, with access still correctly unverified.

## Warehouse defaults and confirmed permission setup - 2026-09-28 UTC

- **90 targeted UI tests and 58 server tests passed.** The final UI changes were also
  checked by a focused 35-test rerun. TypeScript, production build, and read-only safety
  scan passed. Vite retains the existing large-bundle advisory.
- Warehouse tests cover running-first/smallest-stopped selection, deterministic ties,
  unsupported sizes/states, existing selections, explicit None, and fresh warehouse consent.
  Live discovery now uses the warehouse list GET API, with tested pagination.
- Permission tests cover separate consent, verified principal, exact grants, expiry,
  replay rejection, identity change, partial failure, audit failure, lost responses,
  bounded token requests, incomplete HTTP responses, and read-only status recovery.
  Historical snapshots do not render or invoke permission setup.
- Playwright exercised the rebuilt UI against an isolated local instance of the real
  server routes with a fake SQL client and cloud calls explicitly prohibited. Preview and
  cancel submitted no grants. A confirmed successful case submitted exactly the three fixed
  grants followed by SELECT verification. Replay returned 409; identity change submitted
  no grants; a partial-denial case stayed failed without retry or false success.
- Browser checks verified unchecked initial warehouse approval, no automatic validation,
  one explicitly requested fixture validation, zero runtime errors, and no horizontal
  overflow at 1440, 768, and 390 pixels.
- **No live grants, identity queries, warehouse starts, or assessment reruns were performed.**
  Updated host `2026.09.28.7` was started after confirming the old host had no child
  collector process. Its health endpoint and rebuilt UI returned successfully.

## Workspace-specific deep dives and warning mitigation - 2026-09-28 UTC

- **61 targeted UI tests, 39 server tests, 47 Databricks collector tests, and 15 assessment
  contract tests passed.** TypeScript, the production build, and the read-only safety scan
  passed. The local host was updated to `2026.09.28.6` after confirming no collector child
  process was active; its health endpoint and rebuilt UI responded successfully.
- Job run IDs and selected table names are now workspace-scoped. Legacy single-workspace
  lists migrate before automatic scope expansion. Ambiguous multi-workspace globals require
  assignment or removal, and explicit empty workspace lists override global values.
- Collector tests asserted **zero run-metadata and selected-table requests to other
  workspaces**, while preserving the real detailed-Spark-metrics limitation on the selected
  workspace. Untargeted Spark deep dives are skipped, not reported as successfully inspected.
- Production browser tests used a three-workspace fixture with a legacy numeric run ID and
  table target. Only the original workspace received those targets. The two missing warehouse
  selections were named explicitly, and warehouse approval was required before the single
  explicit fixture validation request. Permission and unsupported Spark-metrics warnings
  stayed visible. Layout checks passed at 1440, 768, and 390 pixels.
- Existing initial-scope, retry-recovery, manual-exclusion, and same-name-group browser
  regressions passed. **0 automatic validations, 0 live cloud calls, and 0 browser errors.**
  No permissions were granted, no warehouses started, and no real assessment was rerun.

## Preselected subscription initialization - 2026-09-28 UTC

- **55 targeted UI tests passed** across configuration state, validation, workflow navigation,
  and saved snapshots. TypeScript and production build passed.
- Defaults now also apply on the first successful discovery of a setup whose subscription
  is already selected. Discovery and sign-in retries retain edits, manual exclusions, and
  approvals instead of reloading the disk template. Failed initial discovery keeps default
  initialization pending until discovery succeeds.
- Browser fixtures reproduced the reported pattern: only `rg-adb-cost-workshop-l300c01`
  initially configured, with `dbx-rg` and `dbx-lab-01` also containing workspaces. The rebuilt
  UI checked all three without a subscription click. Recovery after an initial discovery
  failure produced the same selection and retained an intervening customer-ID edit.
- Manual deselection survived workflow navigation; fresh subscription defaults, empty-group
  exclusion, and same-name subscription isolation also passed. Legacy global Warehouse IDs
  remain limited to previously configured targets.
- Snapshot regressions confirmed historical pages do not bootstrap or expand scope.
  **0 automatic validation calls, 0 live cloud calls, and 0 browser errors**. The browser
  suite's single explicit validation used a fixture response; no real assessment was run.

## Automatic subscription scope defaults - 2026-09-28 UTC

- **38 targeted UI tests passed** for configuration state, scope validation, and workflow
  navigation; TypeScript and production build passed.
- Browser testing with fixture responses verified that selecting a subscription checks
  both discovered workspace-containing groups and their workspaces, leaving empty groups
  unchecked. Manual exclusions survive adding another subscription, and same-named groups
  in separate subscriptions remain independent.
- The submitted configuration includes qualified resource-group IDs and the selected
  subscription cost scopes. Removing the subscription removes only its selection.
- Warehouse choices and auto-start approval remain unset. Selection starts **0 validation
  or collection calls**; the test's only validation request followed an explicit click
  and used a local fixture response. **0 live cloud calls and 0 browser errors**.

## Snapshot isolation and deletion - 2026-09-28 UTC

- Frontend: **95 tests passed** across 13 files; TypeScript and production build passed.
- Local API server: **38 tests passed**, including confirmation, active-run refusal,
  path boundaries, Windows junctions, partial I/O failures, and origin/content-type checks.
- Reproduced automatic validation on page mount before the fix. Regression tests now
  require explicit validation actions and keep approval edits and navigation passive.
- Production browser checks selected two saved runs, navigated Configure/Validate/Run,
  and refreshed a snapshot URL. Only saved-run list/result GET requests occurred:
  **0 discovery, validation, collection, or deletion calls** against the real history.
- Both themes at **1440, 768, and 390 pixels** passed horizontal-overflow checks.
- An isolated local host with disposable fixture folders verified canceling deletion,
  deleting the selected snapshot, clearing its URL/results, and bulk deletion. A snapshot
  created after confirmation and the output/control folders were preserved. Reloading
  retained the remaining snapshot. **0 browser runtime errors**.
- Host `2026.09.28.5` is running. All **20 existing snapshots were preserved** during testing.
  No Azure or Databricks calls were needed, and no customer review decisions were changed.

## Readiness and analysis corrections - 2026-09-28 UTC

The final pass on the corrected production host (`2026.09.28.4`) used one browser-driven
readiness request and one full assessment with the existing approved workshop scope.
The existing SQL Warehouse auto-start approval was retained; SQL can incur DBU charges.
No access grants, remediation, job runs, or real review-decision writes were performed.

### Automated regression

- Targeted PowerShell suites (collectors, foundation, Azure governance): **65 passed**.
- Python model, contracts, and reports: **44 passed**.
- Local API server: **31 passed**.
- Frontend: **86 passed** across 12 files; TypeScript and production build passed.
- Read-only safety: **PASS**.
- Coverage includes safe table identifier handling, budgets v2.1, OPEN catalog binding
  behavior, unsupported diagnostics versus genuine failures, account configuration,
  structured progress issues, Azure budget normalization, JSON-valued prices, retained
  Databricks service charges, cost-basis separation, hashed table evidence mapping,
  single-row and chunked SQL column alignment, and malformed-row rejection.

### Live browser end-to-end result

Run: `adb-cost-assessment-20260928T061654548Z-d0c2940f`.

An earlier browser pass completed, but deeper artifact inspection exposed single-row
SQL array flattening. That defect was reproduced, fixed, and regression-tested before
this final end-to-end rerun. The earlier run is preserved, not rewritten or presented
as the verified final result.

- Readiness: **0 blockers, 2 actionable warnings**.
- Full collection: **11 source groups passed, 2 partial**.
- Azure policy/diagnostics, workspace/account inventory, Unity Catalog (including the
  corrected selected-table detail query), and governance passed.
- Remaining partial sources are pipeline timeline SELECT access and full Spark
  stage/task/executor metrics. These are genuine gaps; the overall run remains `partial`.
- Authoritative and collected reporting-basis cost: **6.363842 USD**, with **0 excluded
  cost** and **0 variance**. The separate list-price estimate is **1.89387 USD**;
  **0 usage records remain unpriced**. The estimate is not added to the Azure bill.
- The false `MON-MISSING-BUDGET` finding is absent. This scope produced **0 candidates**,
  which is not proof that no optimization exists or that incomplete sources are healthy.
- Selected table detail/history artifacts reached the normalized model. The selected
  table's detail is exactly **1 record**, with `format: delta`, `numFiles: 1`, and a
  populated size, rather than 17 column values split into malformed records.
- All six results tabs opened, the saved snapshot reopened after refresh, and report
  preview/download succeeded. **0 browser runtime errors**.
- Original saved runs were not rewritten. An isolated offline replay of the previous
  run independently verified the corrected amounts and removed budget false positive.

### Fixture browser and publication checks

- Review, named decisions, save, export preview/download, snapshot reopening, and
  **New assessment** reset passed without live cloud calls.
- Grouped warnings and passing checks were tested using production classification
  with local fixtures, in light/dark themes at **1440, 768, and 390 pixels**.
- Six blog animations and their stills were refreshed with labeled fixture data.
  All **14 media links** resolve locally; GIFs contain multiple frames and valid durations.
- Customer review decisions were not changed by these tests.

## Scope-selection validation - 2026-09-26 UTC

This section supersedes earlier test counts for the scope-selection implementation.
Historical execution evidence below is retained, not represented as a fresh rerun.

### Automated validation

Command from the repository root:

```powershell
.\assessment\Invoke-Assessment.ps1 -Action Validate
```

- Exit code: **0**.
- Read-only safety: **PASS**.
- Pester: **136 passed, 0 failed, 0 skipped**.
- Python contracts, model, and reports: **40 passed, 0 failed**.
- Total: **176 passed**.
- PowerShell syntax: 34 scripts parsed with zero errors.
- New behavioral coverage includes single/multiple subscriptions and groups,
  same-named groups across subscriptions, explicit qualified IDs, canceled/invalid
  input, inaccessible/disabled/cross-tenant scopes, empty workspace discovery,
  empty base configs with selection, SQL identifier isolation, temporary-file
  cleanup, saved-scope reports, and exact returned-run opening.
- Multi-subscription collection, partial subscription failures, and collision
  boundaries were validated with mocked Azure responses, not a live customer estate.

### Live front-door validation

All collection was restricted to subscription
`463a82d4-1896-4332-aeeb-618ee5a5aa93`, selected group
`rg-adb-cost-workshop-l300c01`, and associated managed group
`mrg-adb-cost-l300c01`.

| Command | Result |
|---|---|
| From `assessment`: `.\Invoke-Assessment.ps1 -Action Readiness -SubscriptionIds '463a82d4-1896-4332-aeeb-618ee5a5aa93' -ResourceGroups 'rg-adb-cost-workshop-l300c01' -ConfigPath .\config\workshop-scope.json` | Exit 0; run `adb-cost-assessment-20260926T214513741Z-2ebbd911`; SQL IDs removed; partial readiness, including Cost Management 429 exhaustion |
| From repository root: `.\assessment\Invoke-Assessment.ps1 -SelectScope -ConfigPath .\assessment\config\assessment-scope.example.json` | Exit 0; actual console selections supplied through stdin; run `adb-cost-assessment-20260926T214949861Z-1e4e3e10`; collection, analysis, one report, and default open completed |
| `.\assessment\Invoke-Assessment.ps1 -Action Reports -RunRoot .\assessment\output\adb-cost-assessment-20260926T214949861Z-1e4e3e10 -NoOpenReport` | Exit 0; used saved scope, no recollection; report SHA-256 unchanged |
| `.\assessment\Invoke-Assessment.ps1 -Action Open -RunRoot .\assessment\output\adb-cost-assessment-20260926T214949861Z-1e4e3e10` | Exit 0; existing consolidated report passed to the OS opener |
| Picker with `q` supplied at the subscription prompt | Expected exit 1; no new run directory |
| Explicit nonexistent resource group | Rejected before collection; no broader fallback |

Full picker-run checks:

- Azure Cost Management recovered from the earlier throttling and collected **76 rows**.
- **15 normalized Azure resource records**; **0 outside the approved groups**.
- **0 outside-scope cost rows** and **0 outside-scope resource-group IDs in the report**.
- Exactly **1 Markdown report**.
- **63 JSON/NDJSON evidence files** parsed successfully.
- Saved configuration and manifest preserve subscription-qualified group IDs.
- SQL Warehouse `19dfff78c4e639c4` was **STOPPED** on the post-run GET check, with five-minute autostop.
- No SQL Warehouse was selected by discovery; no SQL-start approval was used.
- No Azure/Databricks write API or workload-start command was issued.

The final manifest is **partial**, not a claim of complete telemetry. This no-SQL
validation intentionally left billing/system-table sources unavailable; optional
account/metadata/diagnostic sources also recorded limitations. Deep dives were
not selected. SQL-approved collection was not rerun for this change. The OS
opener returned successfully; a human must still review the report and sign off.

Filtering remains resource-group-level attribution. These checks prove exclusion
outside the selected/associated groups, not classification of every resource
inside a mixed-use group.

## Result

- Todo: `assessment-tests`
- Test status: passed
- Live assessment status: partial
- Read-only safety status: passed
- Validation date: 2026-09-26 UTC
- Live run root: `assessment/output/adb-cost-assessment-20260926T034326949Z-54eb3631`

The live run is partial because optional account-level configuration, SQL system-table access, selected deep dives, some Unity Catalog metadata, and amortized cost data were unavailable. No collector ended in `failed` status.

## Commands and counts

| Command | Result |
| --- | --- |
| `Invoke-Pester -Path .\assessment\tests -PassThru -Output Normal` | 56 passed, 0 failed, 0 skipped, 0 not run |
| `python -m unittest -v assessment.tests.test_assessment_contracts assessment.tests.model.test_model_pipeline assessment.tests.reports.test_reports` | 27 passed, 0 failed |
| `.\assessment\scripts\Test-AssessmentReadOnly.ps1 -Path .\assessment` | `AssessmentReadOnlySafety=PASS` |
| `.\assessment\Collect-CostOptimizationAssessment.ps1 -ConfigPath .\assessment\config\assessment-scope.example.json -ContinueOnCollectorError` | Completed collection and analysis; final manifest status `partial` |
| `Get-AzureAssessmentCostPages` against the configured subscription and analysis window | 5,084 actual-cost rows across paginated responses |
| `az monitor activity-log list` for the workshop resource group during the live run | 0 activity-log entries; 0 compute start operations |

Total automated tests: **86 passed**.

## Documented-command smoke tests

| Command | Result |
|---|---|
| `Invoke-Assessment.ps1 -Action Readiness` | Passed without Warehouse approval; SQL IDs omitted in a temporary scope |
| `Invoke-Assessment.ps1 -Action Readiness -ApproveSqlWarehouseAutoStart` | Passed after fixes; live run `adb-cost-assessment-20260926T055234057Z-7329c147` |
| `Invoke-Assessment.ps1 -Action Reports` | Passed and recreated the report suite |
| `Invoke-Assessment.ps1 -Action Validate` | Passed all safety and automated tests |
| `Invoke-Assessment.ps1 -Action Run -ApproveSqlWarehouseAutoStart -ContinueOnCollectorError` | Passed; live run `adb-cost-assessment-20260926T060218141Z-d6305487`, complete report suite generated |
| `Invoke-Assessment.ps1` | Passed; live run `adb-cost-assessment-20260926T154226417Z-4925fac7`, one consolidated report generated and opened |

SQL-approved readiness collected 533 billing rows, 50 compute items, 114 SQL items, 76 workload items, 588 Unity Catalog items, and 2,367 governance items. The SQL Warehouse returned to `STOPPED` through its configured five-minute autostop.

The exact full user command generated all required machine-readable and human-readable outputs. Every JSON and NDJSON file parsed successfully, no required output was missing, and the SQL Warehouse returned to `STOPPED`.

The no-argument workflow generated exactly one Markdown report with all 17 ordered sections. The consolidated report was reduced from 3.5 MB to approximately 152 KB by aggregating unattributed cost at resource grain while retaining complete normalized evidence.

## Azure Databricks scope validation

Fresh run `adb-cost-assessment-20260926T205420604Z-b448b7b9` validated collection-time and analysis-time filtering:

- Allowed resource groups: `rg-adb-cost-workshop-l300c01`, `mrg-adb-cost-l300c01`
- Azure cost rows collected: 74
- Unrelated Azure cost rows collected: 0
- Azure resources in normalized output: 14
- Unrelated Azure resources in normalized output: 0
- Unrelated providers/resource groups in consolidated report: 0
- Markdown reports: 1
- SQL Warehouse returned to `STOPPED`

## Coverage

The automated suites cover:

- Static and runtime read-only controls for Azure and Databricks.
- Scope-file validation, invalid windows, empty scope, unsafe flags, numeric limits, and example fixtures.
- Versioned manifests, required manifest fields, unique immediate repeated runs, and partial-status propagation.
- Azure Resource Graph, ARM list, and Cost Management response mapping and pagination.
- Windows-safe Azure CLI JSON bodies and continuation URLs.
- Retry limits, exponential delays, request timeouts, SQL timeout behavior, and propagated failure/cancellation behavior.
- Explicit partial failure and prevention of success-shaped empty datasets.
- Databricks GET contracts and allow-listed read-only POST contracts for SQL statements and cluster-event queries.
- Token use, sensitive-field redaction, query omission, identity/path hashing, and output secret scans.
- Databricks token, SCIM, cluster-event, and SQL-result pagination, including delayed SQL completion and chunking.
- Source-to-model normalization, canonical Azure IDs, provenance, entity mappings, and schema envelopes.
- Correlation matched, unmatched, and ambiguous behavior.
- Actual/amortized cost separation, corrections, effective-price date boundaries, list-price joins, currencies, attribution, and serverless infrastructure double-count prevention.
- Telemetry coverage, consistency, sample adequacy, partial-source quality penalties, and confidence levels.
- Detector positive, negative, boundary, insufficient-evidence, false-positive, and human-validation contracts.
- Deterministic machine outputs, reports, CSVs, evidence links, unknown-savings handling, repeated pipeline runs, and synthetic single/multi-workspace and classic/serverless scenarios.

## Live run summary

| Measure | Result |
| --- | --- |
| Collector results | 13 |
| Passed | 3 |
| Partial | 8 |
| Failed | 0 |
| Pending telemetry | 1 |
| Skipped | 1 |
| Raw files | 35 |
| Normalized NDJSON datasets | 11 |
| Human-readable/CSV report files | 21 |
| Actual-cost rows | 5,084 |
| Actual authoritative cost | 2,642.122153 USD |
| Collected total | 2,642.122153 USD |
| Telemetry quality | Medium, score 0.836 |
| Recorded collector-status limitations | 9 |
| Candidate findings | 1 (`MON-MISSING-BUDGET`, medium confidence) |
| Evidence-gap findings | 0 |

All required machine-readable files were present. Every JSON and NDJSON output parsed successfully.

## Collector statuses

| Collector | Status | Items |
| --- | --- | ---: |
| Azure inventory | passed | 15 |
| Azure policy and diagnostics | partial | 554 |
| Azure Cost Management | partial | 5,084 |
| Azure budgets and commitments | passed | 3 |
| Azure compute quotas | passed | 232 |
| Databricks workspace | partial | 1 |
| Databricks billing | pending telemetry | 0 |
| Databricks compute | partial | 50 |
| Databricks workloads | partial | 18 |
| Databricks SQL | partial | 2 |
| Databricks Unity Catalog | partial | 307 |
| Databricks governance | partial | 6 |
| Databricks Spark deep dive | skipped | 0 |

## Safety evidence

- The static safety scan passed before collection and after the code changes.
- Azure collection used only Resource Graph/Cost Management query POSTs and ARM GETs.
- Databricks collection used GETs plus two explicitly allow-listed read-only POST endpoints: SQL statement execution and cluster-event history.
- The supplied scope has no SQL Warehouse ID, so no SQL statement was submitted and no warehouse auto-start could occur.
- After cluster-event collection was corrected, 28 historical events were collected. There were 0 cluster events at or after the assessment start and 0 start/create/restart/resize-like events.
- All 10 observed clusters were `TERMINATED`.
- Both observed SQL Warehouses were `STOPPED`.
- Azure Activity Log contained 0 entries and 0 compute-start operations for the workshop resource group during the live-run interval.
- Output scanning found no bearer tokens, unredacted access tokens, unredacted query text, or clear-text notebook paths.
- No Azure or Databricks resource mutation command was executed.

## Root-cause defects fixed

- Made immediate repeated runs collision-safe with millisecond timestamps and a random suffix.
- Accepted absolute output roots on Windows.
- Added strict-mode-safe missing-identifier validation and positive collection-limit validation.
- Made empty NDJSON datasets persist as valid empty files.
- Made single-column Databricks SQL rows normalize correctly.
- Added explicit partial run-status propagation.
- Included collector partial/pending states in `errors.json` and telemetry-quality scoring.
- Excluded explicitly identified serverless infrastructure estimates from the collected total.
- Passed Azure REST request bodies by temporary JSON file and quoted URLs so Windows does not corrupt JSON or split `&$skiptoken`.
- Added and tested paginated read-only POST handling for the Databricks cluster-events API.
- Corrected workspace settings to request supported keys and made scalar/empty API response counts safe.

## Limitations

- Amortized Cost Management collection was throttled with HTTP 429 after bounded retries; actual cost completed.
- Three resource types reported that Azure diagnostic settings are unsupported.
- Databricks account inventory and account budgets require `accountId` and `accountHost`, which are not present in the supplied scope.
- Databricks billing, node timeline, query history, system jobs/pipelines, information schema, governance tags, and audit evidence require a configured SQL Warehouse ID. The test intentionally did not start a stopped warehouse.
- Identity collection is disabled by the supplied scope.
- Some Unity Catalog bindings returned permission-denied responses; these remain explicit partial evidence.
- No Spark run IDs or table deep-dive targets were selected, so those collectors were skipped.
- The live candidate is advisory and requires human validation; no savings value was inferred.
