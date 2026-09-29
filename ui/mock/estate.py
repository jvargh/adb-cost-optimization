"""Discoverable estate used by the Configure pickers and the default config."""

from __future__ import annotations

from typing import Any

from fixtures_common import WINDOW_END, WINDOW_START

TENANT_ID = "5bb5fa45-2dcc-4310-bbc5-883021e9d84b"

SUB_PLATFORM = "463a82d4-1896-4332-aeeb-618ee5a5aa93"
SUB_ANALYTICS = "8c1f0d4a-91b7-4d2e-9a53-6f0b2c7e4411"
SUB_SANDBOX = "d27b5e93-7a10-4c68-b3f4-52e9c8a10d77"


def _warehouse(id_: str, name: str, size: str, state: str, serverless: bool) -> dict[str, Any]:
    return {
        "id": id_,
        "name": name,
        "size": size,
        "state": state,
        "serverless": serverless,
    }


def _workspace(
    name: str,
    workspace_id: str,
    rg: str,
    sub: str,
    managed_rg: str,
    sku: str,
    warehouses: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "name": name,
        "workspaceId": workspace_id,
        "workspaceUrl": f"adb-{workspace_id}.{workspace_id[-2:]}.azuredatabricks.net",
        "resourceGroup": rg,
        "subscriptionId": sub,
        "managedResourceGroup": managed_rg,
        "sku": sku,
        "location": "eastus",
        "sqlWarehouses": warehouses,
    }


WS_PLATFORM_PROD = _workspace(
    "dbw-platform-prod",
    "7405608792310779",
    "rg-databricks-platform-prod",
    SUB_PLATFORM,
    "mrg-databricks-platform-prod",
    "premium",
    [
        _warehouse("19dfff78c4e639c4", "wh-bi-serving", "Medium", "RUNNING", True),
        _warehouse("2a71c5be90ab3317", "wh-adhoc-analysts", "2X-Small", "STOPPED", True),
    ],
)

WS_PLATFORM_NONPROD = _workspace(
    "dbw-platform-nonprod",
    "5518204771003326",
    "rg-databricks-platform-nonprod",
    SUB_PLATFORM,
    "mrg-databricks-platform-nonprod",
    "premium",
    [_warehouse("77c0e41ab2d95f18", "wh-dev-sql", "X-Small", "STOPPED", True)],
)

WS_ANALYTICS_EDW = _workspace(
    "dbw-analytics-edw",
    "3390118246557742",
    "rg-analytics-edw",
    SUB_ANALYTICS,
    "mrg-analytics-edw",
    "premium",
    [_warehouse("b1d4f9cc72ae5630", "wh-edw-reporting", "Large", "RUNNING", False)],
)

WS_SANDBOX = _workspace(
    "dbw-ds-sandbox",
    "9021774365118820",
    "rg-datascience-sandbox",
    SUB_SANDBOX,
    "mrg-datascience-sandbox",
    "premium",
    [],
)

ALL_WORKSPACES = [WS_PLATFORM_PROD, WS_PLATFORM_NONPROD, WS_ANALYTICS_EDW, WS_SANDBOX]


def _rg(
    name: str, sub: str, workspaces: list[dict[str, Any]], managed: bool = False, issue: str | None = None
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "name": name,
        "resourceGroupId": f"/subscriptions/{sub}/resourcegroups/{name}",
        "location": "eastus",
        "subscriptionId": sub,
        "workspaces": workspaces,
        "isManagedResourceGroup": managed,
    }
    if issue:
        entry["permissionIssue"] = issue
    return entry


