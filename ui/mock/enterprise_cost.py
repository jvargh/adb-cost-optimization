"""Cost, compute, warehouse, and workload datasets for the enterprise scenario."""

from __future__ import annotations

from typing import Any

from estate import SUB_ANALYTICS, SUB_PLATFORM, SUB_SANDBOX
from fixtures_common import stable_float, stable_int, window_days

CURRENCY = "USD"

# (display name, type, subscription, resource group, workspace, share of spend)
DRIVER_SHAPE: list[tuple[str, str, str, str, str | None, float]] = [
    ("dbw-platform-prod", "microsoft.databricks/workspaces", SUB_PLATFORM, "rg-databricks-platform-prod", "dbw-platform-prod", 0.317),
    ("dbw-analytics-edw", "microsoft.databricks/workspaces", SUB_ANALYTICS, "rg-analytics-edw", "dbw-analytics-edw", 0.211),
    ("vmss-worker-prod", "microsoft.compute/virtualmachinescalesets", SUB_PLATFORM, "mrg-databricks-platform-prod", "dbw-platform-prod", 0.148),
    ("dbstorageprodeastus01", "microsoft.storage/storageaccounts", SUB_PLATFORM, "mrg-databricks-platform-prod", "dbw-platform-prod", 0.071),
    ("vmss-worker-edw", "microsoft.compute/virtualmachinescalesets", SUB_ANALYTICS, "mrg-analytics-edw", "dbw-analytics-edw", 0.063),
    ("dbw-ds-sandbox", "microsoft.databricks/workspaces", SUB_SANDBOX, "rg-datascience-sandbox", "dbw-ds-sandbox", 0.052),
    ("nat-gateway-prod", "microsoft.network/natgateways", SUB_PLATFORM, "mrg-databricks-platform-prod", "dbw-platform-prod", 0.038),
    ("dbw-platform-nonprod", "microsoft.databricks/workspaces", SUB_PLATFORM, "rg-databricks-platform-nonprod", "dbw-platform-nonprod", 0.031),
    ("adlsanalyticsedw", "microsoft.storage/storageaccounts", SUB_ANALYTICS, "mrg-analytics-edw", "dbw-analytics-edw", 0.026),
    ("nat-gateway-edw", "microsoft.network/natgateways", SUB_ANALYTICS, "mrg-analytics-edw", "dbw-analytics-edw", 0.017),
    ("dbstoragesandbox02", "microsoft.storage/storageaccounts", SUB_SANDBOX, "mrg-datascience-sandbox", "dbw-ds-sandbox", 0.011),
    ("log-platform-prod", "microsoft.operationalinsights/workspaces", SUB_PLATFORM, "rg-databricks-platform-prod", None, 0.009),
    ("pip-nat-prod", "microsoft.network/publicipaddresses", SUB_PLATFORM, "mrg-databricks-platform-prod", "dbw-platform-prod", 0.004),
    ("kv-platform-prod", "microsoft.keyvault/vaults", SUB_PLATFORM, "rg-databricks-platform-prod", None, 0.002),
]

AUTHORITATIVE_TOTAL = 412_684.37


def cost_drivers() -> list[dict[str, Any]]:
    drivers: list[dict[str, Any]] = []
    for rank, (name, rtype, sub, rg, ws, share) in enumerate(DRIVER_SHAPE, start=1):
        drivers.append(
            {
                "rank": rank,
                "driver": f"/subscriptions/{sub}/resourcegroups/{rg}/providers/{rtype}/{name}",
                "displayName": name,
                "resourceType": rtype,
                "subscriptionId": sub,
                "resourceGroup": rg,
                "workspaceName": ws,
                "observedCost": round(AUTHORITATIVE_TOTAL * share, 2),
                "currency": CURRENCY,
            }
        )
    return drivers


def cost_trend() -> list[dict[str, Any]]:
    """Daily cost with a visible weekday/weekend rhythm and a late-window ramp."""
    days = window_days()
    points: list[dict[str, Any]] = []
    daily_mean = AUTHORITATIVE_TOTAL / len(days)
    for index, day in enumerate(days):
        weekday = index % 7
        seasonal = 0.62 if weekday in (5, 6) else 1.12
        ramp = 1.0 + (index / len(days)) * 0.28
        jitter = stable_float(f"trend:{day}", 0.92, 1.08, 4)
        actual = round(daily_mean * seasonal * ramp * jitter, 2)
        dbu_share = stable_float(f"dbu:{day}", 0.55, 0.64, 4)
        points.append(
            {
                "date": day,
                "actualCost": actual,
                "amortizedCost": round(actual * stable_float(f"amort:{day}", 0.96, 1.02, 4), 2),
                "dbuCost": round(actual * dbu_share, 2),
                "infrastructureCost": round(actual * (1 - dbu_share), 2),
            }
        )
    return points


