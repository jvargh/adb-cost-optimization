# CAP-01 through CAP-13: test plan and execution record

Date: 2026-09-29. Backend: `2026.09.29.1`.
Scope: the [initial implementation described in the user guide](../USER-GUIDE.md),
not every future enhancement in the [broader UI plan](../../docs/ScannerAnalyzer-UI-Modification-Plan.md).

## Outcome and evidence boundaries

**PASS for the implemented local workflows and regression suites.**
The production React build, HTTP adapter, local server, analysis pipeline, saved results,
review and export were exercised together with Playwright.

- **Synthetic cloud boundary:** the browser harness substitutes estate discovery,
  readiness and source collection. It does not prove fresh Azure/Databricks access.
- **Real saved evidence:** an existing native snapshot was re-analyzed in temporary local
  output. All original file hashes stayed unchanged; no cloud requests were made.
- **Cloud writes:** publication success/failure was mocked at the Databricks client.
  The browser tested preview and the separate approval gate, not a live publish.
- **Production host:** the idle old host was restarted, then health, UI HTTP 200 and
  capability endpoint validation were verified. No customer scan, grants, resize,
  purchase or dashboard publication was triggered.

## Initial CAP-01 through CAP-13 suites

| Validation | Result |
| --- | --- |
| UI Vitest | 154 passed, 18 files |
| Python UI/server tests | 89 passed |
| Python assessment contracts | 15 passed |
| Python model tests | 26 passed |
| Python report tests | 4 passed |
| PowerShell/Pester | 186 passed, including parallel runspace initialization without cloud targets |
| TypeScript / Vite / self-contained build | PASS |
| Static assessment read-only scanner | PASS |
| Playwright production-stack journey | 18 recorded checks passed; zero page errors |
| Independent XLSX reader | PASS, 13 sheets, Arial headers, frozen first row, formula-like text retained as inert strings |
| Existing native snapshot compatibility | PASS; original file hashes unchanged |
| Refreshed local host | PASS, version `2026.09.29.1`, HTTP 200, expected 400 for invalid import preview |

Vite reports the existing nonblocking large-chunk warning. The self-contained bundle is
about 1.07 MB; this does not fail the build. Negative tests deliberately log denied access,
failed persistence, invalid snapshots and mocked throttling.
The three automated test families total **474 passing tests**, in addition to the
18 grouped Playwright checks and standalone native/XLSX/host checks.

## CAP acceptance matrix

| ID | Checks executed | Result and qualification |
| --- | --- | --- |
| CAP-01 | Zero vs missing; weighted CPU; workspace identity; bounded sample evidence; driver/worker selector and chart | PASS. Native saved node timeline is empty, and is shown unavailable rather than zero |
| CAP-02 | Sample adequacy, explicit single-node configuration, autoscaling metadata, unique candidate IDs | PASS. Benchmark candidates only; no automatic resize or estimated saving |
| CAP-03 | Success-only alerts do not satisfy failure routing; singleton tasks; email/webhooks; legacy redacted routing becomes Unknown | PASS. Task pagination/inheritance remains a stated limitation |
| CAP-04 | Milliseconds to seconds, invalid time exclusion, JSON-encoded SQL compute struct, 65-query paging and full-dataset grouping | PASS; real saved data contains 224 query rows |
| CAP-05 | Exactly 1,048,576 bytes/MiB and unclipped interval rate denominator | PASS; no claim of billed egress or causal diagnosis |
| CAP-06 | Missing evidence remains Unknown; observed supported checks; posture view | PASS for **two supported checks**, not a full catalog/compliance certification |
| CAP-07 | Selected metadata; default skip; denied and truncated statuses; notebook recursion; MLflow token pagination; asset screen | PASS with mocked APIs. No fresh optional-asset API collection was performed |
| CAP-08 | Review save, workbook generation, binary download, XML validity, independent reader, literal formula-like strings, oversize rejection | PASS; full-run export, not current table filters |
| CAP-09 | Invalid/unknown rules rejected; rule version saved; child analysis; failed child status; parent preserved | PASS |
| CAP-10 | Existing coverage subtracted, idle commitment charges retained, duplicate/missing inputs rejected, browser scenario | PASS for explicit saved hourly evidence. Native financial eligibility is not inferred |
| CAP-11 | Preview/confirmation, scope mismatch rejection, recursive privacy, real pipeline import, cost-unavailable UI | PASS for supported raw CSV/JSON, not aggregate-only scanner summaries |
| CAP-12 | Destination-bound preview, separate approval, viewer credentials, audit-before-write, failure/unknown persistence and retry refusal | PASS for local/mocked behavior. **Coverage-count dashboard only; live rendering unverified** |
| CAP-13 | Profiles/options UI; default sequential behavior; 1-4 bound; optional default skip; parallel worker initialization | PASS for local behavior; live concurrency throughput/throttling not benchmarked |

