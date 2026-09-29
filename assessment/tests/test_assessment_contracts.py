import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ASSESSMENT_ROOT = Path(__file__).resolve().parents[1]
if str(ASSESSMENT_ROOT.parent) not in sys.path:
    sys.path.insert(0, str(ASSESSMENT_ROOT.parent))

from assessment.detectors import run_detectors
from assessment.model.core import (
    DATASET_MAP,
    MODEL_VERSION,
    attribution_coverage,
    build_normalized_model,
    canonical_azure_id,
    reconcile_costs,
    telemetry_quality,
)


def envelope(entity, identifier, **values):
    return {
        "schemaVersion": MODEL_VERSION,
        "entityType": entity,
        "sourceIdentifier": identifier,
        "normalized": values,
    }


class FixtureAndSchemaTests(unittest.TestCase):
    def test_all_example_configs_are_valid_json_and_scope_has_safety_defaults(self):
        config_root = ASSESSMENT_ROOT / "config"
        fixtures = {
            path.name: json.loads(path.read_text(encoding="utf-8-sig"))
            for path in config_root.glob("*.example.json")
        }
        self.assertEqual(
            {
                "allocation-rules.example.json",
                "assessment-scope.example.json",
                "tag-taxonomy.example.json",
            },
            set(fixtures),
        )
        scope = fixtures["assessment-scope.example.json"]
        self.assertFalse(scope["databricks"]["includeQueryText"])
        self.assertFalse(scope["databricks"]["includeNotebookPaths"])
        self.assertFalse(scope["databricks"]["includeIdentities"])
        self.assertTrue(scope["redaction"]["omitQueryText"])
        self.assertGreater(scope["analysis"]["collectorTimeoutSeconds"], 0)

    def test_dataset_mapping_covers_cost_inventory_and_workload_contracts(self):
        required_entities = {
            "azure_resource",
            "azure_cost",
            "workspace",
            "databricks_usage",
            "list_price",
            "compute",
            "job",
            "job_run",
            "pipeline",
            "warehouse",
            "query",
            "table",
            "policy",
            "budget",
        }
        self.assertTrue(required_entities.issubset(set(DATASET_MAP.values())))

    def test_normalized_envelope_has_versioned_required_fields(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            raw = root / "raw" / "azure"
            raw.mkdir(parents=True)
            (raw / "resource-inventory.ndjson").write_text(
                '{"id":"\\\\SUBSCRIPTIONS\\\\S\\\\RESOURCEGROUPS\\\\RG\\\\providers\\\\Microsoft.Databricks\\\\workspaces\\\\W"}\n',
                encoding="utf-8",
            )
            datasets, errors, inventory = build_normalized_model(
                root,
                {"customerId": "customer", "assessmentId": "assessment"},
                {"runId": "run"},
            )
            self.assertFalse(errors)
            inventory_entry = next(
                value
                for key, value in inventory.items()
                if key.replace("\\", "/") == "raw/azure/resource-inventory.ndjson"
            )
            self.assertEqual(1, inventory_entry["recordCount"])
            row = datasets["azure_resource"][0]
            self.assertEqual(
                {
                    "schemaVersion",
                    "entityType",
                    "assessmentRunId",
                    "sourceSystem",
                    "sourceIdentifier",
                    "sourceExtractionTimestamp",
                    "effectiveStartUtc",
                    "effectiveEndUtc",
                    "customerScope",
                    "collectionStatus",
                    "qualityFlags",
                    "sensitivityClassification",
                    "normalized",
                    "provenance",
                },
                set(row),
            )
            self.assertEqual(
                "/subscriptions/s/resourcegroups/rg/providers/microsoft.databricks/workspaces/w",
                row["normalized"]["canonicalResourceId"],
            )
            self.assertEqual(
                "/subscriptions/s/resourcegroups/rg",
                canonical_azure_id("/SUBSCRIPTIONS/S/RESOURCEGROUPS/RG/"),
            )


class ReconciliationEdgeCaseTests(unittest.TestCase):
    def test_corrections_are_preserved_and_actual_and_amortized_remain_separate(self):
        costs = [
            envelope("azure_cost", "a", costBasis="ActualCost", PreTaxCost=100, Currency="USD"),
            envelope("azure_cost", "correction", costBasis="ActualCost", PreTaxCost=-25, Currency="USD"),
            envelope("azure_cost", "b", costBasis="AmortizedCost", PreTaxCost=60, Currency="USD"),
        ]
        for item in costs:
            item["correlation"] = {"status": "matched"}
        result = reconcile_costs(
            {"azure_cost": costs},
            {"azure": {"reportingCostBasis": "ActualCost", "currency": "USD"}},
        )
        self.assertEqual({"ActualCost": 75.0, "AmortizedCost": 60.0}, result["authoritativeTotals"])
        self.assertEqual(75, result["authoritativeTotal"])

    def test_price_boundaries_do_not_overlap(self):
        usage = [
            envelope(
                "databricks_usage",
                "u",
                sku_name="JOBS",
                usage_quantity=2,
                usage_start_time="2026-02-01T00:00:00Z",
            )
        ]
        prices = [
            envelope(
                "list_price",
                "old",
                sku_name="JOBS",
                price=3,
                price_start_time="2026-01-01T00:00:00Z",
                price_end_time="2026-02-01T00:00:00Z",
            ),
            envelope(
                "list_price",
                "new",
                sku_name="JOBS",
                price=5,
                price_start_time="2026-02-01T00:00:00Z",
            ),
        ]
        result = reconcile_costs(
            {"databricks_usage": usage, "list_price": prices},
            {"azure": {"currency": "USD"}},
        )
        self.assertEqual(10, result["databricksListPriceEstimate"])
        self.assertEqual(0, result["unmatchedDatabricksUsageRecords"])

    def test_serverless_dbu_is_not_added_when_azure_already_contains_databricks_cost(self):
        azure = envelope(
            "azure_cost",
            "a",
            costBasis="ActualCost",
            PreTaxCost=50,
            Currency="USD",
            ServiceName="Azure Databricks",
        )
        azure["correlation"] = {"status": "matched"}
        result = reconcile_costs(
            {
                "azure_cost": [azure],
                "databricks_usage": [
                    envelope(
                        "databricks_usage",
                        "u",
                        sku_name="SERVERLESS_JOBS",
                        usage_quantity=4,
                        usage_start_time="2026-01-15T00:00:00Z",
                    )
                ],
                "list_price": [envelope("list_price", "p", sku_name="SERVERLESS_JOBS", price=5)],
            },
            {"azure": {"currency": "USD"}},
        )
        self.assertEqual(20, result["duplicatePrevention"]["serverlessDbuCost"])
        self.assertEqual(0, result["databricksListPriceAddedToAzure"])
        self.assertEqual(50, result["collectedTotal"])

    def test_multiple_currencies_are_explicitly_non_aggregatable(self):
        costs = [
            envelope("azure_cost", "usd", costBasis="ActualCost", PreTaxCost=10, Currency="USD"),
            envelope("azure_cost", "eur", costBasis="ActualCost", PreTaxCost=10, Currency="EUR"),
        ]
        result = reconcile_costs({"azure_cost": costs}, {"azure": {}})
        self.assertFalse(result["currencyAggregationAllowed"])
        self.assertIn("Multiple currencies", result["limitations"][0])

    def test_unmatched_and_attributed_cost_are_independent(self):
        owned = envelope("azure_cost", "owned", PreTaxCost=80, tags={"owner": "team"})
        unowned = envelope("azure_cost", "unowned", PreTaxCost=20, tags={})
        coverage = attribution_coverage({"azure_cost": [owned, unowned]})
        self.assertEqual(50, coverage["resourceCoveragePercent"])
        self.assertEqual(80, coverage["spendCoveragePercent"])


class TelemetryAndDetectorTests(unittest.TestCase):
    def test_parse_errors_reduce_source_consistency_and_empty_sources_are_insufficient(self):
        inventory = {
            "raw/good.ndjson": {"recordCount": 3, "parseErrorCount": 0},
            "raw/partial.ndjson": {"recordCount": 1, "parseErrorCount": 1},
            "raw/empty.ndjson": {"recordCount": 0, "parseErrorCount": 0},
        }
        quality = telemetry_quality(inventory, {"compute": [{}, {}, {}]})
        by_source = {item["source"]: item for item in quality["sources"]}
        self.assertEqual("high", by_source["raw/good.ndjson"]["level"])
        self.assertLess(
            by_source["raw/partial.ndjson"]["metrics"]["consistency"],
            by_source["raw/good.ndjson"]["metrics"]["consistency"],
        )
        self.assertEqual("insufficient", by_source["raw/empty.ndjson"]["level"])

    def test_partial_collection_status_reduces_quality(self):
        inventory = {
            "raw/source-status.json": {
                "recordCount": 3,
                "parseErrorCount": 0,
                "reportedStatuses": ["passed", "partial", "pending telemetry"],
            }
        }
        quality = telemetry_quality(inventory, {"compute": [{}]})
        source = quality["sources"][0]
        self.assertLessEqual(source["metrics"]["collectionSuccess"], 0.5)
        self.assertNotEqual("high", quality["overall"]["level"])

    def test_driver_spot_detector_excludes_spot_workers_with_on_demand_driver(self):
        safe = {
            "compute": [
                envelope(
                    "compute",
                    "safe",
                    driver_availability="on_demand",
                    worker_availability="spot_with_fallback",
                    autoscale={"min_workers": 1, "max_workers": 4},
                )
            ],
            "azure_cost": [envelope("azure_cost", "cost", PreTaxCost=1, tags={"Owner": "x"})],
            "job": [envelope("job", "job", settings={"new_cluster": {}})],
            "budget": [envelope("budget", "budget")],
        }
        unsafe = {
            **safe,
            "compute": [envelope("compute", "unsafe", driver_availability="spot_with_fallback")],
        }
        safe_ids = {item["detectorId"] for item in run_detectors(safe, {"thresholds": {}})}
        unsafe_findings = run_detectors(unsafe, {"thresholds": {}})
        self.assertNotIn("WRK-DRIVER-ON-SPOT", safe_ids)
        spot = next(item for item in unsafe_findings if item["detectorId"] == "WRK-DRIVER-ON-SPOT")
        self.assertEqual("candidate", spot["status"])
        self.assertTrue(spot["humanValidationRequired"])
        self.assertIsNone(spot["estimatedSavings"])

    def test_every_candidate_has_evidence_confidence_action_and_human_validation(self):
        datasets = {
            "compute": [
                envelope("compute", "c1", cluster_source="UI", autotermination_minutes=61),
                envelope("compute", "c2", num_workers=2, driver_is_spot=True),
            ],
            "node_timeline": [envelope("node_timeline", "n1", cluster_id="c2")],
            "azure_cost": [envelope("azure_cost", "cost", PreTaxCost=100, tags={})],
            "job": [
                envelope(
                    "job",
                    "job",
                    settings={"existing_cluster_id": "c1", "schedule": {"pause_status": "UNPAUSED"}},
                )
            ],
        }
        candidates = [
            item for item in run_detectors(
                datasets,
                {"thresholds": {"materialMonthlyCost": 100, "interactiveAutoTerminationMinutes": 60}},
            )
            if item["status"] == "candidate"
        ]
        self.assertGreaterEqual(len(candidates), 5)
        for item in candidates:
            self.assertTrue(item["evidence"])
            self.assertIn(item["confidence"]["level"], {"high", "medium", "low"})
            self.assertTrue(item["recommendedAction"])
            self.assertTrue(item["humanValidationRequired"])


class SyntheticEndToEndTests(unittest.TestCase):
    def _run_pipeline(self, root: Path, workspaces: int, serverless: bool) -> dict:
        config = root / "scope.json"
        config.write_text(
            json.dumps(
                {
                    "customerId": "customer",
                    "assessmentId": "assessment",
                    "azure": {"currency": "USD", "subscriptions": ["sub-a", "sub-b"]},
                    "databricks": {
                        "workspaces": [
                            {
                                "workspaceId": str(index),
                                "workspaceResourceId": f"/subscriptions/sub-a/resourceGroups/rg-{index}/providers/Microsoft.Databricks/workspaces/ws-{index}",
                                "include": True,
                            }
                            for index in range(workspaces)
                        ],
                        "includeQueryText": False,
                    },
                    "analysis": {
                        "startUtc": "2026-01-01T00:00:00Z",
                        "endUtc": "2026-02-01T00:00:00Z",
                    },
                    "thresholds": {},
                }
            ),
            encoding="utf-8",
        )
        run_root = root / "run"
        azure = run_root / "raw" / "azure"
        azure.mkdir(parents=True)
        (azure / "cost-management.ndjson").write_text(
            json.dumps(
                {
                    "costBasis": "ActualCost",
                    "PreTaxCost": 25,
                    "Currency": "USD",
                    "ServiceName": "Virtual Machines",
                    "ResourceId": "/subscriptions/sub-a/resourceGroups/rg-0/providers/Microsoft.Compute/virtualMachines/worker",
                    "isServerless": serverless,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        for index in range(workspaces):
            workspace = run_root / "raw" / "databricks" / str(index)
            workspace.mkdir(parents=True)
            (workspace / "workspace-inventory.ndjson").write_text(
                json.dumps({"workspaceId": str(index), "workspaceName": f"ws-{index}"}) + "\n",
                encoding="utf-8",
            )
        command = [
            sys.executable,
            str(ASSESSMENT_ROOT / "pipeline" / "run_assessment.py"),
            "--config",
            str(config),
            "--run-root",
            str(run_root),
        ]
        first = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertEqual(0, first.returncode, first.stderr)
        normalized_before = {
            path.name: path.read_bytes()
            for path in (run_root / "normalized").glob("*")
        }
        second = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertEqual(0, second.returncode, second.stderr)
        normalized_after = {
            path.name: path.read_bytes()
            for path in (run_root / "normalized").glob("*")
        }
        self.assertEqual(normalized_before, normalized_after)
        return {
            path.name: json.loads(path.read_text(encoding="utf-8"))
            for path in run_root.glob("*.json")
        }

    def test_repeated_multi_subscription_multi_workspace_classic_run(self):
        with tempfile.TemporaryDirectory() as temp:
            outputs = self._run_pipeline(Path(temp), workspaces=2, serverless=False)
            self.assertEqual(MODEL_VERSION, outputs["cost-reconciliation.json"]["schemaVersion"])
            self.assertIn("errors.json", outputs)
            self.assertIn("benefits-baseline.json", outputs)

    def test_repeated_single_workspace_serverless_run(self):
        with tempfile.TemporaryDirectory() as temp:
            outputs = self._run_pipeline(Path(temp), workspaces=1, serverless=True)
            duplicate = outputs["cost-reconciliation.json"]["duplicatePrevention"]
            self.assertEqual(25, duplicate["serverlessVmCostNotAdded"])
            self.assertEqual(0, outputs["cost-reconciliation.json"]["collectedTotal"])

    def test_pipeline_promotes_partial_collector_status_to_errors_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = root / "scope.json"
            config.write_text(
                json.dumps({
                    "customerId": "customer",
                    "assessmentId": "assessment",
                    "azure": {"currency": "USD"},
                    "analysis": {
                        "startUtc": "2026-01-01T00:00:00Z",
                        "endUtc": "2026-02-01T00:00:00Z",
                    },
                    "thresholds": {},
                }),
                encoding="utf-8",
            )
            run_root = root / "run"
            (run_root / "raw").mkdir(parents=True)
            (run_root / "collection-status.json").write_text(
                json.dumps([{
                    "name": "Databricks billing",
                    "status": "pending telemetry",
                    "limitations": ["SQL Warehouse ID is required."],
                }]),
                encoding="utf-8",
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ASSESSMENT_ROOT / "pipeline" / "run_assessment.py"),
                    "--config",
                    str(config),
                    "--run-root",
                    str(run_root),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(0, completed.returncode, completed.stderr)
            errors = json.loads((run_root / "errors.json").read_text(encoding="utf-8"))["errors"]
            self.assertEqual("collector_status", errors[0]["kind"])
            self.assertEqual("pending telemetry", errors[0]["status"])


if __name__ == "__main__":
    unittest.main()