_SERVICE_MIX = [
    ("Azure Databricks", 0.611),
    ("Virtual Machines", 0.211),
    ("Storage", 0.108),
    ("Virtual Network", 0.055),
    ("Log Analytics", 0.009),
    ("Key Vault", 0.006),
]

_SKU_MIX = [
    ("All-Purpose Compute (Premium)", 0.242),
    ("Jobs Compute (Premium)", 0.198),
    ("SQL Serverless", 0.141),
    ("Standard_D8ds_v5", 0.117),
    ("Jobs Compute Photon", 0.094),
    ("Standard_E16ds_v5", 0.081),
    ("Delta Live Tables Advanced", 0.058),
    ("Standard_L8s_v3 (spot)", 0.039),
    ("Hot LRS", 0.030),
]

_OWNER_MIX = [
    ("Platform-Team", 0.298),
    ("EDW-Reporting", 0.204),
    ("Fraud-Analytics", 0.151),
    ("Marketing-Insights", 0.088),
    ("Unattributed (no approved tag)", 0.259),
]


def cost_breakdown() -> list[dict[str, Any]]:
    slices: list[dict[str, Any]] = []

    def add(dimension: str, mix: list[tuple[str, float]]) -> None:
        for label, share in mix:
            slices.append(
                {
                    "key": f"{dimension}:{label}",
                    "label": label,
                    "cost": round(AUTHORITATIVE_TOTAL * share, 2),
                    "currency": CURRENCY,
                    "dimension": dimension,
                }
            )

    add("service", _SERVICE_MIX)
    add("sku", _SKU_MIX)
    add("tagOwner", _OWNER_MIX)

    rg_totals: dict[str, float] = {}
    ws_totals: dict[str, float] = {}
    for _, _, _, rg, ws, share in DRIVER_SHAPE:
        rg_totals[rg] = rg_totals.get(rg, 0.0) + share
        key = ws or "No workspace attribution"
        ws_totals[key] = ws_totals.get(key, 0.0) + share
    add("resourceGroup", sorted(rg_totals.items(), key=lambda kv: -kv[1]))
    add("workspace", sorted(ws_totals.items(), key=lambda kv: -kv[1]))
    return slices


_CLUSTER_SHAPE = [
    ("0912-081455-ad31kq7b", "shared-analytics-interactive", "dbw-platform-prod", "UI", "RUNNING", "Standard_D8ds_v5", "14.3.x-photon-scala2.12", True, 0, 2, 12, False, 671.4, 46.2, "Platform-Team", "prod-interactive-policy"),
    ("0908-114203-9xkv22mp", "ds-exploration-shared", "dbw-ds-sandbox", "UI", "RUNNING", "Standard_E16ds_v5", "12.2.x-scala2.12", False, 0, 1, 8, False, 604.9, 71.8, None, None),
    ("0915-040118-lq04ttz1", "edw-nightly-load", "dbw-analytics-edw", "JOB", "TERMINATED", "Standard_D8ds_v5", "15.4.x-photon-scala2.12", True, 10, 4, 4, False, 188.2, 6.1, "EDW-Reporting", "job-standard-policy"),
    ("0917-020745-8bm3rrf2", "fraud-scoring-batch", "dbw-platform-prod", "JOB", "TERMINATED", "Standard_L8s_v3", "15.4.x-photon-scala2.12", True, 15, 2, 16, True, 142.7, 11.4, "Fraud-Analytics", "job-standard-policy"),
    ("0903-133012-7ck9wwq5", "legacy-etl-allpurpose", "dbw-platform-nonprod", "UI", "RUNNING", "Standard_D4ds_v5", "11.3.x-scala2.12", False, 0, 2, 2, False, 719.9, 88.3, None, None),
    ("0920-061530-2pn5xxa8", "marketing-dlt-pipeline", "dbw-analytics-edw", "PIPELINE", "TERMINATED", "Standard_D4ds_v5", "15.4.x-photon-scala2.12", True, 5, 1, 6, False, 96.3, 14.7, "Marketing-Insights", "dlt-policy"),
    ("0922-093344-5td1yyb9", "adhoc-notebook-dev", "dbw-platform-nonprod", "UI", "TERMINATED", "Standard_D4ds_v5", "14.3.x-scala2.12", False, 120, 1, 4, False, 58.1, 62.5, "Platform-Team", None),
    ("0924-051210-3wq7zzc0", "ml-training-gpu", "dbw-ds-sandbox", "JOB", "TERMINATED", "Standard_NC6s_v3", "15.4.x-gpu-ml-scala2.12", False, 30, 1, 3, True, 41.6, 4.2, None, None),
]