## Browser journey

The [reproducible Playwright harness](../tests/capabilities_e2e.py) performs:

1. Configure -> Validate -> explicit warehouse approval -> validation.
2. Assert exactly one enabled **Continue to run**; start assessment explicitly.
3. Open persisted results through the real API/pipeline.
4. Visit utilization, sizing, job health, network, queries, posture, assets and quality.
5. Page 65 queries and switch to a warehouse summary covering the full matching dataset.
6. Calculate a saved-input commitment scenario.
7. Save a review decision; generate and download a valid binary workbook.
8. Preview publication and verify publish is disabled without its own approval.
9. Import all supported fixture datasets, verify unavailable authoritative cost.
10. Create a child analysis and open its persisted results.
11. Use the actual theme toggle at 1440, 768 and 390 px; assert no page-level overflow.
12. Open the resource drawer, assert both metric curves render, and close using Escape.

The JSON has 18 named checks because related interactions above are grouped. Not every
assertion is a separate test case. Screenshots are synthetic test data, not cloud findings.
The test uses real production components, not the legacy `?mock=1` adapter.

[Machine-readable browser results](test-evidence/capabilities-e2e-results.json)
(latest browser run; subsequent verification is recorded in the follow-up sections below).

### Visual confirmation

Screenshots were captured in both themes at all three widths; desktop light, narrow
dark and the final dark utilization drawer were inspected visually. The drawer initially
was captured during animation; screenshots now disable CSS transitions and immutable
sample charts render without a startup animation.

- [Light 1440 px](test-evidence/capabilities-light-1440.png)
- [Light 768 px](test-evidence/capabilities-light-768.png)
- [Light 390 px](test-evidence/capabilities-light-390.png)
- [Dark 1440 px](test-evidence/capabilities-dark-1440.png)
- [Dark 768 px](test-evidence/capabilities-dark-768.png)
- [Dark 390 px](test-evidence/capabilities-dark-390.png)
- [Utilization drawer and rendered series](test-evidence/capabilities-utilization-detail.png)

Tables retain their own horizontal scrolling on narrow screens. These checks are not a
formal accessibility audit or exhaustive visual coverage of every state in every browser.

## Real saved-evidence compatibility

The [offline compatibility harness](../tests/capabilities_native_compatibility.py) copies
raw evidence into a temporary child, runs the complete analysis/report pipeline, loads
the production results adapter and compares every original file hash.
It leaves no child in the user's snapshot list.

[Recorded native result](test-evidence/capabilities-existing-evidence.json):

- 10 compute inventory rows, **no usable node utilization/network samples**.
- 26 job rows and 224 query rows.
- Six posture check rows across three workspaces.
- Optional asset and commitment inputs unavailable in this historical evidence.
- 14 capability findings; these are **candidates, not approved recommendations**.

This check caught actual native schema issues that the first synthetic fixtures missed:
SQL structs serialized as JSON strings, singleton task objects and opaque legacy
email-notification hashes. Regression cases now cover all three. New collectors retain
notification shape and hash recipients; old evidence is not rewritten.

## Other defects found and fixed during testing

- Optional asset defaults emitted a null selection and incorrectly accessed absent scope.
- Saved-snapshot tests needed to acknowledge the intentional New assessment confirmation.
- Nullable imported cost values were not reflected in all TypeScript contracts.
- Report/backlog/sign-off exports used detector IDs where per-resource finding IDs were needed.
- Commitment rows shared keys across different hours.
- A transient re-analysis error-path edit was caught and corrected by operation tests.
- Workbook failure could leave a partial temp file; writes now use unique atomic temp paths.
- Import privacy now preserves nested notification routing while protecting recipients.
- Pester expectations were corrected to distinguish aggregate `partial` from source `failed`,
  to parse native NDJSON rather than a JSON array, and to supply the normal redaction config.

## Partial/skipped indicators and final-state remediation

Follow-up executed 2026-09-29 against the current built UI and collectors.
This is a focused regression run, not a rerun of all 474 initial-delivery tests.

The real saved 16:30 UTC assessment contains **22 passed, 4 partial, 4 skipped**
collector results. The four partials are jobs redaction and oversized audit SQL in
two workspaces each. The four skips are three unselected Spark deep dives and one
unselected optional-asset inventory. Separate Azure governance collectors passed;
the Databricks-only Azure-governance skip note is not a permission failure.

