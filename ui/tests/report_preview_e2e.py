"""Verify rendered report navigation using the production UI and synthetic local evidence."""
import json
import re
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright
from capabilities_e2e import ROOT, FixtureService, fixture_config, host, ops


def main():
    evidence = ROOT / "ui" / "docs" / "test-evidence"
    evidence.mkdir(exist_ok=True)
    errors, external, writes, checks = [], [], [], []
    with tempfile.TemporaryDirectory(prefix="report-preview-e2e-") as folder:
        service = FixtureService(ROOT, Path(folder), ROOT / "ui" / "dist" / "index.html")
        run_id = service.start_run(fixture_config(), {"approveSqlWarehouseAutoStart": True})
        host.discover_estate = lambda _: ops.load(ROOT / "ui" / "mock" / "fixtures" / "estate.json")
        server = host.AssessmentHttpServer(("127.0.0.1", 0), service)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page(viewport={"width": 1440, "height": 1000})
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.on("request", lambda request: writes.append(request.url) if request.method != "GET" else None)

                def route_request(route):
                    if urlsplit(route.request.url).hostname != "127.0.0.1":
                        external.append(route.request.url)
                        route.abort()
                    else:
                        route.continue_()

                page.route("**/*", route_request)
                page.goto(f"http://127.0.0.1:{server.server_port}/?run={run_id}")
                page.get_by_role("button", name=re.compile(r"5 Review & export")).click()
                content = page.locator(".content")
                preview = page.get_by_role("region", name="Artifact preview", exact=True)
                report = page.get_by_role("article", name="Rendered report")
                title = report.get_by_role("heading", level=1)

                for theme, width in (("light", 1440), ("dark", 1440), ("light", 390)):
                    page.set_viewport_size({"width": width, "height": 1000})
                    toggle = page.get_by_role("button", name=f"Switch to {theme} mode", exact=True)
                    if toggle.count():
                        toggle.click()
                    content.evaluate("el => el.scrollTo(0, 0)")
                    page.get_by_role("button", name="Preview report", exact=True).click()
                    expect(title).to_have_text("Azure Databricks Cost Optimization Assessment Report")
                    expect(preview).to_be_focused()
                    top = preview.bounding_box()["y"] - content.bounding_box()["y"]
                    assert 0 <= top <= 40, top
                    assert report.locator("table").count() > 0
                    assert content.evaluate("el => el.scrollWidth <= el.clientWidth + 1")
                    expect(page.get_by_role("button", name="Download report", exact=True)).to_be_enabled()
                    page.screenshot(path=str(evidence / f"report-preview-{theme}-{width}.png"))
                    checks.append(f"{theme}/{width}: report rendered, preview focused at scroll target, no page overflow")

                links = report.locator("ol").first.locator('a[href^="#"]')
                assert links.count() == 17, links.count()
                for href in links.evaluate_all("nodes => nodes.map(node => node.getAttribute('href'))"):
                    assert report.locator(f'[id="{href[1:]}"]').count() == 1, href
                checks.append("All 17 contents links resolve, including legacy punctuation")
                original_url = page.url
                links.filter(has_text="Governance, policies, budgets, and FinOps").click()
                target = report.get_by_role("heading", name="11. Governance, policies, budgets, and FinOps", exact=True)
                expect(target).to_be_focused()
                assert page.url == original_url
                assert 0 <= target.bounding_box()["y"] - content.bounding_box()["y"] <= 40
                page.set_viewport_size({"width": 1440, "height": 1000})
                target.scroll_into_view_if_needed()
                page.screenshot(path=str(evidence / "report-preview-section.png"))
                checks.append("Contents click scrolls and focuses the section without navigating away")

                report.get_by_role("button", name="Top cost drivers CSV", exact=True).click()
                expect(preview.locator("pre")).to_be_visible()
                expect(report).to_have_count(0)
                checks.append("Supporting CSV opens as a local plain-text preview")
                expect(preview).to_be_focused()
                preview.get_by_role("button", name="Close", exact=True).click()
                expect(preview).to_have_count(0)
                assert not errors and not external and not writes, (errors, external, writes)
                browser.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
    result = {"timestamp": datetime.now(timezone.utc).isoformat(), "status": "PASS",
              "checks": checks, "browserErrors": errors, "externalRequests": external,
              "writeRequests": writes, "boundary": "Production UI/API/report pipeline; isolated synthetic evidence, no cloud access"}
    (evidence / "report-preview-results.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
