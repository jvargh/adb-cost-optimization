"""Production UI/API/pipeline E2E with explicit synthetic cloud boundary.

Run from workspace root: python ui\\tests\\capabilities_e2e.py
Use --serve for an isolated manual/browser-tool visual session (no cloud access).
"""
import argparse
import copy
import json
import re
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ui" / "server"))
import assessment_server as host
import capability_operations as ops
from assessment.model.capabilities import ASSETS, MODULES


def fixture_config():
    config = ops.load(ROOT / "ui" / "mock" / "fixtures" / "default-config.json")
    config["analysis"].update(startUtc="2026-09-01T00:00:00Z", endUtc="2026-09-02T00:00:00Z")
    config["capabilities"] = ops.validate_options({"profile": "extended", "rules": {"minimumSamples": 1}})
    config["databricks"]["workspaces"] = config["databricks"]["workspaces"][:1]
    workspace = config["databricks"]["workspaces"][0]
    workspace["include"] = True
    config["azure"]["subscriptions"] = config["azure"]["subscriptions"][:1]
    config["azure"]["resourceGroups"] = [workspace["resourceGroup"]]
    return config


def fixture_data(ws):
    data = {
        "clusters": [{"workspace_id": ws, "cluster_id": "cluster-one", "cluster_name": "Review cluster", "num_workers": 2, "node_type_id": "Standard_D4s_v5"}],
        "node-timeline": [{"workspace_id": ws, "cluster_id": "cluster-one", "instance_id": "worker-1", "driver": False,
            "start_time": f"2026-09-01T00:{minute:02d}:00Z", "end_time": f"2026-09-01T00:{minute+1:02d}:00Z",
            "cpu_user_percent": minute % 5, "cpu_system_percent": 1, "mem_used_percent": 20,
            "cpu_wait_percent": 2, "network_received_bytes": 1048576, "network_sent_bytes": 524288} for minute in range(30)],
        "query-history": [{"workspace_id": ws, "statement_id": f"query-{i:03d}", "start_time": "2026-09-01T01:00:00Z",
            "warehouse_id": "warehouse-1", "execution_status": "FAILED" if i % 10 == 0 else "FINISHED",
            "total_duration_ms": 120000 + i, "waiting_at_capacity_duration_ms": 3000, "executed_by": "protected:test-user"} for i in range(65)],
        "jobs": [{"workspace_id": ws, "job_id": "job-1", "settings": {"name": "Nightly job", "tasks": [{"task_key": "transform", "max_retries": 0}],
            "email_notifications": {"on_success": ["protected:user"]}}}],
        "job-runs": [{"workspace_id": ws, "job_id": "job-1", "run_id": "run-1", "start_time": 1788220800000,
            "end_time": 1788220920000, "state": {"result_state": "FAILED"}}],
        "sql-warehouses": [{"workspace_id": ws, "id": "warehouse-1", "name": "Review warehouse", "cluster_size": "2X-Small"}],
        "workspace-settings": [{"workspace_id": ws, "enableIpAccessLists": "false"}],
        "metastore-assignment": [{"workspace_id": ws, "metastore_id": "test-metastore"}],
        "commitment-demand": [{"workspace_id": ws, "region": "eastus", "sku": "D4", "currency": "USD",
            "hour": f"2026-09-01T0{i}:00:00Z", "eligibleNodes": 10, "coveredNodes": 4, "onDemandHourlyRate": 1, "commitmentHourlyRate": .6} for i in range(3)],
    }
    data.update({kind: [{"workspace_id": ws, "id": f"{kind}-1", "name": f"Review {kind}"}] for kind in ASSETS})
    return data


