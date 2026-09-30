# Azure Databricks Cost Optimization — UI

> **Production UI.** This app runs the complete journey — Configure → Validate → Run
> analysis → Visualize results → Review & export — over the existing PowerShell/Python
> assessment toolkit. An explicit `?mock=1` mode retains the approved deterministic demo.

The UI is an orchestration and visualization layer over the existing read-only toolkit,
not a second assessment engine. The collectors also emit optional progress events for the
UI; their evidence and assessment logic remain in [`assessment/`](../assessment).

The authoritative behavioural baseline is
[AzureDatabricksCostOptimizationEndToEndSpecification.md](../docs/AzureDatabricksCostOptimizationEndToEndSpecification.md).

## New capability workflows

Read the [UI user guide](USER-GUIDE.md) for utilization, sizing, job/query/network analysis,
posture, assets, offline import, versioned re-analysis, commitments, XLSX and optional
dashboard publication. The [test plan and recorded results](docs/capabilities-test-plan.md)
include Playwright screenshots and distinguish synthetic, saved-native and live checks.

Assessment remains read-only. Optional dashboard publication is a separate, explicitly
confirmed cloud write and currently publishes coverage counts only. Posture currently
contains two supported checks, not a full compliance catalog. See the guide's boundaries.
Restart an idle local host after updating backend files; frontend rebuild alone is insufficient.

---

## Run it

From the repository root, run one command:

```powershell
.\ui\Start-AssessmentUi.ps1
```

The command starts a loopback-only host at `http://127.0.0.1:8765` and opens the browser.
Press **Ctrl+C** in PowerShell to stop it. Use `-NoBrowser`, `-Port`, or `-OutputRoot` when
needed. The browser UI is one self-contained `dist/index.html`; the small local host is
still required because a browser cannot run PowerShell, call Azure CLI, cancel a child
process, or safely read assessment folders by itself.

The browser-tab icon is an original descending cost chart in the UI's rose accent.
Its SVG source is [`src/assets/favicon.svg`](src/assets/favicon.svg); the production build
embeds it in the HTML so it also works offline without a separate favicon request.

Runtime prerequisites are PowerShell 7, Python 3, Azure CLI, and an active `az login`.
No Node server is used at runtime. Node/npm are needed only to rebuild or test the UI.
Only one host can listen on a given port. If it is already in use, reopen the existing
browser app or stop that launcher before restarting; do not run overlapping assessments.

If Configure says that the live Azure scope could not be loaded, run:

```powershell
az logout
az login --tenant 5bb5fa45-2dcc-4310-bbc5-883021e9d84b
```

Then return to the page and select **I have signed in — retry discovery**. You do not need
to restart the browser application.

| Command | What it does |
| --- | --- |
| `.\ui\Start-AssessmentUi.ps1` | Starts the production UI and local API |
| `npm run dev` | Runs the approved fixture-backed development UI on port 5180 |
| `npm test` | Vitest suite, including saved-snapshot navigation and reload |
| `npm run typecheck` | Runs `tsc --noEmit` |
| `npm run build` | Builds and inlines all frontend assets into `dist/index.html` |
| `python -m unittest discover -s server -p 'test_*.py'` | Runs the local-host tests, including snapshot persistence |
| `npm run fixtures` | Regenerates the deterministic mock fixtures |

To open the approved offline demonstration from the production host, add `?mock=1` to its
URL. Mock mode never calls Azure or Databricks.

**Use a window at least 1400 px wide.** The results tabs put a filter rail beside dense
tables and charts; below roughly 1200 px the layout still works but reads as cramped.

Use the **Light / Dark** switch in the top-right corner to change themes. The preference is
retained for the next visit when browser storage is available. Both themes use the same
semantic status colors and preserve readable chart labels, table borders, callouts, and
disabled states.
Informational callouts use neutral surfaces, borders, and icons rather than the
rose action accent. Warning callouts remain amber and error callouts remain red.

