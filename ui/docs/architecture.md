# UI architecture

## Principle

The existing PowerShell + Python toolkit is the assessment engine. This UI orchestrates and
visualizes it. Nothing in `/ui` re-derives a cost figure, re-implements a detector, or
invents a status value — it renders what the backend produced and refuses to render what
the backend did not collect.

That principle is enforced structurally by a single seam.

## Capability extension (2026-09-29)

The [capability analyzer](../../assessment/model/capabilities.py) belongs to the existing
Python pipeline and writes `capability-analysis.json`. The UI server
[operations module](../server/capability_operations.py) performs local import, scoped
paging, child re-analysis, XLSX serialization and guarded publication. It calls the same
analyzer for commitment scenarios; React does not calculate authoritative costs.

The backend seam also exposes `capabilityOperation<T>(runId, action, payload)`.
Routes are POST `/api/capabilities/import` and
`/api/runs/{id}/capabilities/{dataset|reanalyze|workbook|scenario|publish}`.
The existing loopback/origin/content-type guard protects all routes. Preview requests
are read-only. Publication additionally requires idle live operations, an exact preview
fingerprint, explicit destination/write/compute approval, and a persisted attempt audit.
No automatic write retries, DDL, grants, overwrites or embedded credentials are allowed.

Results carry an optional summary rather than bulk datasets; paged reads allow 1-200
rows. Per-resource `findingId` supplements legacy `detectorId`. Imported monetary totals
and baseline amounts are nullable, with `costAvailable=false`. Binary artifacts use
base64 transport with an explicit encoding and XLSX MIME type. Workbooks describe the
full saved run/current saved review; a revision hash distinguishes exported contents.

Imports and re-analysis persist separate run folders; parents and their reviews remain
immutable. Legacy raw JSON-encoded SQL structs, singleton task objects and opaque
notification redaction are supported without inferring missing routing or telemetry.
The PowerShell optional-assets collector preserves per-source failure/truncation,
and native collector concurrency is bounded to 1-4 (default sequential).

See the [user guide](../USER-GUIDE.md) for the supported subset and remaining plan
boundaries, and the [acceptance record](capabilities-test-plan.md) for verification.

## The seam: `src/api/backend.ts`

Every piece of data the UI displays arrives through one interface:

```ts
interface AssessmentBackend {
  discoverEstate(): Promise<SubscriptionOption[]>;   // subscriptions → RGs → workspaces
  loadDefaultConfig(): Promise<AssessmentConfig>;
  validate(config, approvals, onProgress?): Promise<ValidationReport>; // live checks, then report
  startRun(config, approvals): Promise<RunHandle>;          // streams RunEvent
  listRuns(): Promise<RunSummary[]>;
  loadResults(runId): Promise<AssessmentResults>;
  saveReview(runId, entries): Promise<void>;
  readArtifact(runId, relativePath): Promise<ArtifactPayload>;
}
```

`RunHandle` exposes `subscribe(listener)` over a `RunEvent` union (phase change, source
status, log line, completion) plus `cancel()`.

The approved demo uses `mockBackend.ts`, backed by deterministic JSON in `mock/fixtures/`.
Production uses `httpBackend.ts` with the local API. No feature component, store, or chart
knows which one is active; a production URL can opt into the offline demo with `?mock=1`.

## Layers

```
src/
  types/        Contracts only. assessment | config | findings | results | validation.
  api/          The backend seam + the Phase 1 mock implementation.
  lib/          format.ts (absent-vs-zero, status→tone), validation.ts (guard mirror).
  state/        Zustand stores: configStore, runStore, resultsStore (+ filter selectors).
  components/   Presentation primitives: Panel, KpiCard, Badge, DataTable, Tabs, Drawer,
                GuardrailStrip, ErrorBoundary, charts/.
  features/     One folder per workflow step: configure, validate, run, results, review,
                export. Results is tabbed: Executive, Cost, Compute, Findings, Quality,
                Roadmap.
  app/          App.tsx — workflow shell, step gating, scenario switcher.
  styles/       tokens → components → layout, aggregated by global.css.
```

