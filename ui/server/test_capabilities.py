import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from zipfile import ZipFile
from xml.etree import ElementTree

import capability_operations as operations
from assessment.model.capabilities import analyze, validate_options, commitment_scenario


def config():
    return {"analysis": {"startUtc": "2026-09-01T00:00:00Z", "endUtc": "2026-09-02T00:00:00Z"},
            "azure": {"tenantId": "test"}, "databricks": {"workspaces": [
                {"workspaceId": "42", "name": "Same name", "include": True},
                {"workspaceId": "43", "name": "Same name", "include": True}]},
            "capabilities": {"rules": {"minimumSamples": 1}}}


def evidence():
    return {
        "compute": [{"workspace_id": "42", "cluster_id": "c1", "cluster_name": "=unsafe", "num_workers": 2}],
        "node_timeline": [{"workspace_id": "42", "cluster_id": "c1", "instance_id": "n1", "driver": False,
                          "start_time": "2026-09-01T00:00:00Z", "end_time": "2026-09-01T00:01:00Z",
                          "cpu_user_percent": 0, "cpu_system_percent": 0, "mem_used_percent": 20,
                          "network_received_bytes": 1048576, "network_sent_bytes": 0}],
        "query": [{"workspace_id": "42", "statement_id": "q1", "start_time": "2026-09-01T00:00:00Z",
                   "execution_status": "FAILED", "total_duration_ms": 120000, "waiting_at_capacity_duration_ms": 2000}],
        "job": [{"workspace_id": "42", "job_id": "j1", "settings": {"name": "Job", "email_notifications": {"on_success": ["user"]}, "tasks": []}}],
        "job_run": [{"workspace_id": "42", "job_id": "j1", "run_id": "r1", "start_time": 1788220800000, "state": {"result_state": "FAILED"}}],
    }