Workflow steps stay gray while uncompleted, turn green for successful completion,
and red when completed validation/collection needs attention. Step numbers never become
checkmarks. An outline identifies the page being viewed without implying completion.
Configure completes when its local fields and scope are valid; live Validate uses
backend readiness. Completed collection with partial/failed/pending or unrecorded
source evidence is red, not a green success. Intentional skips alone do not fail a run.
Visualize completes when results load; the combined Review & export step completes
after a download. Its collapsed, optional review records a selected finding's decision,
reviewer and note without requiring full sign-off before export. Warnings remain visible.

Selecting a subscription, or first loading a setup with a subscription already selected,
automatically selects its discovered resource groups containing Azure Databricks workspaces
and includes newly discovered workspaces. Groups with no discovered
workspaces remain unchecked. You can deselect groups or individual workspaces; selecting
another subscription preserves those choices. Associated managed groups are still added
by the collector. For workspaces without a choice, the UI selects the smallest running
SQL Warehouse, or the smallest stopped warehouse if none is running. Existing choices
and an explicit **None** are preserved. Listing and selection do not start compute.
Warehouse approval remains unchecked on initial live load and resets when the included
workspace/warehouse targets change.
Legacy global Warehouse IDs are retained only on previously configured workspaces.

Selections carry subscription-qualified resource-group IDs, so same-named groups in
different subscriptions remain independent. Deselecting a subscription removes only its
groups/workspaces and updates the cost scopes. Initial defaults apply once, after successful
discovery; subsequent discovery/sign-in retries keep manual selections, edits, and approvals.
Saved snapshots retain their original scope and never receive these defaults.
Scope changes invalidate readiness but never start validation or collection.

### Saved snapshots

To start over, select **New assessment** in the header. This clears the current
results, filters, review/export UI state, run progress, validation, and approvals,
then opens **Step 1: Configure**. Customer and assessment IDs are prefilled as
`customer-<random suffix>` and `assessment-<random suffix>`. The analysis window covers
the previous 30 complete UTC days, ending at today's midnight UTC. All are editable;
no typing is needed to keep these defaults. Each fresh setup generates new IDs.
Scope selections and warehouse/deep-dive targets are cleared; tenant connection settings
and installation defaults for output remain available. Select the scope before validating
and explicitly starting a run.

The action removes `?run=...` and sets `?new=1`, so subsequent browser refreshes
stay on a fresh Configure screen instead of reopening the old snapshot.
It never deletes snapshots or saved review decisions and does not start validation
or collection. It is disabled while discovery, sign-in, validation, or a run is active.

Every assessment writes a unique run folder automatically, including partial runs.
There is no separate Save step. Use the **Saved snapshots** dropdown beside the
**Light / Dark** toggle. It lists every recorded snapshot, newest collection timestamp
first, with the customer, status, and run ID. Selecting one opens its results immediately.
The list refreshes when a run finishes and when the dropdown receives focus.

The dropdown remains available on every workflow screen. The selected run ID is
kept in the page URL, so refreshing or bookmarking that URL reopens the same saved run
without Azure discovery, readiness, or collection calls. Review decisions and exports
remain attached to that run. Opening history does not authorize or start a new run.

Snapshots survive browser and host restarts in the configured output folder
(`assessment/output` by default). Restart with the same `-OutputRoot` to see the same
history. These are local evidence folders, not off-machine backups; protect and retain
them as customer data. Incomplete or missing artifacts are reported as errors rather
than reconstructed by silently collecting again.

While a snapshot is selected, Configure, Validate, and Run show its **historical scope
and collection checks**, not the current setup or a live progress screen. The final
green/red banner and the saved Validate/Run indicators reflect recorded collection
outcomes, with separate passed/partial/failed/pending/skipped counts. Validate is
labeled **Saved collection checks**, not pre-flight. Older runs do not contain a separate
pre-run validation report; the UI does not manufacture one or run validation to replace it.
An independently started live operation is labeled separately.
Choose **New assessment** to leave history and configure fresh collection.