Dependencies point downward only: `features` → `state` → `api` → `types`, with `lib` and
`components` available to any layer above them. No feature imports another feature.

## Two rules that shaped the code

**Absent is not zero.** `lib/format.ts` returns `—` for a missing number and
`"Not available"` for a missing money value; it never coerces `null` to `0`. Components
that would otherwise draw a chart check for evidence first and render a callout naming the
failed source instead. The `fabrikam-failed` scenario exists to keep this honest, and
`tests/mockBackend.test.ts` asserts it.

**The five statuses are not three.** `passed`, `partial`, `failed`, `pending telemetry` and
`skipped` each carry a distinct meaning taken from the spec, and `STATUS_MEANING` in
`lib/format.ts` is the single place that explains them to a user. `pending telemetry` in
particular is neither a failure nor a zero — it means the signal exists but the window
hasn't accumulated it yet. Collapsing these into pass/fail was the most tempting
simplification available and would have been the most damaging.

## Validation mirror

`lib/validation.ts` reproduces the CLI's guard clauses — scope required, window bounded,
SQL Warehouse auto-start approval, output root writable — so the UI can never offer to
launch something `Invoke-Assessment.ps1` would refuse. It is a *mirror*, not the authority:
Production calls `-Action Readiness` and uses the real result. If the two ever disagree,
the backend wins and the UI is wrong.

The configuration store applies this mirror before calling either backend. It includes
engagement IDs and valid analysis dates. Fresh setups supply random-suffixed IDs and
the previous 30 complete UTC days; clearing or invalidating them reports actionable
local blockers without starting PowerShell. A valid local result does not
authorize a run: the backend readiness report is still required. When PowerShell
fails before emitting progress, a completed blocking report retains its actual error;
an empty or success-shaped report without progress remains an error.

## Testing

The frontend has 60 tests across 11 files, covering formatting, validation, filters, themes,
workflow navigation and completion, warning lists, mock contract conformance, and the HTTP
adapter. The Python host has 15 tests covering CLI arguments, SQL approval behavior, path
containment, progress parsing, plain-English warning handling, review export, and real artifact mapping.

`mockBackend.test.ts` has two conventions worth keeping: the mock adds ~480 ms of
artificial latency per call, so tests that loop over artifacts need an explicit timeout; and
`MockRunHandle` uses real `window.setTimeout`, so the timeline test must use real timers
with `setPlaybackSpeed()` rather than `vi.useFakeTimers()`.

---

# Production integration

`Start-AssessmentUi.ps1` runs a Python standard-library HTTP server on loopback. The server
serves the self-contained `dist/index.html` and exposes these same-origin routes:

| Route | Purpose |
| --- | --- |
| `GET /api/health` | Host readiness |
| `GET /api/config/default` | Existing local → workshop → example config precedence |
| `GET /api/estate` | Azure subscriptions, resource groups, and Databricks workspaces |
| `POST /api/validate` | Read-only readiness with the selected approvals |
| `POST /api/validations` | Start a background readiness job; return its ID immediately |
| `GET /api/validations/{id}` | Live check list, activity timestamps, terminal report or error |
| `POST /api/runs` | Start `Invoke-Assessment.ps1 -Action Run` |
| `GET /api/runs/{id}/events` | Poll bounded progress and source-status events |
| `DELETE /api/runs/{id}` | Cancel the tracked child process |
| `GET /api/runs` | List completed persisted runs |
| `POST /api/snapshots/delete` | Permanently delete explicitly confirmed `runIds`; return `deletedRunIds` and per-run `failures`. Separate from cancellation. |
| `GET /api/runs/{id}/results` | Map persisted artifacts into `AssessmentResults` |
| `PUT /api/runs/{id}/review` | Atomically persist human decisions |
| `GET /api/runs/{id}/artifacts/{path}` | Read a contained text artifact for export |

