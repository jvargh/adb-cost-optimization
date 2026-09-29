import json
import io
import threading
import tempfile
import unittest
import subprocess
import shutil
import os
from http.client import HTTPConnection
from pathlib import Path
from unittest.mock import patch, Mock

from assessment_server import (
    ApiError,
    AssessmentService,
    AssessmentHttpServer,
    RunState,
    ValidationState,
    build_assessment_arguments,
    collector_event,
    map_results,
    readiness_source_warnings,
    readiness_source_checks,
    readiness_warnings,
    validation_report,
    resolve_artifact,
    resolve_run_root,
)


class ArgumentConstructionTests(unittest.TestCase):
    def test_readiness_omits_sql_approval_without_explicit_approval(self):
        args = build_assessment_arguments(
            "pwsh",
            Path("Invoke-Assessment.ps1"),
            "Readiness",
            Path("config.json"),
            Path("output"),
            {"approveSqlWarehouseAutoStart": False},
        )
        self.assertIn("Readiness", args)
        self.assertNotIn("-ApproveSqlWarehouseAutoStart", args)
        self.assertNotIn("-NoOpenReport", args)

    def test_run_maps_approvals_and_disables_report_open(self):
        args = build_assessment_arguments(
            "pwsh",
            Path("Invoke-Assessment.ps1"),
            "Run",
            Path("config.json"),
            Path("output"),
            {
                "approveSqlWarehouseAutoStart": True,
                "continueOnCollectorError": False,
            },
        )
        self.assertIn("-ApproveSqlWarehouseAutoStart", args)
        self.assertIn("-FailOnCollectorError", args)
        self.assertIn("-NoOpenReport", args)
        self.assertNotIn("-ContinueOnCollectorError", args)


class ProgressParsingTests(unittest.TestCase):
    def test_streamed_checks_preserve_waiting_warning_and_running_states(self):
        state = ValidationState("test")
        state.consume('AssessmentProgress:{"steps":[{"id":"one","title":"One"},{"id":"two","title":"Two"}]}')
        state.consume('AssessmentProgress:{"id":"one","status":"warn","detail":"Incomplete evidence."}')
        state.consume('AssessmentProgress:{"id":"two","status":"running","detail":"Reading costs."}')
        snapshot = state.snapshot()
        self.assertEqual([step["status"] for step in snapshot["steps"]], ["warn", "running"])
        self.assertIsNotNone(snapshot["steps"][0]["finishedAtUtc"])
        self.assertIsNone(snapshot["steps"][1]["finishedAtUtc"])
        snapshot["steps"][0]["status"] = "pass"
        self.assertEqual(state.snapshot()["steps"][0]["status"], "warn")

    def test_failure_never_marks_waiting_or_active_checks_passed(self):
        state = ValidationState("test")
        state.consume('AssessmentProgress:{"steps":[{"id":"one","title":"One"},{"id":"two","title":"Two"}]}')
        state.consume('AssessmentProgress:{"id":"one","status":"running"}')
        state.finish(error="PowerShell stopped.")
        snapshot = state.snapshot()
        self.assertEqual(snapshot["status"], "failed")
        self.assertEqual([step["status"] for step in snapshot["steps"]], ["fail", "skipped"])

    def test_no_progress_is_not_reported_as_success(self):
        state = ValidationState("test")
        state.finish({"canRun": True})
        self.assertEqual(state.snapshot()["status"], "failed")

    def test_blocking_report_is_preserved_when_power_shell_stops_before_progress(self):
        state = ValidationState("test")
        report = {
            "canRun": False, "blockerCount": 1,
            "checks": [{"id": "read-only-scanner", "severity": "blocker", "status": "fail",
                        "detail": "Assessment config requires customerId and assessmentId."}],
        }
        state.finish(report)
        snapshot = state.snapshot()
        self.assertEqual(snapshot["status"], "completed")
        self.assertEqual(snapshot["report"], report)
        self.assertFalse(snapshot["report"]["canRun"])
        self.assertIsNone(snapshot["error"])
        self.assertEqual(snapshot["steps"], [])
        self.assertIn("before source checks", snapshot["message"])

    def test_collector_line_becomes_source_event(self):
        event = collector_event("  Databricks billing [42]: pending telemetry (0 items)")
        self.assertIsNotNone(event)
        self.assertEqual(event["source"]["status"], "pending telemetry")
        self.assertEqual(event["source"]["workspaceKey"], "42")
        self.assertEqual(event["source"]["domain"], "databricks")

    def test_repeated_resource_warning_is_plain_and_deduplicated(self):
        output = "\n".join(
            [
                "WARNING: request failed: The resource type 'microsoft.databricks/accessconnectors' does not support diagnostic settings.",
                "WARNING: retry failed: The resource type 'microsoft.databricks/accessconnectors' does not support diagnostic settings.",
            ]
        )
        warnings = readiness_warnings(output)
        self.assertEqual(len(warnings), 1)
        self.assertIn("Azure does not support diagnostic settings", warnings[0])

    def test_each_degraded_source_becomes_its_own_warning(self):
        warnings = readiness_source_warnings(
            "\n".join(
                [
                    "  Azure inventory: passed (16 items)",
                    "  Azure policy and diagnostics: partial (554 items)",
                    "  Databricks billing [42]: pending telemetry (0 items)",
                ]
            )
        )
        self.assertEqual(len(warnings), 2)
        self.assertEqual(warnings[0]["status"], "partial")
        self.assertEqual(warnings[1]["status"], "pending telemetry")