class FixtureService(host.AssessmentService):
    def load_default_config(self):
        return fixture_config()

    def start_validation(self, config, approvals):
        state = host.ValidationState("a" * 32)
        state.consume('AssessmentProgress:{"steps":[{"id":"fixture","title":"Synthetic source boundary"}]}')
        state.consume('AssessmentProgress:{"id":"fixture","status":"pass","detail":"Test fixture only; no cloud access."}')
        state.finish({"generatedAtUtc": host.utc_now(), "checks": [{"id": "system-tables-access", "title": "Fixture source access",
            "status": "pass", "severity": "info", "group": "permissions", "detail": "Synthetic cloud responses for E2E."}],
            "blockerCount": 0, "warningCount": 0, "canRun": approvals.get("approveSqlWarehouseAutoStart") is True,
            "requiresSqlWarehouseApproval": False})
        self.validations["a" * 32] = state
        return state.snapshot()

    def start_run(self, config, approvals):
        if approvals.get("approveSqlWarehouseAutoStart") is not True:
            raise host.ApiError(400, "Fixture still requires explicit warehouse approval.")
        run_id = "fixture-native-" + str(time.time_ns())
        root = self.output_root / run_id
        root.mkdir()
        now = host.utc_now()
        manifest = {"runId": run_id, "customerId": "Synthetic acceptance estate", "assessmentId": run_id,
                    "schemaVersion": "1.0", "toolkitVersion": "capability-e2e", "status": "completed", "startedAtUtc": now,
                    "completedAtUtc": now, "analysisWindow": config["analysis"], "scope": {"subscriptions": config["azure"]["subscriptions"], "resourceGroups": config["azure"]["resourceGroups"]}}
        ops.save(root / "assessment-config.json", config)
        ops.save(root / "assessment-manifest.json", manifest)
        selected = [w for w in config["databricks"]["workspaces"] if w["include"]]
        for workspace in selected:
            ws = str(workspace["workspaceId"])
            for kind, rows in fixture_data(ws).items():
                ops.save(root / "raw" / "databricks" / ws / f"{kind}.json", rows)
        ops.save(root / "collection-status.json", [{"name": "Synthetic Databricks evidence", "status": "partial", "itemCount": 100,
            "outputs": [], "limitations": ["E2E fixture boundary; not a real cloud scan."], "error": ""}])
        ops.run_pipeline(root / "assessment-config.json", root)
        state = host.RunState(run_id, root / "assessment-config.json")
        state.add_event({"type": "phase", "phase": "analyzing", "message": "Production pipeline with synthetic cloud evidence", "atUtc": now})
        state.add_event({"type": "completed", "runId": run_id, "atUtc": now})
        self.runs[run_id] = state
        return run_id


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--serve", action="store_true")
    args = parser.parse_args()
    evidence_root = ROOT / "ui" / "docs" / "test-evidence"
    evidence_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="capability-e2e-") as folder:
        root = Path(folder)
        service = FixtureService(ROOT, root, ROOT / "ui" / "dist" / "index.html")
        estate = ops.load(ROOT / "ui" / "mock" / "fixtures" / "estate.json")
        selected_id = fixture_config()["databricks"]["workspaces"][0]["workspaceId"]
        for subscription in estate:
            for group in subscription["resourceGroups"]:
                group["workspaces"] = [w for w in group["workspaces"] if w["workspaceId"] == selected_id]
        host.discover_estate = lambda _: copy.deepcopy(estate)
        server = host.AssessmentHttpServer(("127.0.0.1", 8771 if args.serve else 0), service)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        url = f"http://127.0.0.1:{server.server_port}"
        if args.serve:
            run_id = service.start_run(fixture_config(), {"approveSqlWarehouseAutoStart": True})
            print(f"Visual fixture URL: {url}/?run={run_id}", flush=True)
            try:
                while True:
                    time.sleep(1)
            finally:
                server.shutdown(); server.server_close()
        else:
            from playwright.sync_api import sync_playwright, expect
            results = []
            errors = []
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page(viewport={"width": 1440, "height": 1000}, accept_downloads=True)
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.on("dialog", lambda dialog: dialog.accept())
                page.goto(url)
                page.get_by_role("button", name="Validate configuration").wait_for()
                page.get_by_role("button", name=re.compile(r"2 Validate")).click()
                page.get_by_role("checkbox", name=re.compile(r"Approve SQL Warehouse auto-start")).check()
                page.get_by_role("button", name="Run validation", exact=True).click()
                expect(page.get_by_role("button", name="Continue to run", exact=True)).to_be_enabled()
                assert page.get_by_role("button", name="Continue to run", exact=True).count() == 1
                page.get_by_role("button", name="Continue to run", exact=True).click()
                page.get_by_role("button", name="Start read-only assessment", exact=True).click()
                page.get_by_role("button", name="Visualize results", exact=True).click()
                page.get_by_text("Viewing a saved snapshot", exact=True).wait_for()
                native_id = page.url.split("run=")[1].split("&")[0]
                results.append({"test": "Configure / validate / explicit start / persisted results", "status": "PASS", "boundary": "Synthetic cloud; production UI/API/pipeline"})
                for view in ("Compute and SQL", "Queries", "Posture", "Assets", "Evidence quality"):
                    page.get_by_role("tab", name=view, exact=True).click()
                    if view == "Compute and SQL":
                        for section in ("Utilization", "Sizing", "Job health", "Network"):
                            page.get_by_role("tab", name=section, exact=True).click()
                            expect(page.get_by_text(re.compile("matching saved rows"))).to_be_visible()
                    elif view in ("Queries", "Posture", "Assets"):
                        expect(page.get_by_text(re.compile("matching saved rows"))).to_be_visible()
                    results.append({"test": view, "status": "PASS"})
                page.get_by_role("tab", name="Queries", exact=True).click()
                expect(page.get_by_text("65 matching saved rows", exact=True)).to_be_visible()
                page.get_by_role("button", name="Next page", exact=True).click()
                expect(page.get_by_text("51-65 of 65", exact=True)).to_be_visible()
                page.get_by_label("Query view").select_option("warehouseId")
                expect(page.get_by_text("1 matching saved rows", exact=True)).to_be_visible()
                results.append({"test": "Query pagination and full-dataset warehouse summaries", "status": "PASS"})
                page.get_by_role("tab", name="Cost analysis", exact=True).click()
                page.get_by_role("tab", name="Commitment opportunities", exact=True).click()
                page.get_by_role("button", name="Calculate scenario", exact=True).click()
                expect(page.locator("pre").filter(has_text="baselineUncoveredCost")).to_be_visible()
                results.append({"test": "Commitment saved-input scenario", "status": "PASS"})
                page.get_by_role("button", name="Review & export", exact=True).click()
                page.get_by_text("Record a decision", exact=True).click()
                page.get_by_role("combobox").filter(has=page.locator('option[value="deferred"]')).first.select_option("deferred")
                page.get_by_role("textbox", name="Reviewer", exact=True).first.fill("Acceptance reviewer")
                page.get_by_role("button", name="Save review decisions", exact=True).click()
                expect(page.get_by_role("button", name=re.compile(r"5 Review & export"))).to_be_visible()
                page.get_by_role("button", name="Generate workbook artifact", exact=True).click()
                workbook_row = page.get_by_role("row").filter(has_text=".xlsx")
                with page.expect_download() as download:
                    workbook_row.get_by_role("button", name="Download", exact=True).click()
                download.value.save_as(str(root / "download.xlsx"))
                with ZipFile(root / "download.xlsx") as workbook:
                    assert "xl/workbook.xml" in workbook.namelist()
                results.append({"test": "Review save and valid binary workbook download", "status": "PASS"})
                page.get_by_text("Preview an explicitly approved destination", exact=True).click()
                page.get_by_label("Destination workspace URL").fill("adb-42.1.azuredatabricks.net")
                page.get_by_label("Destination warehouse ID").fill("test-warehouse")
                page.get_by_role("button", name="Preview publication plan", exact=True).click()
                expect(page.get_by_role("button", name="Publish approved dashboard", exact=True)).to_be_disabled()
                results.append({"test": "Publication plan and separate approval gate; no writes", "status": "PASS"})
                page.get_by_role("button", name="Import evidence", exact=True).click()
                page.get_by_label("Workspace ID", exact=True).fill("42")
                page.get_by_label("Declared start UTC").fill("2026-09-01T00:00")
                page.get_by_label("Declared end UTC").fill("2026-09-02T00:00")
                import_files = []
                for kind, rows in fixture_data("42").items():
                    file = root / f"{kind}.json"; ops.save(file, rows); import_files.append(str(file))
                page.locator('input[type="file"][multiple]').set_input_files(import_files)
                page.get_by_role("button", name="Validate import", exact=True).click()
                page.get_by_role("checkbox", name="Confirm declared scope, limitations and redaction").check()
                page.get_by_role("button", name="Analyze imported evidence", exact=True).click()
                page.get_by_role("tab", name="Executive summary", exact=True).click()
                expect(page.get_by_text("Imported evidence: authoritative cost unavailable", exact=True)).to_be_visible()
                results.append({"test": "Local import validation / analysis / saved snapshot / no-cost state", "status": "PASS"})
                page.get_by_role("tab", name="Evidence quality", exact=True).click()
                page.get_by_text("Inspect effective rules / create another analysis", exact=True).click()
                page.get_by_role("button", name="Create child analysis", exact=True).click()
                expect(page.get_by_text("Viewing a saved snapshot", exact=True)).to_be_visible()
                page.wait_for_url(re.compile(r".*run=analysis-.*"))
                results.append({"test": "Child re-analysis preserves parent", "status": "PASS"})
                for theme in ("light", "dark"):
                    toggle = page.get_by_role("button", name=f"Switch to {theme} mode", exact=True)
                    if toggle.count():
                        toggle.click()
                    for width in (1440, 768, 390):
                        page.set_viewport_size({"width": width, "height": 1000})
                        assert page.locator("html").get_attribute("data-theme") == theme
                        page.get_by_role("tab", name="Compute and SQL", exact=True).click()
                        page.get_by_role("tab", name="Utilization", exact=True).click()
                        expect(page.get_by_text("1 matching saved rows", exact=True)).to_be_visible()
                        page.screenshot(path=str(evidence_root / f"capabilities-{theme}-{width}.png"), full_page=True, animations="disabled")
                        overflow = page.evaluate("document.documentElement.scrollWidth > window.innerWidth")
                        assert not overflow, f"Page overflow at {width}/{theme}"
                        results.append({"test": f"Visual {theme} {width}px", "status": "PASS"})
                page.set_viewport_size({"width": 1440, "height": 1000})
                page.get_by_role("button", name="Review cluster", exact=True).click()
                expect(page.get_by_role("dialog", name="Review cluster", exact=True)).to_be_visible()
                expect(page.locator(".recharts-line-curve")).to_have_count(2)
                page.screenshot(path=str(evidence_root / "capabilities-utilization-detail.png"), full_page=True, animations="disabled")
                page.keyboard.press("Escape")
                expect(page.get_by_role("dialog")).to_have_count(0)
                assert not errors, errors
                browser.close()
            server.shutdown(); server.server_close()
            ops.save(evidence_root / "capabilities-e2e-results.json", {"timestamp": datetime.now(timezone.utc).isoformat(), "results": results,
                     "browserErrors": errors, "liveCloudTested": False, "nativeFixtureRun": native_id})
            print(json.dumps({"status": "PASS", "checks": len(results), "browserErrors": errors}, indent=2))


if __name__ == "__main__":
    main()
