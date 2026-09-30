"""Capture four latest-UI walkthroughs against an isolated synthetic service.

From the repository root, after building: python .\\blog\\capture-ui-walkthroughs.py
Requires the existing Playwright browser and Pillow. Never reads live scope or credentials.
"""
import copy
import io
import json
import re
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit

from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ui" / "tests"))
from capabilities_e2e import FixtureService, fixture_config, host, ops

OUT = ROOT / "blog" / "assets"
WIDTH, HEIGHT = 1440, 900
FONT = ImageFont.truetype(r"C:\Windows\Fonts\segoeui.ttf", 22)
SMALL = ImageFont.truetype(r"C:\Windows\Fonts\segoeuib.ttf", 15)


class RecordingService(FixtureService):
    def start_validation(self, config, approvals):
        state = host.ValidationState(uuid.uuid4().hex)
        self.validations[state.data["validationId"]] = state
        titles = ["Scope and safety", "Azure inventory access", "Cost access probe",
                  "Databricks workspace access", "System-table SELECT access", "Saving readiness results"]
        state.consume("AssessmentProgress:" + json.dumps({"steps": [
            {"id": f"demo-{i}", "title": title} for i, title in enumerate(titles)]}))

        def replay():
            for i, title in enumerate(titles):
                state.consume("AssessmentProgress:" + json.dumps({"id": f"demo-{i}", "status": "running", "detail": title}))
                time.sleep(0.8)
                state.consume("AssessmentProgress:" + json.dumps({
                    "id": f"demo-{i}", "status": "pass", "detail": "Synthetic readiness response; no cloud request."}))
            state.finish({"generatedAtUtc": host.utc_now(), "blockerCount": 0, "warningCount": 0,
                          "canRun": approvals.get("approveSqlWarehouseAutoStart") is True,
                          "requiresSqlWarehouseApproval": False, "checks": [
                              {"id": "system-tables-access", "title": "System-table SELECT access",
                               "severity": "info", "status": "pass", "group": "permissions",
                               "detail": "Synthetic accessible-source responses for this recording."}]})
        threading.Thread(target=replay, daemon=True).start()
        return state.snapshot()

    def start_run(self, config, approvals):
        run_id = super().start_run(config, approvals)
        root = self.output_root / run_id
        sources = [{"name": name, "status": status, "itemCount": count, "outputs": [],
                    "limitations": [reason] if reason else [], "error": "", "domain": "azure" if name.startswith("Azure") else "databricks"}
                   for name, status, count, reason in [
                       ("Databricks compute", "passed", 31, ""),
                       ("Databricks workloads", "passed", 2, ""),
                       ("Databricks queries", "passed", 65, ""),
                       ("Databricks assets", "passed", 7, ""),
                       ("Azure cost evidence", "partial", 0, "Synthetic fixture does not include authoritative Azure cost exports."),
                       ("Databricks Spark deep dive", "skipped", 0, "No deep-dive job run IDs are selected.")]]
        ops.save(root / "collection-status.json", sources)
        manifest = ops.load(root / "assessment-manifest.json")
        manifest["status"] = "running"
        ops.save(root / "assessment-manifest.json", manifest)
        state = host.RunState(run_id, root / "assessment-config.json")
        self.runs[run_id] = state
        state.add_event({"type": "phase", "phase": "collecting", "message": "Replaying synthetic source responses.", "atUtc": host.utc_now()})

        def replay():
            for source in sources:
                time.sleep(0.7)
                state.add_event({"type": "source", "source": source, "atUtc": host.utc_now()})
            for phase in ("normalizing", "analyzing", "reporting"):
                state.add_event({"type": "phase", "phase": phase, "message": "Synthetic timeline; saved outputs use the production pipeline.", "atUtc": host.utc_now()})
                time.sleep(0.6)
            manifest.update(status="partial", completedAtUtc=host.utc_now())
            ops.save(root / "assessment-manifest.json", manifest)
            state.add_event({"type": "completed", "runId": run_id, "atUtc": host.utc_now()})
        threading.Thread(target=replay, daemon=True).start()
        return run_id