class ReadinessEvidenceTests(unittest.TestCase):
    cost_probe = {
        "name": "Azure Cost Management", "status": "partial",
        "limitations": ["Cost access probe succeeded. Readiness checks only a one-day aggregate per scope; full cost coverage is not validated until Run."],
    }
    unsupported = {
        "name": "Azure policy and diagnostics", "status": "partial",
        "limitations": ["The resource type 'microsoft.databricks/accessconnectors' does not support diagnostic settings."],
    }

    @staticmethod
    def source(name, source, status, message):
        return {"name": name, "status": "partial", "sources": [
            {"source": source, "status": status, "message": message},
            {"source": "identities", "status": "skipped", "message": "Disabled by scope."},
        ]}

    @staticmethod
    def report(results, extra_output=""):
        output = "AssessmentProgress:" + json.dumps({"results": results}) + "\n" + extra_output
        return validation_report(
            {"azure": {"subscriptions": ["sub"], "resourceGroups": ["rg"]},
             "databricks": {"workspaces": [{"include": True}]}}, {},
            subprocess.CompletedProcess([], 0, output, ""),
        )

    def test_cost_probe_and_unsupported_diagnostics_are_notes_not_coverage_passes(self):
        report = self.report([self.cost_probe, self.unsupported])
        self.assertTrue(report["canRun"])
        self.assertEqual(report["warningCount"], 0)
        cost = next(check for check in report["checks"] if check["title"] == "Cost Management access probe passed")
        self.assertEqual(cost["severity"], "info")
        self.assertIn("have not yet been validated", cost["detail"])
        diagnostics = next(check for check in report["checks"] if "resource types" in check["title"])
        self.assertEqual(diagnostics["status"], "skipped")
        self.assertEqual(self.cost_probe["status"], "partial")

    def test_23_source_warnings_become_two_configuration_actions_and_two_notes(self):
        results = [self.cost_probe, self.unsupported]
        for workspace in ("one", "two", "three"):
            for category in ("billing", "compute", "workloads", "SQL", "Unity Catalog", "governance"):
                results.append(self.source(
                    f"Databricks {category} [{workspace}]", "system table", "pending telemetry",
                    "A SQL Warehouse ID is required to read this source.",
                ))
            results.append(self.source(
                f"Databricks workspace [{workspace}]", "account workspace inventory", "pending telemetry",
                "accountId and accountHost are required for Account API inventory.",
            ))
        self.assertEqual(len(results), 23)
        report = self.report(results)
        self.assertEqual(report["warningCount"], 2)
        sql = next(check for check in report["checks"] if check["title"] == "SQL-backed evidence was not checked")
        self.assertEqual(len(sql["evidence"]), 18)
        self.assertIn("approve", sql["remediation"])
        self.assertNotIn("not enough telemetry", sql["detail"])
        self.assertNotIn("Disabled by scope", json.dumps(report))

    def test_missing_warehouses_name_only_affected_workspaces_and_preserve_evidence(self):
        results = [self.source(f"Databricks billing [{workspace}]", "system.billing.usage", "pending telemetry",
                               "A SQL Warehouse ID is required to read this source.") for workspace in ("one", "two")]
        config = {"azure": {"subscriptions": ["sub"], "resourceGroups": ["rg"]}, "databricks": {
            "workspaces": [{"include": True, "workspaceId": key, "name": name} for key, name in (
                ("one", "dbx-rg-workspace"), ("two", "dbx-lab-workspace"), ("three", "configured-workspace"),
            )],
        }}
        report = validation_report(config, {}, subprocess.CompletedProcess(
            [], 0, "AssessmentProgress:" + json.dumps({"results": results}), "",
        ))
        sql = next(check for check in report["checks"] if check["title"] == "SQL-backed evidence was not checked")
        self.assertIn("dbx-rg-workspace (one)", sql["detail"])
        self.assertIn("dbx-lab-workspace (two)", sql["detail"])
        self.assertNotIn("configured-workspace", sql["detail"])
        self.assertIn("CAN USE", sql["remediation"])
        self.assertIn("explicitly approve", sql["remediation"])
        self.assertEqual(len(sql["evidence"]), 2)
        self.assertEqual(report["warningCount"], 1)

    def test_permissions_are_not_hidden_by_expected_deferral(self):
        result = self.source("Databricks workloads [one]", "system table", "pending telemetry",
                             "A SQL Warehouse ID is required to read this source.")
        result["sources"].append({"source": "jobs", "status": "failed",
                                  "message": "Databricks API returned HTTP 403: PERMISSION_DENIED"})
        checks = readiness_source_checks([result])
        self.assertEqual(len(checks), 2)
        denied = next(check for check in checks if "access was denied" in check["title"])
        self.assertEqual(denied["checkStatus"], "warn")
        self.assertIn("403", denied["evidence"][0]["detail"])

    def test_cost_throttling_and_azure_denial_remain_warnings(self):
        results = [
            {**self.cost_probe, "status": "failed", "limitations": ["Cost Management HTTP 429: Too Many Requests"]},
            {**self.unsupported, "limitations": [*self.unsupported["limitations"], "Azure Policy: AuthorizationFailed"]},
        ]
        report = self.report(results)
        self.assertEqual(report["warningCount"], 2)
        self.assertTrue(any("throttling" in check["title"] for check in report["checks"]))
        self.assertTrue(any("Azure evidence access was denied" == check["title"] for check in report["checks"]))

    def test_unknown_pending_status_does_not_claim_no_telemetry(self):
        checks = readiness_source_warnings("  Databricks billing [42]: pending telemetry (0 items)")
        self.assertEqual(checks[0]["checkStatus"], "warn")
        self.assertIn("without an explanation", checks[0]["detail"])
        self.assertNotIn("not enough telemetry", checks[0]["detail"])

    def test_structured_results_replace_console_summary_without_duplicates(self):
        report = self.report([self.cost_probe, self.unsupported],
                             "  Azure Cost Management: partial (0 items)\n"
                             "WARNING: The resource type 'microsoft.databricks/accessconnectors' does not support diagnostic settings.")
        self.assertEqual(report["warningCount"], 0)
        self.assertEqual(sum(check["id"].startswith("readiness-source-") for check in report["checks"]), 2)

    def test_progress_classification_matches_report(self):
        for result, expected in ((self.cost_probe, "pass"), (self.unsupported, "not-applicable"),
                                 ({**self.unsupported, "itemCount": 12}, "pass")):
            with self.subTest(expected=expected):
                state = ValidationState("test")
                state.consume('AssessmentProgress:{"steps":[{"id":"check","title":"Check"}]}')
                state.consume("AssessmentProgress:" + json.dumps(
                    {"id": "check", "status": "warn", "results": [result]}))
                step = state.snapshot()["steps"][0]
                self.assertEqual(step["status"], expected)
                self.assertNotIn("returned partial", step["detail"])

    def test_progress_exposes_remediation_and_evidence_instead_of_raw_error_wall(self):
        result = self.source("Databricks workloads [one]", "system.lakeflow.pipeline_update_timeline", "failed",
                             "INSUFFICIENT_PERMISSIONS: User does not have SELECT on Table 'system.lakeflow.pipeline_update_timeline'")
        state = ValidationState("test")
        state.consume('AssessmentProgress:{"steps":[{"id":"check","title":"Check"}]}')
        state.consume("AssessmentProgress:" + json.dumps({"id": "check", "status": "warn", "results": [result]}))
        step = state.snapshot()["steps"][0]
        self.assertEqual(step["status"], "warn")
        self.assertNotIn("INSUFFICIENT_PERMISSIONS", step["detail"])
        self.assertIn("SELECT on system.lakeflow.pipeline_update_timeline", step["issues"][0]["remediation"])
        self.assertIn("INSUFFICIENT_PERMISSIONS", step["issues"][0]["evidence"][0]["detail"])

    def test_successful_results_are_not_green_when_any_real_failure_remains(self):
        result = {**self.unsupported, "itemCount": 12,
                  "limitations": [*self.unsupported["limitations"], "Azure Policy: AuthorizationFailed"]}
        state = ValidationState("test")
        state.consume('AssessmentProgress:{"steps":[{"id":"check","title":"Check"}]}')
        state.consume("AssessmentProgress:" + json.dumps({"id": "check", "status": "warn", "results": [result]}))
        self.assertEqual(state.snapshot()["steps"][0]["status"], "warn")

    def test_spark_detailed_metrics_are_not_claimed_to_be_supported(self):
        checks = readiness_source_checks([self.source(
            "Databricks Spark deep dive [one]", "Spark stage, task, executor, and SQL execution metrics",
            "pending telemetry", "The Jobs and cluster event APIs do not expose full Spark UI metrics. Supply an approved event-log export to satisfy detailed Spark evidence.",
        )])
        self.assertEqual(checks[0]["checkStatus"], "warn")
        self.assertIn("no event-log importer", checks[0]["remediation"])

    def test_missing_structured_causes_never_suppress_a_degraded_result(self):
        result = {"name": "Databricks compute [one]", "status": "partial",
                  "sources": [{"source": "clusters", "status": "passed"}], "error": "Unknown failure"}
        checks = readiness_source_checks([result])
        self.assertEqual(checks[0]["checkStatus"], "warn")
        self.assertEqual(checks[0]["detail"], "Unknown failure")