**Manage snapshots**, next to the dropdown, supports **Delete snapshot** for one run and
**Delete all snapshots** for the displayed history. Both require a second **Permanently
delete** confirmation listing the exact run IDs. This removes their local folders,
including raw evidence, reports, exports, and review decisions; it cannot be undone.
Nothing is deleted merely by opening the manager or canceling confirmation. Snapshots
arriving after confirmation opens are not part of that deletion.

Deletion is unavailable during live work in this browser; the server also rejects active
or unfinished runs. Only individually verified run folders under the configured output
root may be removed. The root, configuration, readiness folders, and linked/junction
directories are protected. Per-run failures stay visible, including partial disk failures.
Deleting the open snapshot clears its results and URL without starting validation,
discovery, or collection. Demo-mode deletion affects only the in-memory fixture session.

### Validation progress and waiting times

Validation starts only from **Validate configuration**, **Run validation**, or an explicit
retry/re-run button. Opening Step 2, changing scope/approvals, selecting a snapshot, or
refreshing a snapshot URL never starts it automatically. Changes invalidate readiness
and require another explicit validation before a new run.

Step 2 keeps approvals and **Run/Retry/Re-run validation** above the progress and results.
The start control stays in place while validation runs, disabled as **Validation running...**;
approvals are also locked during live validation or permission setup. Only **Continue to run**
is below the validation and permission panels. This keeps progress beneath the initiating
action and the next-stage action after the checks.

**Re-run validation** asks for confirmation before replacing the current checks and starting
again. Cancel keeps the results and **Continue to run** available. Returning from Configure
with an unchanged, already-validated setup opens those results instead of rerunning checks.
Configuration and saved snapshots are not cleared by a validation rerun.

Step 2 first checks engagement IDs, scope, analysis dates, output settings, and SQL
approvals locally. Missing fields appear as named blockers with a **Back to Configure**
action; no PowerShell job or cloud call starts while configuration is invalid.
New assessments supply valid IDs and dates automatically. If those values are cleared
or changed to invalid values, local checks explain what to correct. Once these checks
pass, Step 2 performs real read-only source checks. Allow
several minutes. Larger scopes, Azure API retries, and approved SQL Warehouse queries can
take longer. It does not generate findings or the final report; step 3 does that.
Changing workflow steps resets the content scroll position so the validation summary
is visible even when Configure was scrolled to the bottom.
For Cost Management, readiness now issues only a one-day aggregate access probe per
scope, not the full resource/meter query for every cost basis and date window. A successful
probe is an informational **access probe passed** result; it does not certify the full
period or remove the partial-coverage status from the underlying collection artifacts.
Validation groups shared causes across collectors and workspaces into actionable warnings,
with expandable source responses. A missing SQL Warehouse means **SQL-backed evidence was
not checked**, not that telemetry is absent. Missing account settings remain a coverage
warning. Explicitly unsupported Azure diagnostic-setting resource types are informational
and not applicable. Permission failures, throttling, and unknown failures remain warnings;
validation never grants access or approves billable SQL starts automatically.
Configure names every included workspace without a SQL Warehouse and provides a separate
warehouse dropdown for each. The final readiness warning names affected workspaces while
retaining the original source responses. A selected warehouse requires CAN USE plus the
relevant Unity Catalog read privileges; leaving None selected explicitly limits SQL coverage.

### Optional pipeline timeline permission setup

This is a separate security-changing action in live **Validate**, not part of the read-only
assessment. It is unavailable in historical snapshots and demo mode.

1. Review each SQL Warehouse selection in Configure.
2. Explicitly approve SQL Warehouse use in Validate. Even identity verification can start
   a stopped warehouse and incur DBU charges. This approval does **not** approve grants.
3. In **Pipeline timeline permission setup**, choose the workspace and select
   **Check access and preview grants**. This runs identity verification followed by
   `SELECT 1 FROM system.lakeflow.pipeline_update_timeline LIMIT 1`.