class Clip:
    def __init__(self, page, name):
        self.page, self.name = page, name
        self.frames, self.durations = [], []

    def snap(self, caption, duration=2200):
        self.page.wait_for_timeout(180)
        image = Image.open(io.BytesIO(self.page.screenshot(animations="disabled"))).convert("RGB")
        colors = self.page.evaluate("""() => {
            const s = getComputedStyle(document.documentElement);
            return ['--cp-bg-elevated', '--cp-text', '--cp-accent', '--cp-surface-soft'].map(k => s.getPropertyValue(k).trim());
        }""")
        boxes = self.page.locator("body").evaluate(r"""body => {
            const walker = document.createTreeWalker(body, NodeFilter.SHOW_TEXT), boxes = [];
            while (walker.nextNode()) {
                const n = walker.currentNode;
                if (['SCRIPT','STYLE'].includes(n.parentElement?.tagName)) continue;
                for (const m of n.textContent.matchAll(/[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}|adb-\d+\.\d+\.azuredatabricks\.net|\b\d{12,}\b/gi)) {
                    const r = document.createRange(); r.setStart(n, m.index); r.setEnd(n, m.index + m[0].length);
                    for (const b of r.getClientRects()) boxes.push([b.x, b.y, b.width, b.height]);
                }
            }
            return boxes;
        }""")
        draw = ImageDraw.Draw(image)
        for x, y, w, h in boxes:
            draw.rectangle((x, y, x + w, y + h), fill=colors[3])
        frame = Image.new("RGB", (WIDTH, HEIGHT + 78), colors[0])
        frame.paste(image, (0, 78))
        draw = ImageDraw.Draw(frame)
        draw.text((22, 8), "DEMO DATA | Synthetic readiness and collection | Latest built UI", fill=colors[2], font=SMALL)
        draw.text((22, 34), caption, fill=colors[1], font=FONT)
        self.frames.append(frame)
        self.durations.append(duration)

    def scroll(self, locator, caption):
        target = locator.evaluate("""el => {
            const content = el.closest('.content');
            return el.getBoundingClientRect().top - content.getBoundingClientRect().top + content.scrollTop - 20;
        }""")
        start = self.page.locator(".content").evaluate("el => el.scrollTop")
        for fraction in (0.5, 1):
            self.page.locator(".content").evaluate("(el, y) => el.scrollTo(0, y)", start + (target - start) * fraction)
            self.snap(caption, 220 if fraction < 1 else 2200)

    def save(self, poster=0):
        self.frames[poster].save(OUT / f"{self.name}.png")
        palette_source = Image.new("RGB", (360 * len(self.frames), 245))
        for i, frame in enumerate(self.frames):
            palette_source.paste(frame.resize((360, 245)), (i * 360, 0))
        palette = palette_source.quantize(colors=240)
        frames = [frame.quantize(palette=palette, dither=Image.Dither.NONE) for frame in self.frames]
        path = OUT / f"{self.name}.gif"
        frames[0].save(path, save_all=True, append_images=frames[1:], duration=self.durations, loop=0, optimize=True, disposal=2)
        with Image.open(path) as result:
            assert result.n_frames > 1 and result.size == (WIDTH, HEIGHT + 78)
            encoded_frames = result.n_frames
        assert path.stat().st_size < 8 * 1024 * 1024
        return {"file": path.name, "frames": encoded_frames, "capturedFrames": len(frames), "seconds": sum(self.durations) / 1000, "bytes": path.stat().st_size}


def top(page):
    page.locator(".content").evaluate("el => el.scrollTo(0, 0)")