class PathContainmentTests(unittest.TestCase):
    def test_run_id_rejects_traversal(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ApiError):
                resolve_run_root(Path(directory), "..")

    def test_artifact_rejects_encoded_or_backslash_traversal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(ApiError):
                resolve_artifact(root, "%2e%2e/secret.txt")
            with self.assertRaises(ApiError):
                resolve_artifact(root, "..\\secret.txt")

    def test_artifact_resolves_contained_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / "reports" / "assessment-report.md"
            report.parent.mkdir()
            report.write_text("report", encoding="utf-8")
            self.assertEqual(resolve_artifact(root, "reports/assessment-report.md"), report.resolve())


class ValidationJobTests(unittest.TestCase):
    def test_early_process_failure_reaches_the_report_instead_of_the_generic_no_checks_error(self):
        process = Mock(
            stdout=io.StringIO("\x1b[31mAssessment config requires customerId and assessmentId.\x1b[0m\n"),
            wait=Mock(return_value=1), poll=Mock(return_value=1),
        )
        with tempfile.TemporaryDirectory() as directory, patch("assessment_server.subprocess.Popen", return_value=process):
            root = Path(directory)
            service = AssessmentService(root, root, root / "index.html")
            config_path = root / "config.json"
            config_path.write_text("{}", encoding="utf-8")
            state = ValidationState("early-failure")
            service._monitor_validation(state, config_path, {"azure": {}, "databricks": {}}, {})
            snapshot = state.snapshot()
            self.assertEqual(snapshot["status"], "completed")
            self.assertFalse(snapshot["report"]["canRun"])
            readiness = next(check for check in snapshot["report"]["checks"] if check["id"] == "read-only-scanner")
            self.assertEqual(readiness["status"], "fail")
            self.assertIn("requires customerId and assessmentId", readiness["detail"])
            self.assertNotIn("\x1b", readiness["detail"])
            self.assertIsNone(snapshot["error"])
            self.assertFalse(config_path.exists())

    def test_returns_job_before_process_finishes_and_reports_live_checks(self):
        waiting = threading.Event()
        release = threading.Event()

        class Stream(io.StringIO):
            def __iter__(self):
                yield 'AssessmentProgress:{"steps":[{"id":"scope","title":"Scope"}]}\n'
                yield 'AssessmentProgress:{"id":"scope","status":"running"}\n'
                waiting.set()
                release.wait(5)
                yield 'AssessmentProgress:{"id":"scope","status":"pass"}\n'

        process = Mock(stdout=Stream(), wait=Mock(return_value=0), poll=Mock(return_value=0))
        with tempfile.TemporaryDirectory() as directory, patch("assessment_server.subprocess.Popen", return_value=process):
            root = Path(directory)
            service = AssessmentService(root, root, root / "index.html")
            initial = service.start_validation({"azure": {}, "databricks": {}}, {})
            self.assertTrue(waiting.wait(2))
            job_id = initial["validationId"]
            self.assertEqual(service.validation_status(job_id)["steps"][0]["status"], "running")
            release.set()
            # Wait for the worker's actual completion, not a simulated success.
            for thread in threading.enumerate():
                if thread.name.endswith("(_monitor_validation)"):
                    thread.join(3)
            final = service.validation_status(job_id)
            self.assertEqual(final["status"], "completed")
            self.assertEqual(final["steps"][0]["status"], "pass")
            self.assertIsNotNone(final["report"])
            self.assertEqual(list((root / ".ui-server" / "configs").glob("*.json")), [])

    def test_unknown_job_explains_server_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            service = AssessmentService(root, root, root / "index.html")
            with self.assertRaisesRegex(ApiError, "server may have restarted"):
                service.validation_status("missing")


