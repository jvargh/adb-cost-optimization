"""Findings, roadmap, and evidence gaps for the enterprise scenario."""

from __future__ import annotations

from typing import Any

from estate import SUB_ANALYTICS, SUB_PLATFORM, SUB_SANDBOX
from fixtures_common import confidence, finding

NORMALIZED = "normalized"


def findings() -> list[dict[str, Any]]:
    return [
        finding(
            "OPT-INTERACTIVE-AUTOTERMINATION",
            "Interactive clusters run without auto-termination",
            "choose-optimal-resources",
            "candidate",
            "Three interactive (UI-created) clusters have auto-termination disabled or set beyond the configured threshold of 60 minutes. Observed uptime materially exceeds observed activity, which is consistent with idle billing.",
            "Confirm with each cluster owner whether an always-on interactive cluster is required. Where it is not, set auto-termination to the shortest interval that still meets the team's interactive workflow.",
            confidence("high", 0.9125, completeness=0.95, coverage=0.9, sourceAuthority=1.0, attributionQuality=0.8),
            [
                {"clusterId": "0912-081455-ad31kq7b", "clusterName": "shared-analytics-interactive", "autoterminationMinutes": 0, "observedUptimeHours": 671.4, "idlePercent": 46.2},
                {"clusterId": "0908-114203-9xkv22mp", "clusterName": "ds-exploration-shared", "autoterminationMinutes": 0, "observedUptimeHours": 604.9, "idlePercent": 71.8},
                {"clusterId": "0903-133012-7ck9wwq5", "clusterName": "legacy-etl-allpurpose", "autoterminationMinutes": 0, "observedUptimeHours": 719.9, "idlePercent": 88.3},
            ],
            [
                "Idle percent is derived from cluster event timelines, not from per-second utilization.",
                "A business requirement for always-on interactive compute would invalidate this candidate.",
            ],
            {"subscriptionId": None, "resourceGroup": None, "workspaceName": None, "workload": "interactive-compute"},
            [f"{NORMALIZED}/compute.ndjson", f"{NORMALIZED}/compute_event.ndjson", "optimization-candidates.json"],
        ),
        finding(
            "DYN-AUTOSCALING",
            "Fixed-size clusters carry variable workloads",
            "dynamically-allocate-resources",
            "candidate",
            "Two clusters are provisioned with identical minimum and maximum worker counts while their observed run durations vary by more than a factor of four, indicating the fixed size is not matched to demand.",
            "Validate the workload's concurrency profile, then evaluate autoscaling bounds against a representative run before changing any production job.",
            confidence("medium", 0.7583, completeness=0.75, coverage=0.7, sourceAuthority=0.9, sampleAdequacy=0.7),
            [
                {"clusterId": "0915-040118-lq04ttz1", "clusterName": "edw-nightly-load", "minWorkers": 4, "maxWorkers": 4, "p50DurationSeconds": 742, "p95DurationSeconds": 3184},
                {"clusterId": "0903-133012-7ck9wwq5", "clusterName": "legacy-etl-allpurpose", "minWorkers": 2, "maxWorkers": 2, "p50DurationSeconds": 311, "p95DurationSeconds": 1508},
            ],
            ["Duration variance may reflect upstream data volume rather than compute sizing."],
            {"subscriptionId": SUB_ANALYTICS, "resourceGroup": "rg-analytics-edw", "workspaceName": "dbw-analytics-edw", "workload": "edw-nightly-load"},
            [f"{NORMALIZED}/compute.ndjson", f"{NORMALIZED}/job_run.ndjson"],
        ),
        finding(
            "MON-UNOWNED-COST",
            "A material share of spend carries no approved ownership tag",
            "monitor-and-control-cost",
            "candidate",
            "Cost records representing 25.9 percent of in-scope spend cannot be attributed to an approved owner using the configured tag taxonomy. This exceeds the configured unattributed threshold of 5 percent.",
            "Run tag remediation with the resource owners named in the estate inventory, then re-run the assessment to confirm attribution coverage improves.",
            confidence("high", 0.925, completeness=1.0, coverage=0.95, sourceAuthority=1.0, attributionQuality=0.6),
            [
                {"unattributedSpend": 106883.24, "totalSpend": 412684.37, "unattributedPercent": 25.9, "currency": "USD"},
                {"resourceGroup": "mrg-datascience-sandbox", "unattributedSpend": 4539.53},
                {"resourceGroup": "rg-databricks-platform-nonprod", "unattributedSpend": 12793.22},
            ],
            ["Managed resource groups inherit tags from the parent workspace only when the workspace propagates them."],
            {"subscriptionId": None, "resourceGroup": None, "workspaceName": None, "workload": None},
            [f"{NORMALIZED}/azure_cost.ndjson", f"{NORMALIZED}/owner.ndjson", "attribution-coverage.json"],
        ),
        finding(
            "WRK-JOB-COMPUTE",
            "Scheduled jobs execute on all-purpose compute",
            "design-cost-effective-workloads",
            "candidate",
            "One scheduled job runs on an all-purpose cluster. All-purpose compute is billed at a higher DBU rate than jobs compute for the same workload shape.",
            "Confirm the job does not depend on a shared interactive session, then validate an equivalent run on jobs compute in a non-production workspace before changing the schedule.",
            confidence("high", 0.8917, completeness=0.9, coverage=0.85, sourceAuthority=1.0),
            [
                {"jobId": "447203998165520", "jobName": "legacy-etl-allpurpose", "clusterSource": "UI", "runCount": 186, "workspaceName": "dbw-platform-nonprod"},
            ],
            ["DBU rate differentials are list-price based and are not multiplied into a savings figure."],
            {"subscriptionId": SUB_PLATFORM, "resourceGroup": "rg-databricks-platform-nonprod", "workspaceName": "dbw-platform-nonprod", "workload": "legacy-etl-allpurpose"},
            [f"{NORMALIZED}/job.ndjson", f"{NORMALIZED}/compute.ndjson"],
        ),
        finding(
            "WRK-DRIVER-ON-SPOT",
            "Job cluster drivers are provisioned on spot instances",
            "design-cost-effective-workloads",
            "candidate",
            "Two job clusters place the driver node on spot capacity. Driver eviction terminates the entire run, so spot drivers trade a small unit-price reduction for a disproportionate reliability risk.",
            "Move the driver to on-demand capacity while leaving workers on spot, then confirm the job's failure rate over a full schedule cycle.",
            confidence("high", 0.9, completeness=0.95, coverage=0.9, sourceAuthority=1.0),
            [
                {"clusterId": "0917-020745-8bm3rrf2", "clusterName": "fraud-scoring-batch", "firstOnDemand": 0, "availability": "SPOT_WITH_FALLBACK_AZURE"},
                {"clusterId": "0924-051210-3wq7zzc0", "clusterName": "ml-training-gpu", "firstOnDemand": 0, "availability": "SPOT_WITH_FALLBACK_AZURE"},
            ],
            ["Observed eviction events are not available without cluster event retention across the full window."],
            {"subscriptionId": SUB_SANDBOX, "resourceGroup": "rg-datascience-sandbox", "workspaceName": "dbw-ds-sandbox", "workload": "ml-training-gpu"},
            [f"{NORMALIZED}/compute.ndjson", f"{NORMALIZED}/compute_event.ndjson"],
        ),
        finding(
            "MON-MISSING-BUDGET",
            "An active cost scope has no budget defined",
            "monitor-and-control-cost",
            "candidate",
            "The sandbox subscription carried in-scope spend during the analysis window but no Azure budget was returned for it.",
            "Validate budget coverage with the FinOps owner and create an accountable budget with an alert threshold where one is absent.",
            confidence("medium", 0.7667, completeness=0.7, coverage=0.7, sourceAuthority=0.9),
            [{"subscriptionId": SUB_SANDBOX, "costRecordCount": 214, "budgetCount": 0}],
            ["Budget inventory may be incomplete where the principal lacks Cost Management Reader on the scope."],
            {"subscriptionId": SUB_SANDBOX, "resourceGroup": None, "workspaceName": None, "workload": None},
            [f"{NORMALIZED}/budget.ndjson", f"{NORMALIZED}/azure_cost.ndjson"],
        ),
        finding(
            "OPT-JOB-COMPUTE",
            "SQL Warehouse right-sizing could not be evaluated",
            "choose-optimal-resources",
            "insufficient_evidence",
            "Query history for wh-edw-reporting was not collected because system table access was unavailable in this workspace. Warehouse sizing cannot be assessed from configuration alone.",
            "Grant SELECT on system.query.history for the assessment principal and re-run, or supply an approved query-history export.",
            confidence("low", 0.3667, completeness=0.2, coverage=0.25, sourceAuthority=0.9, sampleAdequacy=0.2),
            [{"warehouseId": "b1d4f9cc72ae5630", "warehouseName": "wh-edw-reporting", "queryRecordsCollected": 0}],
            [
                "No recommendation is produced. Missing evidence is reported as missing rather than inferred.",
            ],
            {"subscriptionId": SUB_ANALYTICS, "resourceGroup": "rg-analytics-edw", "workspaceName": "dbw-analytics-edw", "workload": "wh-edw-reporting"},
            [f"{NORMALIZED}/warehouse.ndjson", "telemetry-quality.json"],
        ),
    ]


