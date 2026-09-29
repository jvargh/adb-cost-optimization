"""Assembles complete AssessmentResults fixtures for each demo scenario."""

from __future__ import annotations

from typing import Any

import enterprise_cost as ec
import enterprise_findings as ef
from estate import (
    SUB_ANALYTICS,
    SUB_PLATFORM,
    SUB_SANDBOX,
    TENANT_ID,
    WS_ANALYTICS_EDW,
    WS_PLATFORM_NONPROD,
    WS_PLATFORM_PROD,
    WS_SANDBOX,
)
from fixtures_common import (
    SCHEMA,
    STANDARD_EXPORTS,
    TOOLKIT_VERSION,
    analysis_window,
    confidence,
    iso,
    review_entry,
    source,
)
from report_builder import build_report

RAW_AZ = "raw/azure"


def _manifest(run_id: str, status: str, customer: str, workspaces: list[dict[str, Any]], subs: list[str], rgs: list[str]) -> dict[str, Any]:
    return {
        "schemaVersion": SCHEMA,
        "toolkitVersion": TOOLKIT_VERSION,
        "runId": run_id,
        "customerId": customer,
        "assessmentId": "adb-cost-assessment",
        "startedAtUtc": iso(0),
        "completedAtUtc": iso(184),
        "status": status,
        "analysisWindow": analysis_window(),
        "outputRoot": f"./assessment/output/{run_id}",
        "scope": {
            "tenantId": TENANT_ID,
            "subscriptionIds": subs,
            "resourceGroups": rgs,
            "resourceGroupIds": [f"/subscriptions/{s}/resourcegroups/{g}" for s in subs for g in rgs],
            "workspaces": [
                {
                    "name": w["name"],
                    "workspaceId": w["workspaceId"],
                    "workspaceUrl": w["workspaceUrl"],
                    "resourceGroup": w["resourceGroup"],
                    "subscriptionId": w["subscriptionId"],
                }
                for w in workspaces
            ],
        },
    }


def _enterprise_collection() -> list[dict[str, Any]]:
    entries = [
        source("Azure inventory", "partial", "azure", 148, [f"{RAW_AZ}/resource-inventory.ndjson", f"{RAW_AZ}/databricks-workspaces.json"], limitations=["Reader is not assigned on rg-analytics-archive; that group was skipped."], started=1, duration=11),
        source("Azure policy and diagnostics", "partial", "azure", 1042, [f"{RAW_AZ}/policy-inventory.ndjson", f"{RAW_AZ}/diagnostic-settings.ndjson"], limitations=["Access connectors and user-assigned identities do not support diagnostic settings."], started=12, duration=22),
        source("Azure Cost Management", "passed", "azure", 8914, [f"{RAW_AZ}/cost-management.ndjson"], started=34, duration=29),
        source("Azure budgets and commitments", "passed", "azure", 7, [f"{RAW_AZ}/budgets-commitments.json"], started=63, duration=4),
        source("Azure compute quotas", "passed", "azure", 486, [f"{RAW_AZ}/compute-quotas.ndjson"], started=67, duration=8),
    ]
    workspace_plan = [
        (WS_PLATFORM_PROD, {"workspace": ("passed", 3), "billing": ("passed", 5411), "compute": ("passed", 96), "workloads": ("passed", 412), "SQL": ("passed", 18422), "Unity Catalog": ("partial", 1204), "governance": ("passed", 31), "Spark deep dive": ("skipped", 0)}),
        (WS_ANALYTICS_EDW, {"workspace": ("passed", 2), "billing": ("pending telemetry", 0), "compute": ("passed", 58), "workloads": ("partial", 233), "SQL": ("partial", 3), "Unity Catalog": ("passed", 806), "governance": ("partial", 12), "Spark deep dive": ("skipped", 0)}),
        (WS_PLATFORM_NONPROD, {"workspace": ("passed", 2), "billing": ("passed", 1877), "compute": ("passed", 41), "workloads": ("passed", 186), "SQL": ("passed", 1904), "Unity Catalog": ("passed", 318), "governance": ("passed", 9), "Spark deep dive": ("skipped", 0)}),
        (WS_SANDBOX, {"workspace": ("passed", 1), "billing": ("passed", 902), "compute": ("partial", 27), "workloads": ("passed", 64), "SQL": ("skipped", 0), "Unity Catalog": ("passed", 141), "governance": ("failed", 0), "Spark deep dive": ("skipped", 0)}),
    ]
    offset = 76
    for ws, plan in workspace_plan:
        key = ws["workspaceId"]
        for label, (status, count) in plan.items():
            error = ""
            limitations: list[str] = []
            if status == "failed":
                error = "403 Forbidden: the assessment principal is not a workspace admin, so governance settings could not be read."
            if status == "pending telemetry":
                limitations = ["system.billing.usage returned no rows for the analysis window."]
            if status == "skipped":
                limitations = ["No deep-dive targets were supplied." if label == "Spark deep dive" else "No SQL Warehouse is present in this workspace."]
            entries.append(
                source(
                    f"Databricks {label} [{key}]",
                    status,
                    "databricks",
                    count,
                    [f"raw/databricks/{key}/{label.lower().replace(' ', '-')}.ndjson"],
                    limitations=limitations,
                    error=error,
                    workspace_key=key,
                    started=offset,
                    duration=6,
                )
            )
            offset += 4
    return entries