def main():
    OUT.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="blog-ui-demo-") as directory:
        service = RecordingService(ROOT, Path(directory), ROOT / "ui" / "dist" / "index.html")
        estate = ops.load(ROOT / "ui" / "mock" / "fixtures" / "estate.json")
        selected_id = fixture_config()["databricks"]["workspaces"][0]["workspaceId"]
        for subscription in estate:
            for group in subscription["resourceGroups"]:
                group["workspaces"] = [w for w in group["workspaces"] if w["workspaceId"] == selected_id]
        host.discover_estate = lambda _: copy.deepcopy(estate)
        server = host.AssessmentHttpServer(("127.0.0.1", 0), service)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page(viewport={"width": WIDTH, "height": HEIGHT}, accept_downloads=True)
                errors, external = [], []
                page.on("pageerror", lambda error: errors.append(str(error)))
                def boundary(route):
                    if urlsplit(route.request.url).hostname != "127.0.0.1":
                        external.append(route.request.url)
                        route.abort()
                    else:
                        route.continue_()
                page.route("**/*", boundary)
                page.goto(f"http://127.0.0.1:{server.server_port}/")
                page.get_by_role("button", name="Validate configuration", exact=True).wait_for()
                expect(page.locator("nav .nav-item")).to_have_count(5)
                clips = []
                configure = Clip(page, "01-configure")
                configure.snap("Configure: start with editable IDs and a bounded assessment scope")
                configure.scroll(page.get_by_role("heading", name="Azure subscriptions", exact=True), "Select subscriptions and workspace resource groups")
                configure.scroll(page.get_by_role("heading", name="Azure Databricks workspaces", exact=True), "Select workspaces and an approved SQL Warehouse")
                configure.scroll(page.get_by_role("heading", name="Analysis modules, rules and collection profile"), "Choose Standard, Extended, or Custom collection and analysis modules")
                page.get_by_label("Collection profile").select_option("standard")
                configure.snap("Standard keeps optional asset metadata off")
                page.get_by_label("Collection profile").select_option("extended")
                configure.snap("Extended explicitly selects the seven optional asset inventories")
                configure.scroll(page.get_by_role("heading", name="Analysis window and cost basis"), "Keep Actual and Amortized costs distinct; scope the time window")
                clips.append(configure.save(poster=6))

                page.get_by_role("button", name=re.compile(r"2 Validate")).click()
                top(page)
                validate = Clip(page, "02-validate")
                validate.snap("Validate: approve warehouse use, then explicitly start readiness")
                page.get_by_role("checkbox", name=re.compile("Approve SQL Warehouse auto-start")).check()
                page.get_by_role("button", name="Run validation", exact=True).click()
                for _ in range(8):
                    top(page)
                    validate.snap("Track readiness progress without starting the assessment", 900)
                    if page.get_by_role("button", name="Continue to run", exact=True).is_enabled():
                        break
                    page.wait_for_timeout(500)
                expect(page.get_by_role("button", name="Continue to run", exact=True)).to_be_enabled(timeout=15000)
                top(page)
                validate.snap("Ready means checks passed; collection still requires its own Start action")
                validate.scroll(page.get_by_role("button", name="Continue to run", exact=True), "Continue sits beneath the validation and permission content")
                clips.append(validate.save(poster=-3))

                page.get_by_role("button", name="Continue to run", exact=True).click()
                top(page)
                run = Clip(page, "03-run-analysis")
                run.snap("Run analysis: confirm the saved scope before starting collection")
                page.get_by_role("button", name="Start read-only assessment", exact=True).click()
                for _ in range(10):
                    top(page)
                    run.snap("Follow collection phases and source outcomes; timing here is simulated", 900)
                    if page.get_by_text("Assessment finished - snapshot saved", exact=True).count():
                        break
                    page.wait_for_timeout(600)
                expect(page.get_by_text("Assessment finished - snapshot saved", exact=True)).to_be_visible(timeout=15000)
                run.snap("Finished is not the same as complete evidence: partial results remain red", 2800)
                clips.append(run.save(poster=-1))
                page.get_by_role("button", name="Visualize results", exact=True).click()
                page.get_by_text("Viewing a saved snapshot", exact=True).wait_for()

                visual = Clip(page, "04-visualize-results")
                for tab, sub, caption in [
                    ("Compute and SQL", "Utilization", "Visualize results: inspect observed utilization, not assumed savings"),
                    ("Compute and SQL", "Job health", "Review job retry and notification coverage"),
                    ("Queries", None, "Inspect query duration, queue time, failures, and grouped summaries"),
                    ("Posture", None, "Posture checks are bounded evidence, not a compliance certification"),
                    ("Assets", None, "Browse selected optional metadata without exporting notebook source"),
                    ("Findings", None, "Trace candidates to supporting evidence and limitations"),
                    ("Evidence quality", None, "See final red/green outcomes with distinct partial and skipped counts"),
                ]:
                    page.get_by_role("tab", name=re.compile(r"^Findings\b") if tab == "Findings" else tab, exact=tab != "Findings").click()
                    if sub:
                        page.get_by_role("tab", name=sub, exact=True).click()
                    if tab in ("Compute and SQL", "Queries", "Posture", "Assets"):
                        expect(page.get_by_text(re.compile("matching saved rows"))).to_be_visible()
                    visual.scroll(page.get_by_role("tablist").first, caption)
                page.get_by_role("button", name="Switch to dark mode", exact=True).click()
                visual.snap("The same saved outcomes remain clear in dark mode")
                page.get_by_role("button", name="Switch to light mode", exact=True).click()
                clips.append(visual.save(poster=0))
                page.get_by_role("button", name="Review & export", exact=True).click()
                top(page)
                expect(page.get_by_label("Reviewer")).not_to_be_visible()
                handoff = Clip(page, "review-export")
                handoff.snap("One final step: download reports, with a small optional decision form")
                handoff.frames[0].save(OUT / "review-export.png")
                with page.expect_download() as download:
                    page.get_by_role("button", name="Download report", exact=True).click()
                download.value.delete()
                expect(page.get_by_role("button", name=re.compile(r"5 Review & export"))).to_have_class(re.compile(r"\bdone\b"))
                assert not errors and not external, (errors, external)
                browser.close()
                record = {"boundary": "Isolated synthetic service; production UI/API/pipeline; no Azure or Databricks calls",
                          "workflowSteps": 5, "clips": clips, "pageErrors": errors, "externalRequests": external}
                (OUT / "walkthrough-recording.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
                print(json.dumps(record, indent=2))
        finally:
            server.shutdown()
            server.server_close()
            worker.join()


if __name__ == "__main__":
    main()
