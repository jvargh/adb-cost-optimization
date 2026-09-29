import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ASSESSMENT_ROOT = Path(__file__).resolve().parents[2]
if str(ASSESSMENT_ROOT.parent) not in sys.path:
    sys.path.insert(0, str(ASSESSMENT_ROOT.parent))

from assessment.detectors import run_detectors
from assessment.model.core import (
    attribution_coverage,
    build_normalized_model,
    confidence_from_metrics,
    correlate_model,
    filter_databricks_scope,
    read_records,
    reconcile_costs,
)


def envelope(entity, identifier, **values):
    return {
        "schemaVersion": "1.0",
        "entityType": entity,
        "sourceIdentifier": identifier,
        "normalized": values,
    }


class ModelInputTests(unittest.TestCase):
    def test_hashed_table_datasets_are_normalized_with_original_provenance(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            raw = root / "raw" / "databricks" / "workspace"
            raw.mkdir(parents=True)
            for name, entity in (("table-detail", "table_file_summary"), ("table-history", "table_operation")):
                filename = f"{name}-0123456789abcdef.ndjson"
                (raw / filename).write_text('{"id":"table","numFiles":12}\n', encoding="utf-8")
                (raw / f"{name}-source-status.json").write_text('{"status":"failed"}', encoding="utf-8")
            datasets, errors, inventory = build_normalized_model(root, {}, {})
            self.assertFalse(errors)
            for name, entity in (("table-detail", "table_file_summary"), ("table-history", "table_operation")):
                self.assertEqual(len(datasets[entity]), 1)
                item = datasets[entity][0]
                self.assertTrue(item["provenance"]["sourceFile"].endswith(f"{name}-0123456789abcdef.ndjson"))
                self.assertEqual(item["customerScope"]["workspaceKey"], "workspace")
                self.assertEqual(inventory[item["provenance"]["sourceFile"]]["mappedEntity"], entity)

    def test_azure_budget_envelope_reaches_detector_without_mapping_commitments_as_budgets(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            raw = root / "raw" / "azure"
            raw.mkdir(parents=True)
            (raw / "budgets-commitments.json").write_text(json.dumps({
                "budgets": [{"id": "/subscriptions/s/providers/Microsoft.Consumption/budgets/b"}],
                "reservations": [{"id": "reservation"}], "savingsPlans": [],
            }))
            datasets, errors, _ = build_normalized_model(root, {}, {})
            self.assertFalse(errors)
            self.assertEqual(len(datasets["budget"]), 1)
            datasets["azure_cost"] = [envelope("azure_cost", "cost", PreTaxCost=10)]
            self.assertNotIn("MON-MISSING-BUDGET", [f["detectorId"] for f in run_detectors(datasets, {})])

    def test_reads_json_array_object_and_partial_ndjson(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            array = root / "array.json"
            array.write_text('[{"id": 1}]', encoding="utf-8")
            self.assertEqual(read_records(array)[0][0]["id"], 1)
            obj = root / "object.json"
            obj.write_text('{"value": [{"id": 2}]}', encoding="utf-8")
            self.assertEqual(read_records(obj)[0][0]["id"], 2)
            ndjson = root / "rows.ndjson"
            ndjson.write_text('{"id": 3}\nnot-json\n{"id": 4}\n', encoding="utf-8")
            records, errors = read_records(ndjson)
            self.assertEqual([3, 4], [item["id"] for item in records])
            self.assertEqual(1, len(errors))

    def test_mapping_preserves_raw_provenance_and_schema(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            raw = root / "raw" / "azure"
            raw.mkdir(parents=True)
            (raw / "resource-inventory.ndjson").write_text(
                '{"id":"/SUBSCRIPTIONS/A/resourceGroups/R/providers/Microsoft.Databricks/workspaces/W","name":"W"}\n',
                encoding="utf-8",
            )
            datasets, errors, _ = build_normalized_model(
                root, {"customerId": "c", "assessmentId": "a"}, {"runId": "r"}
            )
            item = datasets["azure_resource"][0]
            self.assertFalse(errors)
            self.assertEqual("1.0", item["schemaVersion"])
            self.assertEqual("/SUBSCRIPTIONS/A/resourceGroups/R/providers/Microsoft.Databricks/workspaces/W", item["provenance"]["raw"]["id"])
            self.assertEqual("/subscriptions/a/resourcegroups/r/providers/microsoft.databricks/workspaces/w", item["normalized"]["canonicalResourceId"])


class ModelCorrelationTests(unittest.TestCase):
    def test_filters_and_deduplicates_to_selected_databricks_resource_groups(self):
        workspace = envelope(
            "workspace",
            "workspace",
            name="dbw",
            resourceGroup="workshop-rg",
            properties={
                "managedResourceGroupId": "/subscriptions/s/resourceGroups/managed-rg",
            },
        )
        workspace_resource = envelope(
            "azure_resource",
            "workspace-resource",
            canonicalResourceId="/subscriptions/s/resourcegroups/workshop-rg/providers/microsoft.databricks/workspaces/dbw",
            resourceGroup="workshop-rg",
            type="microsoft.databricks/workspaces",
        )
        managed_resource = envelope(
            "azure_resource",
            "managed-resource",
            canonicalResourceId="/subscriptions/s/resourcegroups/managed-rg/providers/microsoft.compute/virtualmachines/worker",
            resourceGroup="managed-rg",
            type="microsoft.compute/virtualmachines",
        )
        duplicate_managed_resource = envelope(
            "azure_resource",
            "managed-resource-duplicate",
            **managed_resource["normalized"],
        )
        unrelated_resource = envelope(
            "azure_resource",
            "unrelated",
            canonicalResourceId="/subscriptions/s/resourcegroups/unrelated-rg/providers/microsoft.search/searchservices/search",
            resourceGroup="unrelated-rg",
            type="microsoft.search/searchservices",
        )
        in_scope_cost = envelope(
            "azure_cost",
            "in-scope-cost",
            canonicalResourceId=managed_resource["normalized"]["canonicalResourceId"],
            ResourceId=managed_resource["normalized"]["canonicalResourceId"],
            PreTaxCost=10,
        )
        unrelated_cost = envelope(
            "azure_cost",
            "unrelated-cost",
            canonicalResourceId=unrelated_resource["normalized"]["canonicalResourceId"],
            ResourceId=unrelated_resource["normalized"]["canonicalResourceId"],
            PreTaxCost=100,
        )
        datasets = {
            "workspace": [workspace],
            "azure_resource": [
                workspace_resource,
                managed_resource,
                duplicate_managed_resource,
                unrelated_resource,
            ],
            "azure_cost": [in_scope_cost, unrelated_cost],
        }

        result = filter_databricks_scope(
            datasets,
            {
                "azure": {"resourceGroups": ["workshop-rg"]},
                "databricks": {"workspaces": [{"name": "dbw", "resourceGroup": "workshop-rg", "include": True}]},
            },
        )

        self.assertEqual(["managed-rg", "workshop-rg"], result["allowedResourceGroups"])
        self.assertEqual(2, len(datasets["azure_resource"]))
        self.assertEqual(1, len(datasets["azure_cost"]))
        self.assertEqual(1, result["entities"]["azure_cost"]["excludedRecords"])
        self.assertEqual(2, result["entities"]["azure_resource"]["excludedRecords"])

    def test_correlates_ids_without_forcing_ambiguous_workspace(self):
        resource = envelope(
            "azure_resource", "az",
            id="/subscriptions/s/resourceGroups/rg/providers/Microsoft.Databricks/workspaces/ws",
            canonicalResourceId="/subscriptions/s/resourcegroups/rg/providers/microsoft.databricks/workspaces/ws",
            name="ws", resourceGroup="rg", type="microsoft.databricks/workspaces",
        )
        workspace = envelope("workspace", "123", workspaceId="123", workspaceName="ws", resourceGroup="rg")
        cost = envelope(
            "azure_cost", "cost",
            ResourceId=resource["normalized"]["id"],
            canonicalResourceId=resource["normalized"]["canonicalResourceId"],
            PreTaxCost=10,
        )
        datasets = {"azure_resource": [resource], "workspace": [workspace], "azure_cost": [cost]}
        result = correlate_model(datasets)
        self.assertEqual("matched", workspace["correlation"]["status"])
        self.assertEqual(1, result["matchedAzureCostRecords"])

        duplicate = envelope("azure_resource", "az2", **resource["normalized"])
        second_workspace = envelope("workspace", "124", workspaceName="ws", resourceGroup="rg")
        result = correlate_model({"azure_resource": [resource, duplicate], "workspace": [second_workspace]})
        self.assertEqual("ambiguous", second_workspace["correlation"]["status"])
        self.assertEqual("ambiguous", result["unmatched"][0]["status"])


class QualifiedScopeTests(unittest.TestCase):
    sub_a = "11111111-1111-1111-1111-111111111111"
    sub_b = "22222222-2222-2222-2222-222222222222"

    def setUp(self):
        self.group_a = f"/subscriptions/{self.sub_a}/resourcegroups/shared"
        self.group_b = f"/subscriptions/{self.sub_b}/resourcegroups/other"
        self.collision = f"/subscriptions/{self.sub_b}/resourcegroups/shared"
        self.other_collision = f"/subscriptions/{self.sub_a}/resourcegroups/other"
        self.managed_a = f"/subscriptions/{self.sub_a}/resourcegroups/managed"
        self.managed_b = f"/subscriptions/{self.sub_b}/resourcegroups/managed-other"
        self.managed_collision = f"/subscriptions/{self.sub_b}/resourcegroups/managed"
        self.groups = [
            self.group_a, self.group_b, self.collision, self.other_collision,
            self.managed_a, self.managed_b, self.managed_collision,
        ]
        self.config = {
            "azure": {
                "subscriptions": [self.sub_a, self.sub_b],
                "resourceGroupIds": [self.group_a.upper(), self.group_b],
                "resourceGroups": ["shared", "other"],
            },
        }
        self.workspaces = []
        for group, managed in (
            (self.group_a, self.managed_a),
            (self.group_b, self.managed_b),
            (self.collision, self.managed_collision),
        ):
            identifier = f"{group}/providers/microsoft.databricks/workspaces/dbw"
            self.workspaces.append(envelope(
                "workspace", identifier, id=identifier, name="dbw",
                properties={"managedResourceGroupId": managed},
            ))
        self.datasets = {"workspace": self.workspaces}
        for entity in ("azure_resource", "azure_cost", "owner"):
            self.datasets[entity] = [
                envelope(
                    entity, group,
                    canonicalResourceId=f"{group}/providers/microsoft.compute/virtualmachines/vm",
                    # A conflicting name must never override the ARM identity.
                    resourceGroup="shared",
                )
                for group in self.groups
            ] + [envelope(entity, "unqualified", resourceGroup="shared")]

    def test_qualified_groups_are_exact_not_a_subscription_name_cross_product(self):
        result = filter_databricks_scope(self.datasets, self.config)
        expected = {self.group_a, self.group_b, self.managed_a, self.managed_b}
        self.assertEqual(expected, set(result["allowedResourceGroupIds"]))
        for entity in ("azure_resource", "azure_cost", "owner"):
            self.assertEqual(expected, {item["sourceIdentifier"] for item in self.datasets[entity]})
            self.assertEqual(4, result["entities"][entity]["excludedRecords"])
        self.assertEqual(2, len(self.datasets["workspace"]))

    def test_excluded_workspace_with_same_name_does_not_extend_managed_scope(self):
        self.config["databricks"] = {"workspaces": [
            {"workspaceResourceId": self.workspaces[0]["normalized"]["id"], "include": True},
            {"resourceId": self.workspaces[1]["normalized"]["id"], "include": False},
        ]}
        result = filter_databricks_scope(self.datasets, self.config)
        self.assertIn(self.managed_a, result["allowedResourceGroupIds"])
        self.assertNotIn(self.managed_b, result["allowedResourceGroupIds"])
        self.assertNotIn(self.managed_collision, result["allowedResourceGroupIds"])
        self.assertEqual(1, len(self.datasets["workspace"]))

    def test_legacy_names_apply_across_selected_subscriptions_only(self):
        del self.config["azure"]["resourceGroupIds"]
        self.config["azure"]["resourceGroups"] = ["shared"]
        self.datasets["azure_resource"].append(envelope(
            "azure_resource", "unselected-sub",
            canonicalResourceId="/subscriptions/third/resourcegroups/shared/providers/microsoft.compute/virtualmachines/vm",
        ))
        result = filter_databricks_scope(self.datasets, self.config)
        self.assertEqual(
            {self.group_a, self.collision, self.managed_a, self.managed_collision},
            set(result["allowedResourceGroupIds"]),
        )
        self.assertNotIn("unselected-sub", [item["sourceIdentifier"] for item in self.datasets["azure_resource"]])
        self.assertNotIn(self.group_b, result["allowedResourceGroupIds"])

    def test_empty_qualified_groups_ignore_names_but_keep_databricks_related_boundary(self):
        self.config["azure"]["resourceGroupIds"] = []
        self.config["azure"]["resourceGroups"] = ["obsolete"]
        result = filter_databricks_scope(self.datasets, self.config)
        self.assertEqual(
            {self.group_a, self.group_b, self.collision, self.managed_a, self.managed_b, self.managed_collision},
            set(result["allowedResourceGroupIds"]),
        )
        self.assertNotIn(self.other_collision, [item["sourceIdentifier"] for item in self.datasets["azure_resource"]])

    def test_empty_inventory_does_not_allow_subscription_wide_azure_data(self):
        self.config["azure"]["resourceGroupIds"] = []
        self.datasets["workspace"] = []
        result = filter_databricks_scope(self.datasets, self.config)
        self.assertEqual([], result["allowedResourceGroupIds"])
        self.assertTrue(result["limitations"])
        for entity in ("azure_resource", "azure_cost", "owner"):
            self.assertEqual([], self.datasets[entity])

    def test_configured_arm_workspace_group_is_preserved_without_cross_subscription_inference(self):
        self.config["azure"]["resourceGroupIds"] = []
        self.config["databricks"] = {"workspaces": [
            {"workspaceResourceId": self.workspaces[0]["normalized"]["id"], "include": True},
        ]}
        self.datasets["workspace"] = []
        result = filter_databricks_scope(self.datasets, self.config)
        self.assertEqual([self.group_a], result["allowedResourceGroupIds"])

    def test_qualified_workspace_subscription_and_group_match_without_arm_id(self):
        self.config["databricks"] = {"workspaces": [
            {"subscriptionId": self.sub_a, "resourceGroup": "shared", "name": "dbw", "include": True},
        ]}
        result = filter_databricks_scope(self.datasets, self.config)
        self.assertIn(self.managed_a, result["allowedResourceGroupIds"])
        self.assertNotIn(self.managed_b, result["allowedResourceGroupIds"])
        self.assertEqual(1, len(self.datasets["workspace"]))

    def test_invalid_qualified_groups_fail_explicitly(self):
        for value in ("shared", "/subscriptions/third/resourceGroups/shared", self.workspaces[0]["normalized"]["id"]):
            with self.subTest(value=value):
                self.config["azure"]["resourceGroupIds"] = [value]
                with self.assertRaises(ValueError):
                    filter_databricks_scope(self.datasets, self.config)

    def test_explicit_empty_workspace_selection_cannot_expand_from_account_inventory(self):
        self.config["azure"]["resourceGroupIds"] = []
        self.config["databricks"] = {"workspaces": []}
        result = filter_databricks_scope(self.datasets, self.config)
        self.assertEqual([], self.datasets["workspace"])
        self.assertEqual([], result["allowedResourceGroupIds"])
        self.assertEqual([], self.datasets["azure_resource"])

    def test_stale_template_derived_groups_are_not_scope_evidence(self):
        self.config["azure"]["allowedResourceGroups"] = ["template-allowed"]
        self.config["azure"]["supportResourceGroupIds"] = [self.managed_collision]
        self.config["model"] = {"allowedResourceGroupIds": [self.other_collision]}
        self.config["databricks"] = {"workspaces": [{
            "workspaceResourceId": self.workspaces[0]["normalized"]["id"],
            "workspaceId": "123",
            "include": True,
            "properties": {"managedResourceGroupId": self.managed_collision},
        }]}
        self.datasets["workspace"] = [envelope("workspace", "123", workspace_id="123", workspace_name="dbw")]
        result = filter_databricks_scope(self.datasets, self.config)
        self.assertEqual({self.group_a, self.group_b}, set(result["allowedResourceGroupIds"]))
        self.assertEqual(["other", "shared"], result["allowedResourceGroups"])

    def test_broad_account_inventory_is_filtered_before_persisting_normalized_reports(self):
        self.config["databricks"] = {"workspaces": [{
            "workspaceResourceId": self.workspaces[0]["normalized"]["id"],
            "name": "dbw",
            "workspaceId": "123",
            "include": True,
        }]}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            account = root / "raw" / "databricks" / "account"
            account.mkdir(parents=True)
            (account / "account-workspaces.json").write_text(json.dumps([
                {"workspace_id": 123, "workspace_name": "dbw"},
                {"workspace_id": 456, "workspace_name": "dbw"},
                {"workspace_id": 789, "workspace_name": "old-template-workspace"},
                {"workspace_id": 999, "workspace_name": "foreign", "id": self.workspaces[2]["normalized"]["id"]},
            ]), encoding="utf-8")
            config_path = root / "config.json"
            config_path.write_text(json.dumps(self.config), encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, str(ASSESSMENT_ROOT / "pipeline" / "run_assessment.py"),
                 "--config", str(config_path), "--run-root", str(root)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(0, completed.returncode, completed.stderr)
            records = read_records(root / "normalized" / "workspace.ndjson")[0]
            self.assertEqual(["123"], [item["sourceIdentifier"] for item in records])
            report = (root / "reports" / "assessment-report.md").read_text(encoding="utf-8")
            self.assertNotIn("old-template-workspace", report)
            self.assertNotIn("foreign", report)
            scope = json.loads((root / "scope-filter.json").read_text(encoding="utf-8"))
            self.assertEqual(3, scope["entities"]["workspace"]["excludedRecords"])
            self.assertEqual({self.group_a, self.group_b}, set(scope["allowedResourceGroupIds"]))

    def test_pipeline_persists_exact_scope_and_databricks_only_report(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            raw = root / "raw" / "azure"
            raw.mkdir(parents=True)
            config_path = root / "config.json"
            config_path.write_text(json.dumps(self.config), encoding="utf-8")
            (root / "assessment-manifest.json").write_text(json.dumps({
                "scope": self.config["azure"],
            }), encoding="utf-8")
            (raw / "databricks-workspaces.json").write_text(json.dumps([
                item["normalized"] for item in self.workspaces
            ]), encoding="utf-8")
            (raw / "resource-inventory.ndjson").write_text("".join(
                json.dumps({"id": item["normalized"].get("canonicalResourceId"), "name": item["sourceIdentifier"]}) + "\n"
                for item in self.datasets["azure_resource"]
            ), encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, str(ASSESSMENT_ROOT / "pipeline" / "run_assessment.py"),
                 "--config", str(config_path), "--run-root", str(root)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(0, completed.returncode, completed.stderr)
            rows = read_records(root / "normalized" / "azure_resource.ndjson")[0]
            self.assertEqual(4, len(rows))
            report = (root / "reports" / "assessment-report.md").read_text(encoding="utf-8")
            self.assertIn("Resource group IDs", report)
            self.assertIn(self.group_a, report)
            self.assertIn(self.managed_b, report)
            self.assertNotIn(self.collision + "/", report)
            self.assertNotIn(self.managed_collision + "/", report)
            scope = json.loads((root / "scope-filter.json").read_text(encoding="utf-8"))
            self.assertEqual(
                {self.group_a, self.group_b, self.managed_a, self.managed_b},
                set(scope["allowedResourceGroupIds"]),
            )


class ModelReconciliationTests(unittest.TestCase):
    def test_actual_collector_price_shape_and_serverless_service_charge_are_retained(self):
        datasets = {
            "azure_cost": [
                envelope("azure_cost", "a", costBasis="ActualCost", PreTaxCost=7, Currency="USD",
                         ServiceName="Azure Databricks", Meter="Serverless Compute"),
                envelope("azure_cost", "b", costBasis="AmortizedCost", PreTaxCost=6, Currency="USD",
                         ServiceName="Azure Databricks", Meter="Serverless Compute"),
            ],
            "databricks_usage": [envelope("databricks_usage", "u", sku_name="JOBS", usage_quantity=2)],
            "list_price": [envelope("list_price", "p", sku_name="JOBS",
                                   pricing='{"default":"5","effective_list":{"default":"4"}}')],
        }
        result = reconcile_costs(datasets, {"azure": {"reportingCostBasis": "ActualCost"}})
        self.assertEqual(result["databricksListPriceEstimate"], 8)
        self.assertEqual(result["unmatchedDatabricksUsageRecords"], 0)
        self.assertEqual(result["collectedTotal"], 7)
        self.assertEqual(result["unmatchedCost"], 7)
        self.assertEqual(result["excludedCost"], 0)
        self.assertEqual(result["varianceAmount"], 0)
        self.assertEqual(result["databricksListPriceAddedToAzure"], 0)

    def test_unparseable_pricing_keeps_an_explicit_gap(self):
        result = reconcile_costs({
            "databricks_usage": [envelope("databricks_usage", "u", sku_name="JOBS", usage_quantity=2)],
            "list_price": [envelope("list_price", "p", sku_name="JOBS", pricing="invalid JSON")],
        }, {})
        self.assertEqual(result["unmatchedDatabricksUsageRecords"], 1)
        self.assertTrue(any("could not be priced" in text for text in result["limitations"]))

    def test_actual_amortized_list_price_and_serverless_double_count(self):
        azure = [
            envelope("azure_cost", "a", costBasis="ActualCost", PreTaxCost=100, Currency="USD",
                     ServiceName="Azure Databricks", correlation="matched"),
            envelope("azure_cost", "b", costBasis="AmortizedCost", PreTaxCost=90, Currency="USD",
                     ServiceName="Azure Databricks"),
            envelope("azure_cost", "c", costBasis="ActualCost", PreTaxCost=40, Currency="USD",
                     ServiceName="Virtual Machines", isServerless=True),
        ]
        for item in azure:
            item["correlation"] = {"status": "matched"}
        usage = [envelope(
            "databricks_usage", "u", sku_name="SERVERLESS_JOBS", usage_quantity=2,
            usage_start_time="2026-01-15T00:00:00Z",
        )]
        prices = [envelope(
            "list_price", "p", sku_name="SERVERLESS_JOBS", pricing={"default": 5},
            price_start_time="2026-01-01T00:00:00Z", price_end_time="2026-02-01T00:00:00Z",
        )]
        result = reconcile_costs(
            {"azure_cost": azure, "databricks_usage": usage, "list_price": prices},
            {"azure": {"reportingCostBasis": "ActualCost", "currency": "USD"}},
        )
        self.assertEqual(140, result["authoritativeTotals"]["ActualCost"])
        self.assertEqual(90, result["authoritativeTotals"]["AmortizedCost"])
        self.assertEqual(10, result["databricksListPriceEstimate"])
        self.assertEqual(0, result["databricksListPriceAddedToAzure"])
        self.assertEqual(40, result["duplicatePrevention"]["serverlessVmCostNotAdded"])
        self.assertEqual(100, result["collectedTotal"])

    def test_list_price_is_added_when_azure_has_only_classic_infrastructure(self):
        azure = envelope("azure_cost", "a", costBasis="ActualCost", PreTaxCost=25, ServiceName="Virtual Machines")
        azure["correlation"] = {"status": "matched"}
        result = reconcile_costs(
            {
                "azure_cost": [azure],
                "databricks_usage": [envelope(
                    "databricks_usage", "u", sku_name="JOBS", usage_quantity=2,
                    usage_start_time="2026-01-15T00:00:00Z",
                )],
                "list_price": [envelope("list_price", "p", sku_name="JOBS", price=4)],
            },
            {"azure": {}},
        )
        self.assertEqual(33, result["collectedTotal"])


class ModelConfidenceTests(unittest.TestCase):
    def test_confidence_levels_and_required_metric(self):
        self.assertEqual("high", confidence_from_metrics({"coverage": .9, "completeness": .9})["level"])
        self.assertEqual("medium", confidence_from_metrics({"coverage": .7, "completeness": .7})["level"])
        self.assertEqual("low", confidence_from_metrics({"coverage": .5, "completeness": .5})["level"])
        self.assertEqual(
            "insufficient",
            confidence_from_metrics({"coverage": 0, "completeness": 1}, ("coverage",))["level"],
        )


class ModelDetectorTests(unittest.TestCase):
    config = {"thresholds": {"materialMonthlyCost": 100, "interactiveAutoTerminationMinutes": 60}}

    def test_positive_boundary_negative_and_insufficient_cases(self):
        positive = {
            "compute": [envelope("compute", "c", cluster_source="UI", autotermination_minutes=61)],
            "azure_cost": [envelope("azure_cost", "x", PreTaxCost=100, tags={})],
            "job": [envelope("job", "j", settings={"existing_cluster_id": "c", "schedule": {"pause_status": "UNPAUSED"}})],
        }
        findings = run_detectors(positive, self.config)
        ids = {item["detectorId"] for item in findings if item["status"] == "candidate"}
        self.assertIn("OPT-INTERACTIVE-AUTOTERMINATION", ids)
        self.assertIn("MON-UNOWNED-COST", ids)
        self.assertIn("OPT-JOB-COMPUTE", ids)
        self.assertTrue(all(item["estimatedSavings"] is None for item in findings))

        boundary = {
            "compute": [envelope("compute", "c", cluster_source="UI", autotermination_minutes=60)],
            "azure_cost": [envelope("azure_cost", "x", PreTaxCost=99.99, tags={"Owner": "team"})],
            "job": [envelope("job", "j", settings={"new_cluster": {"num_workers": 1}})],
        }
        boundary_ids = {item["detectorId"] for item in run_detectors(boundary, self.config) if item["status"] == "candidate"}
        self.assertNotIn("OPT-INTERACTIVE-AUTOTERMINATION", boundary_ids)
        self.assertNotIn("MON-UNOWNED-COST", boundary_ids)
        self.assertNotIn("OPT-JOB-COMPUTE", boundary_ids)

        insufficient = run_detectors({}, self.config)
        self.assertTrue(insufficient)
        self.assertTrue(all(item["status"] == "insufficient_evidence" for item in insufficient))

    def test_attribution_resource_and_spend_coverage(self):
        data = {
            "azure_cost": [
                envelope("azure_cost", "a", PreTaxCost=80, tags={"Owner": "x"}),
                envelope("azure_cost", "b", PreTaxCost=20, tags={}),
            ]
        }
        result = attribution_coverage(data)
        self.assertEqual(50, result["resourceCoveragePercent"])
        self.assertEqual(80, result["spendCoveragePercent"])


class ModelPipelineTests(unittest.TestCase):
    def test_cli_writes_required_outputs_and_survives_bad_ndjson_row(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = root / "config.json"
            config.write_text(json.dumps({
                "customerId": "c", "assessmentId": "a",
                "azure": {"currency": "USD"}, "thresholds": {},
                "analysis": {"startUtc": "2026-01-01T00:00:00Z", "endUtc": "2026-02-01T00:00:00Z"},
            }), encoding="utf-8")
            run_root = root / "run"
            raw = run_root / "raw" / "azure"
            raw.mkdir(parents=True)
            (raw / "cost-management.ndjson").write_text(
                '{"costBasis":"ActualCost","PreTaxCost":12,"Currency":"USD"}\nbad\n',
                encoding="utf-8",
            )
            script = ASSESSMENT_ROOT / "pipeline" / "run_assessment.py"
            completed = subprocess.run(
                [sys.executable, str(script), "--config", str(config), "--run-root", str(run_root)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(0, completed.returncode, completed.stderr)
            required = [
                "cost-reconciliation.json", "telemetry-quality.json",
                "attribution-coverage.json", "optimization-candidates.json",
                "backlog-import.json", "benefits-baseline.json", "errors.json",
            ]
            self.assertTrue(all((run_root / name).exists() for name in required))
            self.assertEqual(1, len(json.loads((run_root / "errors.json").read_text())["errors"]))


if __name__ == "__main__":
    unittest.main()