def _telemetry(sources: list[dict[str, Any]], overall: dict[str, Any]) -> dict[str, Any]:
    levels = {"passed": ("high", 0.95), "partial": ("medium", 0.68), "pending telemetry": ("low", 0.32), "failed": ("low", 0.18), "skipped": ("low", 0.25)}
    entries = []
    for s in sources:
        level, score = levels[s["status"]]
        entries.append({**confidence(level, score, completeness=score, coverage=score), "source": s["outputs"][0] if s["outputs"] else s["name"]})
    return {"schemaVersion": SCHEMA, "generatedAtUtc": iso(184), "overall": overall, "sources": entries}


def enterprise() -> dict[str, Any]:
    run_id = "adb-cost-assessment-20260926T214949861Z-1e4e3e10"
    workspaces = [WS_PLATFORM_PROD, WS_ANALYTICS_EDW, WS_PLATFORM_NONPROD, WS_SANDBOX]
    subs = [SUB_PLATFORM, SUB_ANALYTICS, SUB_SANDBOX]
    rgs = ["rg-databricks-platform-prod", "rg-databricks-platform-nonprod", "rg-analytics-edw", "rg-datascience-sandbox"]
    collection = _enterprise_collection()
    all_findings = ef.findings()
    total = ec.AUTHORITATIVE_TOTAL

    results: dict[str, Any] = {
        "manifest": _manifest(run_id, "partial", "contoso", workspaces, subs, rgs),
        "scopeFilter": {
            "schemaVersion": SCHEMA,
            "allowedResourceGroups": rgs + ["mrg-databricks-platform-prod", "mrg-databricks-platform-nonprod", "mrg-analytics-edw", "mrg-datascience-sandbox"],
            "allowedResourceGroupIds": [f"/subscriptions/{SUB_PLATFORM}/resourcegroups/rg-databricks-platform-prod"],
            "entities": {
                "azure_cost": {"inputRecords": 8914, "includedRecords": 8914, "excludedRecords": 0},
                "azure_resource": {"inputRecords": 148, "includedRecords": 97, "excludedRecords": 51},
                "owner": {"inputRecords": 64, "includedRecords": 52, "excludedRecords": 12},
                "workspace": {"inputRecords": 4, "includedRecords": 4, "excludedRecords": 0},
            },
            "limitations": ["rg-analytics-archive was excluded because Reader is not assigned."],
        },
        "collection": collection,
        "reconciliation": {
            "schemaVersion": SCHEMA,
            "reportingBasis": "ActualCost",
            "currency": ec.CURRENCY,
            "authoritativeTotal": total,
            "authoritativeTotals": {"ActualCost": total, "AmortizedCost": round(total * 0.987, 2)},
            "collectedTotal": round(total * 0.964, 2),
            "matchedCost": round(total * 0.951, 2),
            "unmatchedCost": round(total * 0.013, 2),
            "excludedCost": round(total * 0.036, 2),
            "allocatedSharedCost": 0.0,
            "varianceAmount": round(total * 0.036, 2),
            "variancePercent": 3.6,
            "withinTolerance": True,
            "currencyAggregationAllowed": True,
            "databricksListPriceEstimate": 0.0,
            "databricksListPriceAddedToAzure": 0.0,
            "unmatchedDatabricksUsageRecords": 118,
            "taxIncluded": None,
            "duplicatePrevention": {
                "rule": "Serverless DBU includes infrastructure; explicit serverless VM estimates are never additive.",
                "azureContainsDatabricksServiceCost": True,
                "serverlessDbuCost": round(total * 0.141, 2),
                "serverlessVmCostNotAdded": round(total * 0.036, 2),
            },
            "limitations": ["Billing telemetry is missing for dbw-analytics-edw, so its DBU split is inferred from Azure meters only."],
        },
        "attribution": {
            "schemaVersion": SCHEMA,
            "resourceCount": 97,
            "attributedResourceCount": 68,
            "resourceCoveragePercent": 70.1,
            "totalSpend": total,
            "attributedSpend": round(total * 0.741, 2),
            "spendCoveragePercent": 74.1,
        },
        "telemetry": _telemetry(collection, confidence("medium", 0.7412, completeness=0.72, coverage=0.7, collectionSuccess=0.7838, attributionQuality=0.741)),
        "benefits": {
            "schemaVersion": SCHEMA,
            "baselineId": f"{run_id}:v1",
            "createdAtUtc": iso(184),
            "analysisWindow": analysis_window(),
            "reportingBasis": "ActualCost",
            "currency": ec.CURRENCY,
            "authoritativeCost": total,
            "realizedSavings": None,
            "workloadNormalization": {"method": "none", "reason": "No approved workload normalization factor was supplied."},
        },
        "candidates": {
            "schemaVersion": SCHEMA,
            "analysisWindow": analysis_window(),
            "candidateCount": sum(1 for f in all_findings if f["status"] == "candidate"),
            "insufficientEvidenceCount": sum(1 for f in all_findings if f["status"] == "insufficient_evidence"),
            "findings": all_findings,
        },
        "costDrivers": ec.cost_drivers(),
        "costTrend": ec.cost_trend(),
        "costBreakdown": ec.cost_breakdown(),
        "compute": ec.compute_records(),
        "warehouses": ec.warehouse_records(),
        "workloads": ec.workload_records(),
        "roadmap": ef.roadmap(),
        "evidenceGaps": ef.evidence_gaps(),
        "review": [review_entry(f) for f in all_findings],
        "exports": STANDARD_EXPORTS,
    }
    results["reportMarkdown"] = build_report(results)
    return results
