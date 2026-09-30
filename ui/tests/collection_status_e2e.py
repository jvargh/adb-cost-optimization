"""Saved source outcomes through the production UI/API; synthetic cloud boundary."""
import json
import re
import tempfile
import threading
from pathlib import Path

from capabilities_e2e import FixtureService, ROOT, fixture_config, host, ops
from playwright.sync_api import expect, sync_playwright


def main():
    evidence = ROOT / "ui" / "docs" / "test-evidence"
    evidence.mkdir(exist_ok=True)
    checks = []
    with tempfile.TemporaryDirectory(prefix="source-outcomes-") as folder:
        service = FixtureService(ROOT, Path(folder), ROOT / "ui" / "dist" / "index.html")
        cases = []
        for incomplete in (True, False):
            run_id = service.start_run(fixture_config(), {"approveSqlWarehouseAutoStart": True})
            root = service.output_root / run_id
            sources = [
                {"name": f"Synthetic source {i}", "status": "partial" if incomplete and i < 4 else "passed",
                 "itemCount": 1, "outputs": [], "limitations": ["Synthetic evidence gap"] if incomplete and i < 4 else [], "error": ""}
                for i in range(26)
            ]
            sources.extend({"name": f"Optional source {i}", "status": "skipped", "itemCount": 0,
                            "outputs": [], "limitations": ["Not selected"], "error": ""} for i in range(4))
            ops.save(root / "collection-status.json", sources)
            manifest = ops.load(root / "assessment-manifest.json")
            manifest["status"] = "partial" if incomplete else "completed"
            ops.save(root / "assessment-manifest.json", manifest)
            cases.append((run_id, incomplete))
        server = host.AssessmentHttpServer(("127.0.0.1", 0), service)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                page = browser.new_page(viewport={"width": 1600, "height": 1000})
                errors, writes = [], []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.on("request", lambda request: writes.append(request.url) if request.method != "GET" else None)
                for run_id, incomplete in cases:
                    color = "red" if incomplete else "green"
                    expected_class = "attention" if incomplete else "done"
                    url = f"http://127.0.0.1:{server.server_port}/?run={run_id}"
                    page.goto(url)
                    for attempt in range(2):
                        if attempt:
                            page.reload()
                        validate = page.get_by_role("button", name=re.compile(r"2 Validate"))
                        expect(validate).to_have_class(re.compile(rf"\b{expected_class}\b"))
                        expect(page.get_by_role("button", name=re.compile(r"3 Run analysis"))).to_have_class(re.compile(rf"\b{expected_class}\b"))
                        validate.click()
                        banner = page.locator(".callout-danger" if incomplete else ".callout-ok")
                        expect(banner).to_contain_text("Assessment completed -")
                        expect(banner).to_contain_text("22 passed; 4 partial;" if incomplete else "26 passed; 0 partial;")
                        expect(banner).to_contain_text("4 skipped.")
                        expect(page.get_by_text("Not selected", exact=True).first).to_be_visible()
                        expect(page.get_by_text("Historical snapshot - no checks are running")).to_have_count(0)
                    for theme in ("light", "dark"):
                        toggle = page.get_by_role("button", name=f"Switch to {theme} mode")
                        if toggle.count():
                            toggle.click()
                        background = banner.evaluate("(element) => getComputedStyle(element).backgroundColor")
                        channels = [int(value) for value in re.findall(r"\d+", background)[:3]]
                        assert (channels[0] > channels[1]) if incomplete else (channels[1] > channels[0]), background
                        filename = f"source-outcome-{color}-{theme}.png"
                        page.screenshot(path=str(evidence / filename))
                        checks.append({"outcome": color, "theme": theme, "reloadPreserved": True,
                                       "skipped": 4, "background": background, "screenshot": filename})
                assert not errors, errors
                assert not writes, writes
                browser.close()
                (evidence / "source-outcomes.json").write_text(json.dumps({
                    "boundary": "Synthetic collection; production UI, API and persisted snapshots",
                    "checks": checks, "pageErrors": errors, "browserWriteRequests": writes,
                }, indent=2), encoding="utf-8")
        finally:
            server.shutdown()
            server.server_close()
            worker.join()
    print(f"PASS: {len(checks)} color/theme cases, reload persistence, source counts, visible skip reasons, no write requests or page errors.")


if __name__ == "__main__":
    main()