ESTATE: list[dict[str, Any]] = [
    {
        "subscriptionId": SUB_PLATFORM,
        "displayName": "Contoso Data Platform (Production)",
        "tenantId": TENANT_ID,
        "state": "Enabled",
        "resourceGroups": [
            _rg("rg-databricks-platform-prod", SUB_PLATFORM, [WS_PLATFORM_PROD]),
            _rg("mrg-databricks-platform-prod", SUB_PLATFORM, [], managed=True),
            _rg("rg-databricks-platform-nonprod", SUB_PLATFORM, [WS_PLATFORM_NONPROD]),
            _rg("mrg-databricks-platform-nonprod", SUB_PLATFORM, [], managed=True),
            _rg("rg-shared-networking", SUB_PLATFORM, []),
        ],
    },
    {
        "subscriptionId": SUB_ANALYTICS,
        "displayName": "Contoso Analytics",
        "tenantId": TENANT_ID,
        "state": "Enabled",
        "resourceGroups": [
            _rg("rg-analytics-edw", SUB_ANALYTICS, [WS_ANALYTICS_EDW]),
            _rg("mrg-analytics-edw", SUB_ANALYTICS, [], managed=True),
            _rg(
                "rg-analytics-archive",
                SUB_ANALYTICS,
                [],
                issue="Reader role is not assigned to the signed-in principal. Resources in this group cannot be collected.",
            ),
        ],
    },
    {
        "subscriptionId": SUB_SANDBOX,
        "displayName": "Contoso Data Science Sandbox",
        "tenantId": TENANT_ID,
        "state": "Enabled",
        "resourceGroups": [
            _rg("rg-datascience-sandbox", SUB_SANDBOX, [WS_SANDBOX]),
            _rg("mrg-datascience-sandbox", SUB_SANDBOX, [], managed=True),
        ],
    },
]


def default_config() -> dict[str, Any]:
    """Mirrors assessment/config/assessment-scope.example.json field for field."""
    return {
        "customerId": "contoso",
        "assessmentId": "adb-cost-assessment",
        "azure": {
            "tenantId": TENANT_ID,
            "subscriptions": [SUB_PLATFORM],
            "resourceGroups": ["rg-databricks-platform-prod"],
            "includeManagementGroups": False,
            "costScope": f"/subscriptions/{SUB_PLATFORM}",
            "costBasis": ["ActualCost", "AmortizedCost"],
            "currency": "USD",
        },
        "databricks": {
            "workspaces": [
                {
                    "name": WS_PLATFORM_PROD["name"],
                    "resourceGroup": WS_PLATFORM_PROD["resourceGroup"],
                    "workspaceUrl": WS_PLATFORM_PROD["workspaceUrl"],
                    "workspaceId": WS_PLATFORM_PROD["workspaceId"],
                    "include": True,
                }
            ],
            "includeQueryText": False,
            "includeNotebookPaths": False,
            "includeIdentities": False,
            "deepDiveJobRunIds": [],
            "deepDiveTableNames": [],
            "allowSqlWarehouseAutoStart": False,
        },
        "analysis": {
            "startUtc": WINDOW_START,
            "endUtc": WINDOW_END,
            "timeZone": "UTC",
            "maxPages": 100,
            "pageSize": 1000,
            "requestTimeoutSeconds": 120,
            "collectorTimeoutSeconds": 1800,
            "retryCount": 3,
            "retryBaseSeconds": 2,
        },
        "thresholds": {
            "materialMonthlyCost": 100.0,
            "unattributedCostPercent": 5.0,
            "idleComputePercent": 20.0,
            "interactiveAutoTerminationMinutes": 60,
            "legacyRuntimeMajorVersionsBehind": 2,
            "smallFileBytes": 33554432,
            "smallFilePercent": 30.0,
            "sqlQueueP95Seconds": 30.0,
            "jobFailureRatePercent": 5.0,
            "continuousStreamingIdlePercent": 50.0,
            "poolIdleHours": 24.0,
        },
        "redaction": {
            "hashIdentities": True,
            "hashTableNames": False,
            "hashNotebookPaths": True,
            "omitQueryText": True,
            "saltEnvironmentVariable": "ADB_ASSESSMENT_HASH_SALT",
        },
        "outputs": {
            "root": "./assessment/output",
            "retainRaw": True,
            "writeCsv": True,
            "writeJson": True,
            "writeMarkdown": True,
        },
    }