4. If **Already accessible - no grants needed** appears, stop here: no permission change
   is needed for this source, and no grant-application controls are offered. A successful query with
   zero rows still proves read access. Only an explicit permission denial opens a preview.
5. When access is missing, review the verified signed-in assessment identity, target, and exact three statements:
   `USE CATALOG` on `system`, `USE SCHEMA` on `system.lakeflow`, and `SELECT` on
   `system.lakeflow.pipeline_update_timeline`. Check the separate confirmation and select
   **Apply these three grants**, or cancel without granting.
6. After grants succeed, explicitly run validation again. Setup never starts validation
   or an assessment automatically.

The green access result includes **Next: full validation, then assessment** guidance.
Use **Run/Re-run validation** above the progress area, then **Continue to run** beneath
the permission panel. Pipeline-table access alone does
not unlock collection: continuation requires full validation to allow it. If validation
is already running, the panel says so and prevents a duplicate request. Re-running an
existing report still requires confirmation. Continue opens step 3, where **Start read-only
assessment** remains a separate action; there is no need to start a new assessment.

Expand **Manual permission repair commands** for copyable SQL grants, a read-only
verification query, and an optional Azure CLI/PowerShell 7 administrator-assignment script.
Commands use the current target's verified identity; changing workspace or warehouse
requires another access check. Opening/copying the guide never executes its commands.
Successful access retains the guide as reference only, not a recommendation to change roles.
Active work, unknown outcomes, and non-permission failures do not offer manual changes.

Prefer an existing authorized administrator to run the SQL grants. The optional PowerShell
command is only for an authorized Databricks Account Admin establishing a metastore
administrator where the current owner is `System user`. It requires valid Databricks
Account ID/host settings, checks the signed-in identity/account role, discovers the selected
workspace's metastore, refuses to replace an assigned administrator, and requires typing the
metastore ID before the account-level PUT. It assigns the verified identity, not a group:
this is broad, persistent authority over all catalogs and attached workspaces, with no
automatic rollback. Prefer a designated administrator group through the account console
for ongoing administration. Tokens stay in memory. After any interrupted mutation, inspect
actual ownership before retrying. Verify table access as the assessment identity, not just
the administrator, then check access and explicitly re-run validation in the UI.

Table-not-found errors, query timeouts, and other non-permission failures stop with an
explicit error instead of recommending grants. Switching targets hides a previous target's
success until the newly selected workspace and warehouse are checked.

The preview expires after five minutes. Identity is checked again before any grant; a
changed identity aborts without granting. The signed-in identity must already have grant
authority. There is no administrator login, role elevation, arbitrary-principal input, or
broader grant. Grants may affect other workspaces sharing the metastore.

Failure stops subsequent grants; earlier grants may remain applied. There is no automatic
retry or rollback. Use **Check setup status** after a lost response, not a repeated apply.
An explicit Databricks rejection marks that grant **failed** and leaves later grants
**not attempted**. A transport interruption instead keeps a submitted grant's outcome
unknown. A `MANAGE`/grant-authority denial requires an authorized Unity Catalog administrator
to apply the displayed SQL; an admin-looking username or Azure role is not sufficient.
Previewing or canceling grants preserves completed validation; attempting to apply them
invalidates it.

The local audit is stored under `assessment/output/.ui-server/permission-setup/<setupId>.json`
(or the configured output root). It records the principal, target, statements, and step
outcomes, never access tokens. Treat it as sensitive operational data. After a host restart,
status checks recover saved terminal results without submitting SQL. Unused previews are
invalidated and require fresh identity verification. Interrupted applications with submitted
steps remain unknown, not successful or automatically retried.

If status cannot be obtained, the spinner stops and the panel explains that checking has
stopped. Use **Check setup status**, or inspect the audit and actual permissions before
acknowledging an unknown outcome. A stale preview rejected with HTTP 404 allows a new preview
without claiming grants succeeded. Active or unresolved setup blocks new live work.

### Workspace-specific deep-dive targets