class AnalysisTests(unittest.TestCase):
    def test_sql_complex_fields_decode_json_strings(self):
        data = evidence()
        data["query"][0]["compute"] = '{"warehouse_id":"warehouse-from-struct","type":"WAREHOUSE"}'
        data["compute"][0]["autoscale"] = '{"min_workers":1,"max_workers":4}'
        result = analyze(data, config())
        self.assertEqual(result["datasets"]["queries"][0]["warehouseId"], "warehouse-from-struct")
        self.assertEqual(result["datasets"]["sizing"][0]["maxWorkers"], 4)
        data["query"][0]["compute"] = "bad"
        with self.assertRaisesRegex(ValueError, "invalid JSON"):
            analyze(data, config())

    def test_single_native_task_object_preserves_failure_routing(self):
        data = evidence()
        data["job"][0]["settings"]["tasks"] = {"task_key": "single", "webhook_notifications": {"on_failure": [{"id": "test"}]}}
        row = analyze(data, config())["datasets"]["jobs"][0]
        self.assertEqual(row["tasks"], 1)
        self.assertEqual(row["failureAlerts"], "Configured")

    def test_legacy_redacted_notifications_are_unknown_not_failed(self):
        data = evidence()
        data["job"][0]["settings"]["email_notifications"] = "sha256:previous-redaction"
        result = analyze(data, config())
        self.assertEqual(result["datasets"]["jobs"][0]["failureAlerts"], "Unknown")
        self.assertFalse(any(f["title"] == "Verify failure notifications" for f in result["findings"]))

    def test_weighted_samples_and_boundary_network_rate(self):
        data = evidence()
        sample = data["node_timeline"][0]
        sample.update(start_time="2026-08-31T23:59:00Z", end_time="2026-09-01T00:01:00Z", cpu_user_percent=10)
        data["node_timeline"].append({**sample, "start_time": "2026-09-01T00:01:00Z", "end_time": "2026-09-01T00:04:00Z", "cpu_user_percent": 50})
        result = analyze(data, config())
        self.assertEqual(result["datasets"]["utilization"][0]["cpuPercent"], 40)
        self.assertAlmostEqual(result["datasets"]["network"][0]["detail"]["series"][0]["receivedMiBPerSecond"], 1 / 120)

    def test_invalid_percentages_and_query_time_are_unavailable(self):
        data = evidence()
        data["node_timeline"][0].update(cpu_user_percent=-2, mem_used_percent=101)
        data["query"][0]["start_time"] = "invalid"
        result = analyze(data, config())
        self.assertIsNone(result["datasets"]["utilization"][0]["cpuPercent"])
        self.assertEqual(result["datasets"]["sizing"][0]["status"], "No supported resize recommendation")
        self.assertEqual(result["datasets"]["queries"], [])
        self.assertTrue(any("query without" in text for text in result["limitations"]))
        self.assertEqual(result["workspaceCoverage"][0]["modules"]["posture"]["status"], "unavailable")

    def test_same_rule_has_unique_resource_finding_ids(self):
        data = evidence()
        data["compute"].append({**data["compute"][0], "workspace_id": "43"})
        data["node_timeline"].append({**data["node_timeline"][0], "workspace_id": "43"})
        findings = [f for f in analyze(data, config())["findings"] if f["domain"] == "sizing"]
        self.assertEqual(len(findings), 2)
        self.assertEqual(len({f["findingId"] for f in findings}), 2)

    def test_commitment_row_keys_distinguish_hours(self):
        data = evidence()
        data["commitment_demand"] = [{"workspace_id": "42", "sku": "D4", "hour": f"2026-09-01T0{i}:00:00Z"} for i in range(2)]
        rows = analyze(data, config())["datasets"]["commitments"]
        self.assertEqual(len({r["key"] for r in rows}), 2)

    def test_zero_missing_units_and_identity(self):
        data = evidence()
        data["compute"].append({"workspace_id": "43", "cluster_id": "c1", "cluster_name": "Missing"})
        result = analyze(data, config())
        first, missing = result["datasets"]["utilization"]
        self.assertEqual(first["cpuPercent"], 0)
        self.assertIsNone(missing["cpuPercent"])
        self.assertNotEqual(first["key"], missing["key"])
        self.assertEqual(result["datasets"]["network"][0]["receivedMiB"], 1)
        self.assertFalse(result["datasets"]["sizing"][0]["singleNode"])
        self.assertEqual(result["datasets"]["queries"][0]["queueSeconds"], 2)

    def test_no_worker_telemetry_not_single_node(self):
        data = evidence()
        data["node_timeline"][0]["driver"] = True
        self.assertFalse(analyze(data, config())["datasets"]["sizing"][0]["singleNode"])

    def test_missing_posture_not_failure(self):
        rows = analyze(evidence(), config())["datasets"]["posture"]
        self.assertTrue(all(r["status"] == "Unknown" for r in rows))

    def test_success_alert_not_failure_routing(self):
        result = analyze(evidence(), config())
        row = result["datasets"]["jobs"][0]
        self.assertEqual(row["failedRuns"], 1)
        self.assertEqual(row["failureAlerts"], "Not observed")
        self.assertTrue(any(f["domain"] == "jobs" for f in result["findings"]))

    def test_rule_validation(self):
        for options in ({"rules": {"madeUp": 2}}, {"concurrency": 5}, {"rules": {"idleCpuPercent": 90}}, {"rules": {"minimumSamples": .5}}):
            with self.assertRaises(ValueError):
                validate_options(options)

    def test_out_of_scope_and_out_of_window(self):
        data = evidence()
        data["compute"].append({"workspace_id": "999", "cluster_id": "outside"})
        data["node_timeline"][0]["start_time"] = "2020-01-01T00:00:00Z"
        data["node_timeline"][0]["end_time"] = "2020-01-01T00:01:00Z"
        rows = analyze(data, config())["datasets"]["utilization"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["samples"], 0)

    def test_commitment_conservation_and_missing(self):
        row = {"region": "eastus", "sku": "D4", "currency": "USD", "hour": "2026-09-01T00:00:00Z",
               "eligibleNodes": 10, "coveredNodes": 8, "onDemandHourlyRate": 1, "commitmentHourlyRate": .6}
        scenario = commitment_scenario([row], 3)
        self.assertEqual(scenario["baselineUncoveredCost"], 2)
        self.assertAlmostEqual(scenario["scenarioCost"], 1.8)
        with self.assertRaises(ValueError):
            commitment_scenario([], 1)
        with self.assertRaises(ValueError):
            commitment_scenario([row, row], 1)


class OperationsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def import_request(self):
        data = evidence()
        mapping = {"compute": "clusters", "node_timeline": "node-timeline", "query": "query-history", "job": "jobs", "job_run": "job-runs"}
        return {"workspaceId": "42", **config()["analysis"], "confirmed": True,
                "files": [{"name": f"{target}.json", "dataset": target, "content": json.dumps(data[source])} for source, target in mapping.items()]}

    def test_import_pipeline_workbook_reanalysis(self):
        request = self.import_request()
        preview = operations.import_evidence(self.root, request, preview=True)
        self.assertFalse(preview["costAvailable"])
        self.assertEqual(list(self.root.iterdir()), [])
        result = operations.import_evidence(self.root, request)
        root = self.root / result["runId"]
        data = operations.load(root / "capability-analysis.json")
        self.assertEqual(data["origin"], "imported")
        page = operations.dataset_page(root, "queries", {"limit": 50})
        self.assertEqual(page["total"], 1)
        relative = operations.workbook(root, ["utilization", "queries"])
        with ZipFile(root / relative) as z:
            for name in z.namelist():
                if name.endswith((".xml", ".rels")):
                    ElementTree.fromstring(z.read(name))
            contents = b"".join(z.read(n) for n in z.namelist())
            self.assertNotIn(b"<f>", contents)
            self.assertIn(b"=unsafe", contents)
        child = operations.reanalyze(self.root, root, {"rules": {"minimumSamples": 1}})
        self.assertNotEqual(child["runId"], result["runId"])
        self.assertEqual(operations.load(self.root / child["runId"] / "assessment-manifest.json")["parentRunId"], result["runId"])

    def test_scope_mismatch_rejected(self):
        request = self.import_request()
        request["workspaceId"] = "43"
        with self.assertRaisesRegex(ValueError, "mismatch"):
            operations.parse_import(request)

    def test_redaction_recursive(self):
        result = operations.protect({"statement_text": "select sensitive", "settings": {"owner": "person", "notebook_path": "/Users/person",
            "email_notifications": {"on_failure": ["person@example.test"], "on_success": []}, "base_parameters": {"data": "person"}}}, "salt")
        self.assertIsNone(result["statement_text"])
        self.assertNotIn("person", json.dumps(result))
        self.assertEqual(len(result["settings"]["email_notifications"]["on_failure"]), 1)
        self.assertEqual(result["settings"]["email_notifications"]["on_success"], [])

    def test_paging_scope_and_grouping_use_full_dataset(self):
        data = analyze(evidence(), config())
        data["datasets"]["queries"] = [{**data["datasets"]["queries"][0], "resourceId": str(i), "warehouseId": "w"} for i in range(65)]
        operations.save(self.root / "capability-analysis.json", data)
        self.assertEqual(len(operations.dataset_page(self.root, "queries", {"offset": 50})["rows"]), 15)
        self.assertEqual(operations.dataset_page(self.root, "queries", {"groupBy": "warehouseId"})["rows"][0]["queryCount"], 65)
        self.assertEqual(operations.dataset_page(self.root, "queries", {"workspaceId": ["43"]})["total"], 0)
        for request in ({"limit": 201}, {"offset": -1}, {"workspaceId": "42"}):
            with self.assertRaises(ValueError):
                operations.dataset_page(self.root, "queries", request)

    def test_failed_reanalysis_persists_failure_and_preserves_parent(self):
        root = self.root / operations.import_evidence(self.root, self.import_request())["runId"]
        original = (root / "assessment-manifest.json").read_bytes()
        with patch.object(operations, "run_pipeline", side_effect=ValueError("analysis failed")):
            with self.assertRaisesRegex(ValueError, "analysis failed"):
                operations.reanalyze(self.root, root, {})
        child = next(self.root.glob("analysis-*"))
        self.assertEqual(operations.load(child / "assessment-manifest.json")["status"], "failed")
        self.assertEqual((root / "assessment-manifest.json").read_bytes(), original)

    def test_workbook_error_does_not_leave_partial_artifact(self):
        data = analyze(evidence(), config())
        data["datasets"]["utilization"][0]["name"] = "x" * 32768
        operations.save(self.root / "capability-analysis.json", data)
        with self.assertRaisesRegex(ValueError, "cell exceeds"):
            operations.workbook(self.root, ["utilization"])
        self.assertEqual(list((self.root / "reports").iterdir()), [])

    def test_publication_failure_retains_unknown_audit(self):
        root = self.root / operations.import_evidence(self.root, self.import_request())["runId"]
        request = {"workspaceUrl": "adb-42.1.azuredatabricks.net", "warehouseId": "warehouse", "preview": True}
        client = Mock()
        factory = Mock(return_value=client)
        plan = operations.publish(root, request, factory)
        request.update(preview=False, confirmation=plan["confirmation"], confirmed=True, approveCompute=True)
        client.request.side_effect = TimeoutError("unknown remote outcome")
        with self.assertRaises(TimeoutError):
            operations.publish(root, request, factory)
        audit = operations.load(next((root / "reports").glob("publication-*.json")))
        self.assertEqual(audit["status"], "failed_or_unknown")
        with self.assertRaisesRegex(ValueError, "already attempted"):
            operations.publish(root, request, factory)

    def test_publication_explicit_and_no_retry(self):
        root = self.root / operations.import_evidence(self.root, self.import_request())["runId"]
        request = {"workspaceUrl": "adb-42.1.azuredatabricks.net", "warehouseId": "warehouse", "preview": True}
        client = Mock()
        client.request.side_effect = [{"dashboard_id": "test_dashboard"}, {}, {}]
        factory = Mock(return_value=client)
        preview = operations.publish(root, request, factory)
        factory.assert_not_called()
        request.update(preview=False)
        with self.assertRaises(ValueError):
            operations.publish(root, request, factory)
        request.update(confirmation=preview["confirmation"], confirmed=True, approveCompute=True)
        result = operations.publish(root, request, factory)
        self.assertEqual(result["status"], "published")
        self.assertFalse(client.request.call_args_list[1].args[2]["embed_credentials"])
        with self.assertRaisesRegex(ValueError, "already attempted"):
            operations.publish(root, request, factory)


if __name__ == "__main__":
    unittest.main()