def compute_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for (
        cluster_id, name, ws, src, state, node, runtime, photon,
        autoterm, min_w, max_w, spot, uptime, idle, owner, policy,
    ) in _CLUSTER_SHAPE:
        records.append(
            {
                "clusterId": cluster_id,
                "clusterName": name,
                "workspaceName": ws,
                "source": src,
                "state": state,
                "nodeTypeId": node,
                "driverNodeTypeId": node,
                "runtime": runtime,
                "photon": photon,
                "autoterminationMinutes": autoterm,
                "minWorkers": min_w,
                "maxWorkers": max_w,
                "spotDriver": spot,
                "observedUptimeHours": uptime,
                "idlePercent": idle,
                "owner": owner,
                "policyName": policy,
            }
        )
    return records


_WAREHOUSE_SHAPE = [
    ("19dfff78c4e639c4", "wh-bi-serving", "dbw-platform-prod", "Medium", "RUNNING", True, True, 10, 1, 4, 18422, 41.3, 7.8, 12.4),
    ("2a71c5be90ab3317", "wh-adhoc-analysts", "dbw-platform-prod", "2X-Small", "STOPPED", True, True, 5, 1, 1, 1904, 3.1, 4.2, 0.0),
    ("b1d4f9cc72ae5630", "wh-edw-reporting", "dbw-analytics-edw", "Large", "RUNNING", False, True, 60, 2, 6, 9633, 28.7, 19.6, 47.1),
    ("77c0e41ab2d95f18", "wh-dev-sql", "dbw-platform-nonprod", "X-Small", "STOPPED", True, False, 10, 1, 1, None, None, None, None),
]


def warehouse_records() -> list[dict[str, Any]]:
    return [
        {
            "id": wid,
            "name": name,
            "workspaceName": ws,
            "size": size,
            "state": state,
            "serverless": serverless,
            "photon": photon,
            "autoStopMinutes": auto_stop,
            "minClusters": min_c,
            "maxClusters": max_c,
            "queryCount": qc,
            "p95QueueSeconds": queue,
            "p95DurationSeconds": dur,
            "spillGb": spill,
        }
        for (wid, name, ws, size, state, serverless, photon, auto_stop, min_c, max_c, qc, queue, dur, spill) in _WAREHOUSE_SHAPE
    ]


_JOB_SHAPE = [
    ("814772031558411", "edw-nightly-load", "dbw-analytics-edw", "job-cluster", "EDW-Reporting", 0.121),
    ("614161130219943", "fraud-scoring-batch", "dbw-platform-prod", "job-cluster", "Fraud-Analytics", 0.096),
    ("330915522017634", "customer-360-serverless", "dbw-platform-prod", "serverless", "Platform-Team", 0.084),
    ("902118844103275", "marketing-dlt-pipeline", "dbw-analytics-edw", "pipeline", "Marketing-Insights", 0.052),
    ("447203998165520", "legacy-etl-allpurpose", "dbw-platform-nonprod", "all-purpose", None, 0.041),
    ("558330117294863", "ml-feature-refresh", "dbw-ds-sandbox", "job-cluster", None, 0.029),
    ("771449226381957", "cdc-ingest-streaming", "dbw-platform-prod", "job-cluster", "Platform-Team", 0.024),
    ("209556334470182", "daily-quality-checks", "dbw-platform-prod", "serverless", "Platform-Team", 0.011),
]


def workload_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for job_id, name, ws, compute_type, owner, share in _JOB_SHAPE:
        records.append(
            {
                "jobId": job_id,
                "jobName": name,
                "workspaceName": ws,
                "computeType": compute_type,
                "runCount": stable_int(f"runs:{job_id}", 18, 640),
                "failureRatePercent": stable_float(f"fail:{job_id}", 0.0, 14.0, 1),
                "p50DurationSeconds": stable_float(f"p50:{job_id}", 120, 1800, 0),
                "p95DurationSeconds": stable_float(f"p95:{job_id}", 600, 5400, 0),
                "owner": owner,
                "observedCost": round(AUTHORITATIVE_TOTAL * share, 2),
                "currency": CURRENCY,
            }
        )
    return records