The host uses the operator's ambient `az login`; it stores no credentials. Every run uses a
temporary JSON config with the existing schema. The PowerShell wrapper remains responsible
for safety validation, scope isolation, collection, normalization, detectors, reconciliation,
and report generation. Output statuses are preserved without collapsing `partial`, `failed`,
`pending telemetry`, or `skipped`.

The Saved snapshots dropdown beside the theme toggle reads the on-disk run index, including engine
`completed` manifests (mapped to the UI's `passed` status). Run completion refreshes the
index, and focusing the dropdown refreshes it. All snapshots appear newest collection
timestamp first. Selecting a snapshot puts its ID in the URL; loading that URL bypasses configuration
discovery and reads only persisted artifacts. Results-store request sequencing prevents a
slow earlier selection or review save from overwriting a subsequently opened run.

**New assessment** clears the configuration, approvals, validation, run progress,
results, filters, and review/export UI state without deleting saved artifacts. It
replaces the selected-run URL with `?new=1` and opens Configure. That flag reloads
installation defaults with new random-suffixed IDs, a 30-day UTC window, and empty scope
and targets; it survives refresh until a snapshot is selected. Edits are retained on
discovery/sign-in retries within a fresh setup. App owns configuration bootstrapping, and a
request sequence prevents stale discovery from restoring a cleared configuration.
Reset is disabled during discovery, sign-in, validation, or an active run.

The five-step sidebar separates selection from completion: unfinished steps are gray,
successful checks green, and failed/incomplete completed checks red, with numbered markers.
Configure uses local checks (SQL approval belongs to Validate); live Validate uses
backend readiness. Saved Validate/Run use recorded collection outcomes, including
partial and skipped distinctions. Visualize requires loaded results.
Review & export requires a download, not full sign-off. Its collapsed review form
updates selected decision/reviewer/note fields while retaining the remaining record.
Workbook/publication actions cannot reload results while review edits are unsaved.
An active, failed, or canceled run is not made green by an older loaded snapshot.

Validation uses a worker thread so HTTP requests remain responsive while PowerShell reads
source evidence. `ASSESSMENT_UI_PROGRESS=1` enables structured `AssessmentProgress:` lines.
The collector plan is shared with the actual Azure and Databricks dispatch loops; it is not
a second list maintained in the browser. Progress increments only on real collector results.
The UI polls every 750 ms with a 15-second request timeout. Navigation does not restart a
job. Failures require an explicit retry; scope changes cannot accept an older report.
Jobs are held in memory for the host lifetime; restarting the host invalidates their IDs.
The synchronous `/api/validate` route remains available for existing callers.

Readiness passes `-CostReadinessOnly` with `-SkipAnalysis`: Cost Management receives one
one-day aggregate probe per scope, while the full resource/meter/basis collection remains
in Run. Probe success is an informational access result, not a full cost-evidence pass.
Collector progress carries source-level statuses, limitations, and errors; both synchronous
and asynchronous readiness use these structured results rather than only console summaries.
The adapter groups common SQL-warehouse, account-setting, permission, and throttling causes,
retaining each source response for expansion. Explicitly unsupported diagnostics become
not-applicable notes. Unknown degradation remains a warning, and collector artifacts retain
their original evidence-quality statuses. Live progress and the final report use the same
classification.

Snapshot mode is keyed by the selected persisted run ID. Configure/Validate/Run display
saved scope and collection results, never bootstrap a live setup or claim a saved pre-run
validation report exists. Live validation starts only in explicit button handlers, not
page-mount effects or approval/configuration changes. Concurrent live work is labeled
separately and can be resumed without triggering another operation.
Re-running an existing validation report requires native browser confirmation before the
store clears it. Cancel does not call the backend. Configure's validation action opens an
existing report when nothing changed instead of silently starting another readiness run.

Subscription selection adds only discovered workspace-containing resource groups. The same
defaults apply once to preselected subscriptions on initial setup load, after successful
discovery. Failed discovery leaves initialization pending; retries preserve the current
configuration, manual exclusions, and approvals rather than reloading the disk template.
Snapshot mode never bootstraps configuration, so its recorded scope remains unchanged.
The shared scope-selection helper keeps qualified resource-group IDs, display names,
workspace membership, and selected subscription cost scopes consistent. Manual workspace
exclusions and warehouse settings in retained groups survive changes to other subscriptions.
Legacy global Warehouse IDs are moved to previously configured workspace targets before
adding new targets, so they cannot be inherited by newly selected workspaces.
UI checkboxes and local validation use qualified IDs when present, with a legacy name-based
fallback for older configurations. Fresh setup clears both legacy and qualified scope fields.

Deep-dive run/table targets live on each workspace entry. Legacy single-workspace targets
are migrated before discovery expands scope; ambiguous multi-workspace globals require
explicit assignment or removal. Local validation blocks ambiguous or nonnumeric run targets.
Both PowerShell collectors use the same workspace-first resolver, with empty arrays overriding
legacy values. No run ID is sent to a different workspace as a fallback. Detailed Spark
metrics remain unsupported and honestly reported for selected run deep dives.
Warehouse coverage guidance identifies missing selections by workspace; final readiness
warnings retain source evidence and add workspace names. Approval and data access remain
separate prerequisites, never inferred from discovery.

Live discovery lists SQL Warehouses using read-only GETs, including bounded pagination.
Discovery errors remain visible per workspace. For an included workspace with no prior
choice, the scope helper prefers the smallest RUNNING warehouse, then the smallest STOPPED
warehouse; unknown sizes/states are not guessed. Existing IDs are preserved and `''` stores
an explicit None. Initial live load ignores persisted warehouse approval; changes to included
workspace/warehouse pairs invalidate that approval. Selection never starts compute.

### Separate confirmed permission setup

`server/permission_setup.py` is outside the read-only collector boundary. Its routes are:

- `POST /api/permission-setups`: explicit warehouse consent, identity verification and a bounded read-access SELECT; grants are previewed only for a confirmed permission denial.
- `GET /api/permission-setups/{setupId}`: status only.
- `POST /api/permission-setups/{setupId}/apply`: exact confirmation and warehouse consent.

Setup requires loopback, the current local Host, same-origin browser requests, and JSON POSTs.
Only standard per-workspace Azure Databricks hosts are accepted; redirects are refused.
The server stores the target and derives the principal from `current_user()`; clients cannot
supply arbitrary SQL or another grantee. The same client then executes
`SELECT 1 FROM system.lakeflow.pipeline_update_timeline LIMIT 1`. Success, including an
empty result, completes with `accessVerified: true` and an empty grants array. The UI shows
Already accessible, with no grant-application controls. Only SQL failures carrying explicit permission
denial codes create a confirmation preview and retain `accessCheckError`. Unavailable tables,
transport failures, and other errors remain failures with no grant preview.
Apply re-verifies identity and submits only USE
CATALOG on system, USE SCHEMA on system.lakeflow, and SELECT on pipeline_update_timeline,
then verifies SELECT access. Existing grant authority is required; credentials/roles are not
elevated. Five-minute expiry and one-shot application prevent stale or replayed confirmation.

`ManualPermissionGuide` is a display/copy-only companion, not an execution endpoint.
It binds generated SQL to a matched, verified setup result and the optional PowerShell
script to validated account settings. SQL identifiers and PowerShell literals are escaped.
Unknown/active work and non-permission failures suppress mutation commands; target changes
clear the old guide and copy feedback. Clipboard failures are surfaced with manual-copy
instructions. An already accessible target labels the commands as reference only.
The administrator script runs outside the app and uses the verified account's own authority,
checks current workspace/metastore/account identity, refuses existing-admin replacement,
asks for the exact metastore ID, and issues a single
`PUT /api/2.0/accounts/{accountId}/metastores/{metastoreId}` with
`{"metastore_info":{"owner":"<verified-principal>"}}`. This optional broad, persistent role
change is explicitly distinguished from the three read grants and is never sent by the UI.

`ValidationActions` is shared by the main validation footer and the green permission
result's next-step section. Both preserve rerun confirmation, require full validation
before continuing, and block actions during discovery, sign-in, permission work, validation,
or collection. Continue navigates to Run analysis; it does not start collection.

The frontend polls status without resubmitting statements. Lost apply responses remain
unknown until status recovery or explicit operator acknowledgement after inspection. Setup
IDs and preview/apply phase persist in sessionStorage. Atomic local audit writes persist
previews and precede mutation, recording each submitted/applied/failed step. After restart,
status GETs lazily recover audits without SQL: terminal outcomes remain terminal, unused
previews are invalidated, and interrupted submitted grants become explicitly unknown.
Audit failure prevents further grants. Audits contain no tokens.

HTTP error status is preserved so a rejected stale apply (404) can discard that preview;
a 404 while polling an accepted apply is still an unknown outcome. Expiry/conflict responses
recover through a status GET, never automatic mutation. Spinner rendering follows actual
request/poll activity, not the broader safety lock for unknown outcomes. A terminal SQL
FAILED response records a failed grant and stops later grants; transport loss leaves its
outcome unknown. No failure triggers automatic retry, rollback, or role elevation.
Identity preview alone no longer discards completed validation; apply still invalidates it.
Read-access checks also preserve validation. Changing targets hides a previous target's
positive result rather than claiming the new selection was checked.

Operation locking prevents setup overlapping assessment or readiness. Setup is not rendered
in snapshots or demo mode. It never runs from discovery, navigation, validation, or refresh,
and successful setup does not automatically revalidate. The global read-only label explicitly
distinguishes assessment collection from this separately confirmed security action.

### Snapshot deletion and evidence handling

The history manager captures an explicit list of run IDs before confirmation, including
for "all". Deletion requires JSON, same-origin browser requests, and `confirmed: true`.
Under the run-state lock, each direct-child folder must have a matching terminal manifest
and no active tracked process. Symlinks and Windows reparse points are rejected before
recursive removal. The output root and unrelated folders are never deletion targets.
Each failed run is returned explicitly; partial filesystem deletion is not claimed as
success. UI state and the selected URL clear only for successfully deleted IDs.

Progress includes item counts and structured remediation issues. A result with confirmed
applicable success and only unsupported-resource notes can pass; a wholly inapplicable
result is neutral. Permission failures never become a pass. The shared issue renderer
is used by both progress and the final readiness summary.

Optional account fields are validated in the browser and PowerShell, then checked through
live account APIs. Table-detail SQL uses validated, escaped identifier components because
that command does not consistently accept the parameterized identifier form. Normalization
recognizes the collector's hashed table-detail/history filenames, unwraps Azure budget
envelopes, and decodes JSON-valued list pricing. Reconciliation retains Databricks service
charges and selects unmatched cost using the reporting basis rather than adding cost bases.
SQL result conversion preserves the nested row arrays even for a single-row response or
chunk. A row/schema width mismatch fails collection explicitly instead of padding fields
with null values and presenting malformed evidence as a successful source.

Per-check planning allowances generate the clearly labeled approximate ETA. They are not
historical measurements and never determine completion. If an active check exceeds 150%
of its allowance, remaining time is shown as unknown. A separate last-response indicator
distinguishes a lost local connection from a slow Azure call.

Both run IDs and artifact paths are validated and resolved under the configured output root.
The server binds only to `127.0.0.1`, `::1`, or `localhost`. Cancellation is necessarily
process-based because the assessment engine has no whole-run checkpoint; if a manifest was
created, it is marked `partial` with `canceledByOperator: true`.

The frontend production build is a single HTML file with all CSS and JavaScript inline. A
local host is still required: `file://` pages cannot launch PowerShell, call Azure CLI, read
arbitrary run folders, or terminate an assessment safely.