| Validation | Result |
| --- | --- |
| Targeted UI suites: outcomes, snapshots, navigation, validation progress, permission setup | **56 passed** |
| Pester collector contracts, capabilities, partial recovery | **66 passed**, including 11 recovery regressions |
| Python backend/snapshot regression module | **39 passed** |
| TypeScript, Vite, self-contained production build | PASS; existing bundle-size warning only |
| Static read-only scanner | PASS |
| Playwright production UI/API fixture | **4 red/green x light/dark cases passed**, reload persistence, exact counts, visible skip reasons, zero page errors/write requests |
| Playwright actual saved snapshot on port 8765 | PASS: red final outcome and red Validate/Run steps; exact 22/4/4 counts preserved after reload |
| Historical evidence integrity | Original manifest and collection-status hashes unchanged; no cloud collection or permission writes |

Collector regressions reproduce empty JSON notification objects and the real-shaped
SQL `FAILED` / `BAD_REQUEST` inline-limit response through dataset persistence.
They verify non-overlapping time boundaries, bounded attempts, explicit partial
coverage when the bound is hit, permission errors remaining errors, unrepresentably
small windows remaining failures, SQL manifest truncation, recipient privacy, and
intentional skips not degrading an otherwise completed run.

The final saved banner is red for incomplete/missing evidence and green only when
the recorded run and collected checks support success. It does not manufacture
pre-run validation proof. Individual partial/skipped badges and limitations remain
visible rather than being recolored as passes. Live completion uses the same
source-outcome logic; validation blockers also produce a red navigation state.

Evidence: [browser results](test-evidence/source-outcomes.json),
[red/light screenshot](test-evidence/source-outcome-red-light.png),
[green/light screenshot](test-evidence/source-outcome-green-light.png),
[red/dark screenshot](test-evidence/source-outcome-red-dark.png),
[green/dark screenshot](test-evidence/source-outcome-green-dark.png).
The real-customer screenshot is retained in the local session, not copied into these fixtures.

**Boundary:** size-limit recovery was tested against simulated Databricks responses,
not a fresh billable SQL scan. The actual saved snapshot remains partial until a new
assessment collects missing evidence. No permissions, optional selections, or
historical source statuses were changed. The running backend was not restarted.

Reproduce the focused browser check after building:

```powershell
python .\ui\tests\collection_status_e2e.py
```

## Follow-up: minimal review/export and current blog recordings

Executed 2026-09-29 against the rebuilt production UI. The workflow now has five
steps, ending in **Review & export**. Report download and preview are immediate;
the optional review is collapsed and edits one finding's decision, reviewer and note.
Downloads do not approve pending findings.

| Validation | Result |
| --- | --- |
| Targeted review/export, workflow, snapshots and capability tests | **32 passed** |
| Full UI regression suite | **169 passed, 20 files** |
| TypeScript / Vite / self-contained production build | PASS; existing bundle-size warning only |
| Playwright production-stack capability journey | **18 grouped checks passed**, zero page errors |
| Four-stage Playwright recording | PASS; five sidebar steps, explicit Validate/Run actions, capability views in both themes, download without review |
| Running local host on port 8765 | PASS; five-step navigation, visible Download report, collapsed review, no write requests |
| Media inspection | All GIF frames decode; first/middle/last frames and five full-size stills visually inspected |
| Blog links | All 11 local media links resolve; exactly the four requested current GIFs |

The new [review/export regression tests](../tests/reviewExport.test.tsx) cover
export without review, saving a single decision while preserving historical detail
and other findings, required-reviewer validation, visible persistence errors with
retryable drafts, and blocking reload-causing workbook actions until edits are saved
or discarded. Workflow regressions check completion on download, not mandatory sign-off.

The [recording script](../../blog/capture-ui-walkthroughs.py) uses the production UI,
local HTTP API and analysis pipeline with an isolated synthetic collection service.
Every frame is labeled DEMO DATA. Timings are replayed for readability, not measured
cloud performance. Recorded browser errors and external requests are both empty.
No customer snapshot, grant, cloud collection or live publication was changed.

All four GIFs are **1440 x 978**, including captions, and below 1 MiB each:

| Clip | Encoded frames | Duration | Bytes |
| --- | --- | --- | --- |
| [Configure](../../blog/assets/01-configure.gif) | 11 | 16.28 s | 616,646 |
| [Validate](../../blog/assets/02-validate.gif) | 11 | 14.02 s | 633,218 |
| [Run analysis](../../blog/assets/03-run-analysis.gif) | 11 | 13.10 s | 570,651 |
| [Visualize results](../../blog/assets/04-visualize-results.gif) | 12 | 19.14 s | 769,393 |