class ReviewPersistenceTests(unittest.TestCase):
    def test_review_is_saved_to_json_and_export_csv(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run_root = root / "run-1"
            run_root.mkdir()
            service = AssessmentService(root, root, root / "index.html")
            entries = [
                {
                    "findingId": "F-1",
                    "finding": "Finding one",
                    "evidenceLinks": ["a.json", "b.json"],
                    "reviewer": "Reviewer",
                    "role": "Owner",
                    "reviewedAtUtc": "2026-01-01T00:00:00Z",
                    "decision": "accepted",
                    "businessSlaContext": "",
                    "performanceReliabilityRisk": "",
                    "securityGovernanceImpact": "",
                    "validationExperiment": "",
                    "ownerApprover": "",
                    "rationale": "Validated",
                }
            ]

            service.save_review("run-1", entries)

            self.assertEqual(json.loads((run_root / ".ui-review.json").read_text())[0]["reviewer"], "Reviewer")
            csv_text = (run_root / "reports" / "human-validation-sign-off.csv").read_text()
            self.assertIn("a.json; b.json", csv_text)
            self.assertIn("Validated", csv_text)


class ResultMappingTests(unittest.TestCase):
    def test_maps_persisted_artifacts_to_result_shape(self):
        with tempfile.TemporaryDirectory() as directory:
            run_root = Path(directory) / "run-1"
            (run_root / "normalized").mkdir(parents=True)
            (run_root / "reports").mkdir()
            config = {
                "azure": {"tenantId": "tenant", "currency": "USD"},
                "databricks": {
                    "workspaces": [
                        {
                            "name": "workspace-one",
                            "workspaceId": "42",
                            "workspaceUrl": "adb.example",
                            "resourceGroup": "rg-one",
                            "subscriptionId": "sub-one",
                            "include": True,
                        }
                    ]
                },
            }
            manifest = {
                "schemaVersion": "1.0",
                "toolkitVersion": "0.1",
                "runId": "run-1",
                "customerId": "customer",
                "assessmentId": "assessment",
                "startedAtUtc": "2026-01-01T00:00:00Z",
                "completedAtUtc": "2026-01-01T01:00:00Z",
                "status": "partial",
                "analysisWindow": {"startUtc": "a", "endUtc": "b", "timeZone": "UTC"},
                "outputRoot": str(run_root),
                "scope": {
                    "subscriptions": ["sub-one"],
                    "resourceGroups": ["rg-one"],
                    "resourceGroupIds": ["/subscriptions/sub-one/resourceGroups/rg-one"],
                    "workspaces": ["adb.example"],
                },
            }
            candidates = {
                "schemaVersion": "1.0",
                "analysisWindow": manifest["analysisWindow"],
                "candidateCount": 1,
                "insufficientEvidenceCount": 0,
                "findings": [
                    {
                        "detectorId": "MON-MISSING-BUDGET",
                        "title": "Missing budget",
                        "status": "candidate",
                        "recommendedAction": "Create one",
                    }
                ],
            }
            required = {
                "assessment-config.json": config,
                "assessment-manifest.json": manifest,
                "collection-status.json": [
                    {
                        "name": "Databricks compute [42]",
                        "status": "pending telemetry",
                        "startedAtUtc": None,
                        "completedAtUtc": None,
                        "itemCount": 0,
                        "outputs": [],
                        "limitations": ["No rows"],
                        "error": "",
                    }
                ],
                "optimization-candidates.json": candidates,
                "scope-filter.json": {"schemaVersion": "1.0", "allowedResourceGroups": [], "allowedResourceGroupIds": [], "entities": {}, "limitations": []},
                "cost-reconciliation.json": {"authoritativeTotal": 0, "currency": "USD"},
                "attribution-coverage.json": {"schemaVersion": "1.0"},
                "telemetry-quality.json": {"schemaVersion": "1.0"},
                "benefits-baseline.json": {"schemaVersion": "1.0", "authoritativeCost": 0, "currency": "USD"},
            }
            for name, value in required.items():
                (run_root / name).write_text(json.dumps(value), encoding="utf-8")
            (run_root / "reports" / "assessment-report.md").write_text("# Report", encoding="utf-8")

            results = map_results(run_root)

            self.assertEqual(results["manifest"]["scope"]["subscriptionIds"], ["sub-one"])
            self.assertEqual(results["manifest"]["scope"]["workspaces"][0]["name"], "workspace-one")
            self.assertEqual(results["collection"][0]["status"], "pending telemetry")
            self.assertEqual(results["collection"][0]["workspaceKey"], "42")
            self.assertEqual(results["review"][0]["findingId"], "MON-MISSING-BUDGET")
            self.assertEqual(results["roadmap"][0]["horizon"], "0-30")
            self.assertEqual(results["reportMarkdown"], "# Report")
            self.assertTrue(any(item["relativePath"] == "reports/assessment-report.md" for item in results["exports"]))


class SnapshotDeletionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.output = self.root / "output"
        self.service = AssessmentService(self.root, self.output, self.root / "index.html")

    def make_run(self, run_id, status="partial"):
        run = self.output / run_id
        (run / "reports").mkdir(parents=True)
        (run / "assessment-manifest.json").write_text(json.dumps({"runId": run_id, "status": status}))
        (run / "reports" / "report.md").write_text("saved evidence")
        (run / ".ui-review.json").write_text('[]')
        return run

    def test_confirmation_and_valid_explicit_ids_are_required_before_deletion(self):
        run = self.make_run("one")
        for ids, confirm in [(["one"], False), ([], True), ("all", True), (["one", "../outside"], True), (["."], True)]:
            with self.assertRaises(ApiError):
                self.service.delete_snapshots(ids, confirm)
            self.assertTrue(run.is_dir())

    def test_deletes_one_or_an_explicit_batch_but_preserves_root_and_unlisted_files(self):
        first = self.make_run("one")
        second = self.make_run("two")
        third = self.make_run("created-after-confirmation")
        control = self.output / ".ui-server"
        control.mkdir()
        result = self.service.delete_snapshots(["one", "two", "one"], True)
        self.assertEqual(result, {"deletedRunIds": ["one", "two"], "failures": []})
        self.assertFalse(first.exists())
        self.assertFalse(second.exists())
        self.assertTrue(third.exists())
        self.assertTrue(control.is_dir())
        self.assertTrue(self.output.is_dir())
        restarted = AssessmentService(self.root, self.output, self.root / "index.html")
        with self.assertRaises(ApiError):
            resolve_run_root(restarted.output_root, "one")

    def test_refuses_active_unfinished_and_unrecognized_folders(self):
        running = self.make_run("running", "running")
        active = self.make_run("active")
        mismatch = self.make_run("mismatch")
        (mismatch / "assessment-manifest.json").write_text('{"runId":"different","status":"passed"}')
        generic = self.output / "not-a-run"
        generic.mkdir()
        state = RunState("active", self.root / "config.json")
        self.service.runs["active"] = state
        result = self.service.delete_snapshots(["running", "active", "mismatch", "not-a-run"], True)
        self.assertFalse(result["deletedRunIds"])
        self.assertEqual(len(result["failures"]), 4)
        self.assertTrue(all(path.is_dir() for path in [running, active, mismatch, generic]))

    def test_partial_batch_failure_reports_exact_deletions_and_io_errors(self):
        good = self.make_run("good")
        blocked = self.make_run("blocked")
        remove = shutil.rmtree

        def fail_one(path):
            if path == blocked.resolve():
                raise PermissionError("File is locked.")
            remove(path)

        with patch("assessment_server.shutil.rmtree", side_effect=fail_one):
            result = self.service.delete_snapshots(["good", "blocked"], True)
        self.assertEqual(result["deletedRunIds"], ["good"])
        self.assertIn("File is locked", result["failures"][0]["message"])
        self.assertIn("partly removed", result["failures"][0]["message"])
        self.assertFalse(good.exists())
        self.assertTrue(blocked.exists())

    def test_reparse_points_are_rejected_without_deleting_any_files(self):
        run = self.make_run("linked")
        original = Path.lstat

        def with_link(path, *args, **kwargs):
            if path.name == "report.md":
                return Mock(st_mode=0, st_file_attributes=0x400)
            return original(path, *args, **kwargs)

        with patch.object(Path, "lstat", with_link):
            result = self.service.delete_snapshots(["linked"], True)
        self.assertFalse(result["deletedRunIds"])
        self.assertIn("reparse point", result["failures"][0]["message"])
        self.assertTrue((run / "reports" / "report.md").is_file())

    def test_a_directory_junction_cannot_redirect_deletion(self):
        outside = self.root / "outside"
        outside.mkdir()
        sentinel = outside / "keep.txt"
        sentinel.write_text("keep")
        link = self.output / "linked-root"
        if os.name == "nt":
            subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(outside)], check=True, capture_output=True)
        else:
            link.symlink_to(outside, target_is_directory=True)
        try:
            result = self.service.delete_snapshots(["linked-root"], True)
            self.assertFalse(result["deletedRunIds"])
            self.assertIn("reparse point", result["failures"][0]["message"])
            self.assertEqual(sentinel.read_text(), "keep")
        finally:
            if os.name == "nt":
                link.rmdir()
            else:
                link.unlink()

    def test_delete_route_checks_origin_content_type_and_confirmation(self):
        run = self.make_run("one")
        with AssessmentHttpServer(("127.0.0.1", 0), self.service) as server:
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            host, port = server.server_address
            try:
                for content_type, origin, confirmed, expected in [
                    ("text/plain", f"http://{host}:{port}", True, 415),
                    ("application/json", "https://untrusted.example", True, 403),
                    ("application/json", f"http://{host}:{port}", False, 400),
                    ("application/json", f"http://{host}:{port}", True, 200),
                ]:
                    connection = HTTPConnection(host, port)
                    try:
                        connection.request("POST", "/api/snapshots/delete",
                                           json.dumps({"runIds": ["one"], "confirmed": confirmed}),
                                           {"Content-Type": content_type, "Origin": origin})
                        response = connection.getresponse()
                        payload = json.loads(response.read())
                        self.assertEqual(response.status, expected, payload)
                        self.assertEqual(run.exists(), expected != 200)
                    finally:
                        connection.close()
            finally:
                server.shutdown()
                worker.join()


