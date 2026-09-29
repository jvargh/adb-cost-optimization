"""Success and failure scenario variants, derived from the enterprise baseline.

Deriving keeps the fixtures consistent: reviewers compare the same screens
across a healthy run, a degraded run, and a failed run.
"""

from __future__ import annotations

import copy
from typing import Any

import scenario_enterprise as base
from estate import SUB_PLATFORM, WS_PLATFORM_PROD
from fixtures_common import confidence, iso, review_entry
from report_builder import build_report


def _single_workspace(results: dict[str, Any]) -> None:
    """Narrow the scope to one workspace so the run reads as a focused engagement."""
    key = WS_PLATFORM_PROD["workspaceId"]
    results["manifest"]["scope"]["subscriptionIds"] = [SUB_PLATFORM]
    results["manifest"]["scope"]["resourceGroups"] = ["rg-databricks-platform-prod"]
    results["manifest"]["scope"]["resourceGroupIds"] = [
        f"/subscriptions/{SUB_PLATFORM}/resourcegroups/rg-databricks-platform-prod",
        f"/subscriptions/{SUB_PLATFORM}/resourcegroups/mrg-databricks-platform-prod",
    ]
    results["manifest"]["scope"]["workspaces"] = [
        {
            "name": WS_PLATFORM_PROD["name"],
            "workspaceId": key,
            "workspaceUrl": WS_PLATFORM_PROD["workspaceUrl"],
            "resourceGroup": WS_PLATFORM_PROD["resourceGroup"],
            "subscriptionId": SUB_PLATFORM,
        }
    ]
    results["collection"] = [
        s for s in results["collection"] if s["domain"] == "azure" or s.get("workspaceKey") == key
    ]
    for dataset in ("compute", "warehouses", "workloads"):
        results[dataset] = [
            r for r in results[dataset] if r["workspaceName"] == WS_PLATFORM_PROD["name"]
        ]
    results["costDrivers"] = [
        d for d in results["costDrivers"] if d["workspaceName"] == WS_PLATFORM_PROD["name"]
    ]
    for rank, driver in enumerate(results["costDrivers"], start=1):
        driver["rank"] = rank


def clean() -> dict[str, Any]:
    """A healthy run: every source passed, telemetry quality is high."""
    results = copy.deepcopy(base.enterprise())
    run_id = "adb-cost-assessment-20260919T101204517Z-7ac22b91"
    results["manifest"]["runId"] = run_id
    results["manifest"]["customerId"] = "contoso"
    results["manifest"]["status"] = "passed"
    results["benefits"]["baselineId"] = f"{run_id}:v1"

    _single_workspace(results)

    for s in results["collection"]:
        if s["status"] != "skipped":
            s["status"] = "passed"
            s["limitations"] = []
            s["error"] = ""

    results["telemetry"] = base._telemetry(
        results["collection"],
        confidence("high", 0.9438, completeness=0.95, coverage=0.94, collectionSuccess=1.0, attributionQuality=0.96),
    )
    results["attribution"].update(
        {
            "resourceCount": 41,
            "attributedResourceCount": 40,
            "resourceCoveragePercent": 97.6,
            "attributedSpend": round(results["attribution"]["totalSpend"] * 0.982, 2),
            "spendCoveragePercent": 98.2,
        }
    )
    results["reconciliation"]["limitations"] = []
    results["reconciliation"]["variancePercent"] = 0.4
    results["reconciliation"]["withinTolerance"] = True

    kept = [
        f
        for f in results["candidates"]["findings"]
        if f["status"] == "candidate"
        and f["detectorId"] in {"OPT-INTERACTIVE-AUTOTERMINATION", "WRK-DRIVER-ON-SPOT", "MON-UNOWNED-COST"}
    ]
    results["candidates"]["findings"] = kept
    results["candidates"]["candidateCount"] = len(kept)
    results["candidates"]["insufficientEvidenceCount"] = 0
    results["review"] = [review_entry(f) for f in kept]
    results["roadmap"] = [
        item
        for item in results["roadmap"]
        if not item["dependsOnFindingIds"]
        or any(fid in {f["detectorId"] for f in kept} for fid in item["dependsOnFindingIds"])
    ]
    results["evidenceGaps"] = [
        g for g in results["evidenceGaps"] if g["status"] == "skipped"
    ]

    # Two review decisions are already recorded so the Review screen shows a
    # partially completed sign-off register rather than an empty one.
    if results["review"]:
        results["review"][0].update(
            {
                "reviewer": "J. Okafor",
                "role": "Platform engineering lead",
                "reviewedAtUtc": iso(90000),
                "decision": "accepted",
                "businessSlaContext": "Interactive analytics has no overnight SLA.",
                "performanceReliabilityRisk": "Low. Analysts restart clusters on demand.",
                "securityGovernanceImpact": "None.",
                "validationExperiment": "Apply a 45-minute auto-termination in non-production for one week.",
                "ownerApprover": "D. Marchetti",
                "rationale": "Owner confirmed always-on operation is not a business requirement.",
            }
        )
    if len(results["review"]) > 1:
        results["review"][1].update(
            {
                "reviewer": "A. Lindqvist",
                "role": "Data engineering lead",
                "reviewedAtUtc": iso(91800),
                "decision": "deferred",
                "businessSlaContext": "Fraud scoring must complete before the 06:00 batch window.",
                "performanceReliabilityRisk": "Driver eviction would miss the batch window.",
                "securityGovernanceImpact": "None.",
                "validationExperiment": "Observe one full schedule cycle after moving the driver to on-demand.",
                "ownerApprover": "D. Marchetti",
                "rationale": "Agreed in principle but deferred until after the quarter-end freeze.",
            }
        )

    results["reportMarkdown"] = build_report(results)
    return results