GIF encoding merges identical adjacent captured frames while preserving their total
duration. The [recording metadata](../../blog/assets/walkthrough-recording.json)
distinguishes captured from encoded frame counts. The
[merged-step still](../../blog/assets/review-export.png) shows immediate downloads and
the collapsed optional review.

Reproduce the browser journey and media capture after building, with the existing
Python Playwright/Chromium and Pillow dependencies:

```powershell
python .\ui\tests\capabilities_e2e.py
python .\blog\capture-ui-walkthroughs.py
```

## Follow-up: rendered report preview and direct navigation

Executed 2026-09-29. **Preview report** now opens and focuses the preview immediately,
shows loading or failure in that section, and scrolls back to the preview on repeated
clicks. Markdown renders as styled HTML rather than raw source. Other text artifacts
and original report downloads retain their existing formats.

| Validation | Result |
| --- | --- |
| Preview, review/export, workflow, snapshots and capability regressions | **42 passed, 5 files**, including 10 focused preview cases |
| TypeScript / Vite / self-contained production build | PASS; existing bundle-size warning only |
| Playwright preview journey | **6 grouped checks passed**, zero page errors, external requests or write requests |
| Desktop light/dark and 390 px mobile | PASS; preview focused within 40 px of content top, no page overflow |
| Report contents | All **17** links resolve; numbered sections also support older shortened labels and punctuation |
| Existing local host / real saved report | PASS; HTML rendering, preview at 16 px below content top, all 17 targets present, legacy section 7 navigation, no errors or write requests |

The [focused unit tests](../tests/reportPreview.test.tsx) cover loading, rendered
headings/tables/code, repeat navigation from either preview action, section links,
local supporting CSV previews, rejected embedded HTML/unsafe URLs and omitted remote
images, visible read errors with retry, and late responses after close, another request
or a snapshot change. Previewing does not mark a report as downloaded.

The [browser harness](../tests/report_preview_e2e.py) uses isolated synthetic evidence
with the production UI, API and report pipeline. The separate existing-host check only
read an already saved report; it did not recollect data, alter customer artifacts, grant
permissions or restart the backend.

- [Recorded browser results](test-evidence/report-preview-results.json)
- [Desktop light preview](test-evidence/report-preview-light-1440.png)
- [Desktop dark preview](test-evidence/report-preview-dark-1440.png)
- [Mobile preview](test-evidence/report-preview-light-390.png)
- [Formatted tables and section navigation](test-evidence/report-preview-section.png)

The desktop, dark, mobile and section screenshots were visually inspected.

```powershell
python .\ui\tests\report_preview_e2e.py
```

## Reproduce

From the workspace root (dependencies for the existing project already installed):

```powershell
Set-Location .\ui
npm test
npm run typecheck
npm run build
Set-Location ..
python -m unittest discover -s ui\server -p "test_*.py"
python -m unittest discover -s assessment\tests -p "test_*.py"
python -m unittest discover -s assessment\tests\model -p "test_*.py"
python -m unittest discover -s assessment\tests\reports -p "test_*.py"
$r = Invoke-Pester -Path .\assessment\tests -PassThru
if ($r.FailedCount) { throw "Pester failed" }
.\assessment\scripts\Test-AssessmentReadOnly.ps1 -Path .\assessment
python ui\tests\capabilities_e2e.py
python ui\tests\capabilities_native_compatibility.py "<existing native run root>"
```

Playwright Python/Chromium and Pester are test prerequisites, not production runtime
dependencies. The standalone XLSX check used openpyxl 3.1.5 in an isolated session-only
test-dependency directory after the reader was found missing; no application dependency
was added. It loaded the generated workbook, checked all 13 sheets, styles and frozen
headers, and asserted there were no formula cells.

## Unverified / broader-plan work

Do not interpret green local tests as proof of:

- Live optional asset API availability, tenant permissions, throttling behavior or concurrency performance.
- Live Lakeview payload acceptance/rendering in a specifically authorized destination.
- Full scanner posture-category/check parity, published detailed analytics datasets, or
  automatically derived financially authoritative commitment demand.
- A new pre-run per-module permission matrix, dedicated local-operation cancellation, or
  complete URL persistence of every filter/subview.
- CAP-14 detailed Spark stage/task/executor analysis.

These are documented boundaries, not silently marked passing requirements. This release
uses the existing live readiness/collector progress and adds **post-collection** workspace
capability coverage. No additional cloud writes should be attempted just to make this
record appear fully live-validated.