Each included workspace has its own Job run IDs
and Table names fields. When loading a legacy single-workspace configuration, its global
targets move to that workspace before scope is expanded, so they are not queried in newly
selected workspaces. An ambiguous multi-workspace legacy configuration requires assigning
the old lists to a workspace or clearing them. Blank per-workspace lists skip only that
optional deep dive; they do not imply that Spark evidence passed. Manual edits survive
discovery retries and never start validation. Saved snapshot configuration is unchanged.

Configure includes optional **Databricks account settings**. Supply both an account UUID
and an accounts hostname (without `https://` or a path); live validation still verifies
access. Correct account settings enable account workspace inventory and the v2.1 budgets API.
Azure governance is green when applicable checks succeed, even when some resource types
explicitly do not support diagnostic settings. An entirely inapplicable check stays neutral.
OPEN catalogs do not need a workspace-binding API call; ISOLATED and unknown modes do.
Each affected progress check includes its remedy and expandable source response.

Two warnings require action outside this app: missing `SELECT` on
`system.lakeflow.pipeline_update_timeline` needs an authorized administrator, and full Spark
stage/task/executor metrics require separate Spark UI or event-log review. Selecting a job
run collects metadata and cluster events, not those detailed metrics; there is no event-log
importer. Neither limitation is hidden or automatically turned green.

- A live count (for example **4/16 checks completed**) and an ordered list show what has
  finished, what is running, and what is waiting. Each source category covers all selected
  workspaces. The count includes warnings, failed checks, and unavailable checks, not just passes.
- Elapsed time, time on each check, and an approximate remaining-time range are shown.
  The ETA is a rough planning allowance, not historical performance or a deadline. A slow
  check changes it to **Unknown**, rather than counting down to a false zero.
- Server responsiveness is separate from check activity. A responsive server can still be
  waiting on Azure. Missing server responses fail after 15 seconds instead of spinning forever.
- The progress summary remains visible across Configure, Run, and Visualize. Sidebar text
  identifies **Running**, **Waiting for validation**, and **Not started**. Completed steps
  are green; unfinished steps remain gray.
- A connection failure does not automatically restart validation. Check the launcher window
  before selecting **Retry validation**: the previous process may still be running.
- If PowerShell exits before emitting progress, its blocking report is still shown,
  including the actual startup error. No source checks are claimed to have run.
- Changing scope or approvals during validation invalidates its result. Revalidate the new
  selection before starting analysis.
- Use Saved snapshots for previous assessments rather than repeating validation and collection.

Cost Management requests are paced at least 20 seconds apart within a collector process.
HTTP 429 retries honor the largest server cooldown header and use a 60/120/240-second
fallback with jitter, rather than 2/4/8 seconds. Exhausted throttling stops further cost
windows/bases/scopes while preserving complete windows already obtained. A server
cooldown over ten minutes stops the cost query instead of retrying early.
These safeguards reduce request pressure; they cannot guarantee that Azure's shared
quotas will accept a request. A saved partial snapshot remains partial until a later,
explicit assessment obtains new evidence.

Keep the launcher window open while using the app. If the server is stopped, restart
`.\ui\Start-AssessmentUi.ps1` and refresh the browser. An already-open page is not proof that
the local server is still running.

Prerequisites: Node 20+ (developed on 25) and npm 10+. Python is only needed if you want
to regenerate fixtures; the generated JSON is committed, so a fresh clone needs only npm.

---

## Offline demo walkthrough

The `?mock=1` mode ships three scenarios because a demonstration that only shows the happy path
hides exactly the behaviour this toolkit exists to get right: what the screen says when the
evidence is incomplete. Switch between them from the yellow prototype banner at the top of
any screen, or from the **Demo scenarios** panel on Configure and Visualize results.

### 1. `Contoso — multi-subscription estate (partial)` — the default, and the realistic case

Four workspaces across three subscriptions. Several collectors return `partial` or
`pending telemetry`. Start here and walk all five steps.