def failed() -> dict[str, Any]:
    """A failed run: the principal lacks Cost Management Reader, so no cost
    baseline can be established. The UI must show this honestly rather than
    rendering an empty dashboard that looks like zero spend."""
    results = copy.deepcopy(base.enterprise())
    run_id = "adb-cost-assessment-20260926T031755204Z-4f80c113"
    results["manifest"]["runId"] = run_id
    results["manifest"]["customerId"] = "fabrikam"
    results["manifest"]["status"] = "failed"
    results["manifest"]["completedAtUtc"] = iso(46)
    results["benefits"]["baselineId"] = f"{run_id}:v1"

    _single_workspace(results)

    failures = {
        "Azure Cost Management": "403 Forbidden: the signed-in principal does not have Cost Management Reader on /subscriptions/463a82d4-1896-4332-aeeb-618ee5a5aa93.",
        "Azure budgets and commitments": "403 Forbidden: budget enumeration requires Cost Management Reader.",
    }
    for s in results["collection"]:
        if s["name"] in failures:
            s["status"] = "failed"
            s["error"] = failures[s["name"]]
            s["itemCount"] = 0
            s["limitations"] = ["No cost evidence was collected. Cost-dependent analysis was not attempted."]
        elif s["domain"] == "databricks" and s["status"] != "skipped":
            s["status"] = "pending telemetry"
            s["itemCount"] = 0
            s["limitations"] = ["Collection stopped after the cost baseline failed."]

    zeroed = {
        "authoritativeTotal": 0.0,
        "collectedTotal": 0.0,
        "matchedCost": 0.0,
        "unmatchedCost": 0.0,
        "excludedCost": 0.0,
        "varianceAmount": 0.0,
        "variancePercent": 0.0,
        "withinTolerance": False,
        "authoritativeTotals": {},
        "limitations": [
            "No cost baseline could be established. Every cost figure in this run is absent, not zero.",
        ],
    }
    results["reconciliation"].update(zeroed)
    results["attribution"].update(
        {
            "resourceCount": 41,
            "attributedResourceCount": 0,
            "resourceCoveragePercent": 0.0,
            "totalSpend": 0.0,
            "attributedSpend": 0.0,
            "spendCoveragePercent": 0.0,
        }
    )
    results["benefits"]["authoritativeCost"] = 0.0
    results["costDrivers"] = []
    results["costTrend"] = []
    results["costBreakdown"] = []
    results["workloads"] = []
    results["warehouses"] = []
    results["candidates"] = {
        "schemaVersion": results["candidates"]["schemaVersion"],
        "analysisWindow": results["candidates"]["analysisWindow"],
        "candidateCount": 0,
        "insufficientEvidenceCount": 0,
        "findings": [],
    }
    results["review"] = []
    results["roadmap"] = []
    results["telemetry"] = base._telemetry(
        results["collection"],
        confidence("low", 0.2188, completeness=0.1, coverage=0.1, collectionSuccess=0.1176, attributionQuality=0.0),
    )
    results["evidenceGaps"] = [
        {
            "source": "Azure Cost Management",
            "status": "failed",
            "impact": "No cost baseline exists for this run. No cost figure, driver ranking, or optimization candidate can be produced.",
            "requiredToUnlock": ["Cost Management Reader on the target subscription"],
        },
        {
            "source": "Azure budgets and commitments",
            "status": "failed",
            "impact": "Budget coverage cannot be evaluated.",
            "requiredToUnlock": ["Cost Management Reader on the target subscription"],
        },
        {
            "source": "Databricks collectors",
            "status": "pending telemetry",
            "impact": "Workspace collection did not run because the cost baseline failed first.",
            "requiredToUnlock": ["A successful Azure Cost Management collection"],
        },
    ]
    results["exports"] = [
        e for e in results["exports"] if e["relativePath"].endswith((".json",))
    ]
    results["reportMarkdown"] = build_report(results)
    return results