class SavedSnapshotTests(unittest.TestCase):
    def test_a_second_host_cannot_listen_on_the_same_port(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            service = AssessmentService(root, root, root / "index.html")
            with AssessmentHttpServer(("127.0.0.1", 0), service) as first:
                with self.assertRaises(OSError):
                    with AssessmentHttpServer(first.server_address, service):
                        self.fail("A second host must not share the live port.")

    def test_completed_and_partial_snapshots_survive_restart_without_collection(self):
        with tempfile.TemporaryDirectory() as directory, patch("assessment_server.subprocess.Popen") as process:
            root = Path(directory)
            for status in ("completed", "partial", "running"):
                run_root = root / status
                (run_root / "reports").mkdir(parents=True)
                artifacts = {
                    "assessment-manifest.json": {
                        "runId": status, "status": status, "startedAtUtc": "2026-01-01T00:00:00Z",
                        "analysisWindow": {"startUtc": "2025-12-01", "endUtc": "2026-01-01"},
                    },
                    "assessment-config.json": {},
                    "cost-reconciliation.json": {},
                    "attribution-coverage.json": {},
                    "telemetry-quality.json": {},
                    "benefits-baseline.json": {},
                }
                for name, data in artifacts.items():
                    (run_root / name).write_text(json.dumps(data), encoding="utf-8")
                (run_root / "reports" / "assessment-report.md").write_text("# Saved report", encoding="utf-8")
            service = AssessmentService(root, root, root / "index.html")
            self.assertEqual({item["runId"] for item in service.list_runs()}, {"completed", "partial"})
            service.save_review("completed", [{"findingId": "one", "decision": "deferred", "reviewer": "Tester"}])
            restarted = AssessmentService(root, root, root / "index.html")
            self.assertEqual(len(restarted.list_runs()), 2)
            results = map_results(resolve_run_root(root, "completed"))
            self.assertEqual(results["manifest"]["status"], "passed")
            self.assertEqual(results["review"][0]["reviewer"], "Tester")
            self.assertEqual(results["reportMarkdown"], "# Saved report")
            self.assertEqual(restarted.events("completed", 0)["events"][0]["type"], "completed")
            process.assert_not_called()

    def test_run_console_removes_terminal_color_escapes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            service = AssessmentService(root, root, root / "index.html")
            state = RunState("run", root / "temporary-config.json")
            state.process = Mock(stdout=io.StringIO("\x1b[33;1mWARNING: Waiting 61s before retry.\x1b[0m\n"), wait=Mock(return_value=0))
            service._monitor_run(state)
            event = state.snapshot(0)["events"][0]
            self.assertEqual(event["message"], "WARNING: Waiting 61s before retry.")
            self.assertEqual(event["level"], "warn")


if __name__ == "__main__":
    unittest.main()