def roadmap() -> list[dict[str, Any]]:
    return [
        {"horizon": "0-30", "title": "Confirm ownership for unattributed spend", "detail": "Work through the 25.9 percent of spend with no approved owner tag and assign an accountable owner per resource group.", "owner": "FinOps lead", "dependsOnFindingIds": ["MON-UNOWNED-COST"]},
        {"horizon": "0-30", "title": "Validate interactive cluster business need", "detail": "Interview the three interactive cluster owners and record whether always-on operation is a business requirement.", "owner": "Platform engineering", "dependsOnFindingIds": ["OPT-INTERACTIVE-AUTOTERMINATION"]},
        {"horizon": "0-30", "title": "Close the query-history evidence gap", "detail": "Grant system table read access so SQL Warehouse sizing can be assessed on the next run.", "owner": "Workspace admin", "dependsOnFindingIds": ["OPT-JOB-COMPUTE"]},
        {"horizon": "31-60", "title": "Pilot auto-termination in non-production", "detail": "Apply the agreed auto-termination interval in the non-production workspace and observe a full week of interactive usage.", "owner": "Platform engineering", "dependsOnFindingIds": ["OPT-INTERACTIVE-AUTOTERMINATION"]},
        {"horizon": "31-60", "title": "Validate jobs-compute migration", "detail": "Run legacy-etl-allpurpose on jobs compute in non-production and compare duration and failure rate against the current baseline.", "owner": "Data engineering", "dependsOnFindingIds": ["WRK-JOB-COMPUTE"]},
        {"horizon": "31-60", "title": "Move job drivers off spot capacity", "detail": "Set first_on_demand so the driver uses on-demand capacity and observe the failure rate across a full schedule cycle.", "owner": "Data engineering", "dependsOnFindingIds": ["WRK-DRIVER-ON-SPOT"]},
        {"horizon": "61-90", "title": "Scale accepted changes to production", "detail": "Promote only the changes that passed non-production validation, one workload at a time, with rollback criteria agreed in advance.", "owner": "Platform engineering", "dependsOnFindingIds": ["OPT-INTERACTIVE-AUTOTERMINATION", "WRK-JOB-COMPUTE"]},
        {"horizon": "61-90", "title": "Establish budgets and alerting", "detail": "Create budgets for every active cost scope and route alerts to the accountable owner recorded in day 0-30.", "owner": "FinOps lead", "dependsOnFindingIds": ["MON-MISSING-BUDGET", "MON-UNOWNED-COST"]},
        {"horizon": "61-90", "title": "Re-run the assessment and compare to baseline", "detail": "Re-run against the same window shape and compare against the recorded benefits baseline. Realized savings stay null until measured.", "owner": "FinOps lead", "dependsOnFindingIds": []},
    ]