- **Configure** — pick subscriptions and resource groups, set the analysis window and cost
  basis, choose deep-dive targets and the output root. The SQL Warehouse field is
  deliberately awkward: filling it in raises a blocker until you tick the auto-start
  approval, mirroring the `-ApproveSqlWarehouseAutoStart` guard in the CLI.
- **Validate** — pre-flight shows blockers separately from warnings. Resolve the blocker to
  unlock **Run analysis**. Warnings never block; they annotate the run.
- **Run analysis** — the pre-flight card restates the effective scope and every safety
  statement before anything executes. Launch, then watch the phase track advance through
  collection → normalization → analysis → findings → report.
- **Monitor** — the live console streams per-source status. Note the summary line
  ("23 of 37 sources fully passed") and that `partial`, `pending telemetry` and `skipped`
  are each rendered distinctly rather than collapsed into "error".
- **Visualize results** — grouped overview, technical, and decision views. Open **Findings**, click any row for the evidence
  drawer, then open **Filters** and apply a workspace chip: the Findings tab badge recounts
  to match the filtered set, and estate-wide findings correctly drop out of a
  workspace-scoped view.
- **Review & export** — download or preview the consolidated report immediately,
  alongside supporting artifacts and optional workbook generation. A collapsed
  **Record a decision** form edits a selected finding, reviewer and optional note.
  Downloads do not require review and do not approve pending findings.

### 2. `Contoso — single workspace (all sources passed)`

The clean path. Every collector succeeded, confidence is high, and two findings already
carry a recorded review decision so you can see the post-sign-off state.

### 3. `Fabrikam — cost collection failed`

The signed-in principal lacks Cost Management Reader. This is the scenario worth the most
review attention:

- The executive KPIs read **"Not available"**, never `$0`.
- Each card names the missing source rather than showing an empty chart.
- The **Cost analysis** tab replaces itself with an explicit "No cost evidence for this run"
  callout instead of drawing a zero-valued series.
- Estimated savings reads **"Not estimated"**, consistent with the rule that savings are
  never claimed without human validation.

Screenshots of every screen in all three scenarios are in [docs/screens](./docs/screens).

---

## Production integration

Production builds use `HttpAssessmentBackend` and the standard-library Python host under
`server/`. The host invokes `assessment/Invoke-Assessment.ps1`, streams its status, and maps
its persisted JSON/NDJSON/CSV/Markdown artifacts. It does not recalculate cost, duplicate a
detector, or modify Azure or Databricks resources. The ambient Azure CLI sign-in is reused;
no credential or token is stored by the UI.

The local API binds only to loopback. Run IDs and artifact paths are constrained to the
configured output root. Review decisions are stored atomically as `.ui-review.json` and
written to `reports/human-validation-sign-off.csv` for export. Cancellation terminates only the tracked assessment child process and
marks any persisted manifest as operator-cancelled and partial.

See [docs/architecture.md](./docs/architecture.md) for the implemented routes and boundaries.

---

## Guardrails this UI preserves

- **Read-only.** There is no control anywhere that mutates an Azure or Databricks resource.
- **Scope isolation.** Collection is bounded by the selected subscriptions and resource
  groups; the UI cannot widen it after validation.
- **SQL Warehouse auto-start requires explicit approval**, because reading system tables can
  start a warehouse and incur DBUs.
- **Absent evidence is reported, never rendered as zero.** This is enforced in
  `lib/format.ts` and covered by tests.
- **Partial and failed sources are always named**, never summarized away.
- **No savings figure is presented as fact** without a recorded human validation.
- **No remediation.** Findings and a roadmap are produced; nothing is applied.

---

## Status

- [x] Phase 1 mock approved after human review and incorporated feedback.
- [x] Phase 2 production adapter, loopback host, single-file bundle, persisted-run mapping,
      review/export support, and one-command launcher implemented.
- [x] Verified with 60 UI tests, 15 server tests, a clean production build, API smoke tests,
      real persisted assessment artifacts, and browser checks.