def evidence_gaps() -> list[dict[str, Any]]:
    return [
        {"source": "Databricks billing [3390118246557742]", "status": "pending telemetry", "impact": "System billing tables returned no rows for the analysis window, so DBU consumption cannot be attributed per workload in dbw-analytics-edw.", "requiredToUnlock": ["SELECT on system.billing.usage", "SELECT on system.billing.list_prices"]},
        {"source": "Databricks SQL [3390118246557742]", "status": "partial", "impact": "Query history is unavailable, so SQL Warehouse sizing and queue pressure cannot be assessed.", "requiredToUnlock": ["SELECT on system.query.history"]},
        {"source": "Azure policy and diagnostics", "status": "partial", "impact": "Diagnostic settings could not be read for access connectors and user-assigned identities. These resource types do not support diagnostic settings, so the gap is expected and non-blocking.", "requiredToUnlock": []},
        {"source": "Azure inventory [rg-analytics-archive]", "status": "failed", "impact": "Reader is not assigned on rg-analytics-archive, so any Databricks-adjacent resources in that group are absent from the estate topology.", "requiredToUnlock": ["Reader on rg-analytics-archive"]},
        {"source": "Databricks Spark deep dive [all workspaces]", "status": "skipped", "impact": "No deep-dive job run IDs or table names were supplied, so stage-level Spark analysis was not attempted. This is an expected default, not a failure.", "requiredToUnlock": ["analysis.deepDiveJobRunIds", "analysis.deepDiveTableNames"]},
    ]
