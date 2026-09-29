"""Conservative initial detector catalog aligned to the four cost principles."""

from __future__ import annotations

from typing import Any

from assessment.model.core import MODEL_VERSION, confidence_from_metrics


def _record(item: dict[str, Any]) -> dict[str, Any]:
    return item.get("normalized", item)


def _finding(
    detector: str,
    category: str,
    status: str,
    title: str,
    evidence: list[dict[str, Any]],
    limitations: list[str],
    action: str,
    metrics: dict[str, float],
) -> dict[str, Any]:
    confidence = confidence_from_metrics(metrics, ("coverage", "completeness"))
    if status == "insufficient_evidence":
        confidence["level"] = "insufficient"
    return {
        "schemaVersion": MODEL_VERSION,
        "detectorId": detector,
        "category": category,
        "status": status,
        "title": title,
        "explanation": action if status == "candidate" else f"Evidence required before recommendation: {action}",
        "recommendedAction": action,
        "evidence": evidence,
        "confidence": confidence,
        "limitations": limitations,
        "estimatedSavings": None,
        "savingsCurrency": None,
        "humanValidationRequired": True,
    }


def _insufficient(detector: str, category: str, title: str, required: str) -> dict[str, Any]:
    return _finding(
        detector, category, "insufficient_evidence", title, [],
        [f"Missing minimum evidence: {required}."],
        f"Collect and validate {required}.",
        {"coverage": 0.0, "completeness": 0.0, "sourceAuthority": 0.0},
    )


def run_detectors(
    datasets: dict[str, list[dict[str, Any]]], config: dict[str, Any]
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    thresholds = config.get("thresholds", {})
    material = float(thresholds.get("materialMonthlyCost", 100.0))
    termination_limit = int(thresholds.get("interactiveAutoTerminationMinutes", 60))

    computes = datasets.get("compute", [])
    if not computes:
        findings.append(_insufficient(
            "OPT-INTERACTIVE-AUTOTERMINATION", "choose-optimal-resources",
            "Interactive compute configuration unavailable", "cluster inventory",
        ))
        findings.append(_insufficient(
            "DYN-AUTOSCALING", "dynamically-allocate-resources",
            "Dynamic allocation cannot be assessed", "cluster inventory and node timeline",
        ))
    else:
        candidates = []
        for item in computes:
            row = _record(item)
            source = str(row.get("cluster_source", row.get("clusterSource", ""))).upper()
            minutes = row.get("autotermination_minutes", row.get("autoterminationMinutes"))
            if source in ("UI", "API") and (minutes is None or float(minutes) > termination_limit):
                candidates.append({
                    "sourceIdentifier": item.get("sourceIdentifier"),
                    "autoterminationMinutes": minutes,
                    "thresholdMinutes": termination_limit,
                })
        if candidates:
            findings.append(_finding(
                "OPT-INTERACTIVE-AUTOTERMINATION", "choose-optimal-resources", "candidate",
                "Interactive compute exceeds the auto-termination standard", candidates, [],
                "Set an approved auto-termination policy after validating user SLA.",
                {"coverage": 1.0, "completeness": 1.0, "sourceAuthority": 0.9},
            ))

        timeline = datasets.get("node_timeline", [])
        fixed = [
            item for item in computes
            if not isinstance(_record(item).get("autoscale"), dict)
            and _record(item).get("num_workers", _record(item).get("numWorkers")) is not None
        ]
        if fixed and not timeline:
            findings.append(_insufficient(
                "DYN-AUTOSCALING", "dynamically-allocate-resources",
                "Fixed-size compute needs demand evidence", "node timeline or stage demand",
            ))
        elif fixed and timeline:
            findings.append(_finding(
                "DYN-AUTOSCALING", "dynamically-allocate-resources", "candidate",
                "Fixed-size compute has variable node occupancy", [
                    {"fixedComputeCount": len(fixed), "timelineRecordCount": len(timeline)}
                ], ["Validate workload SLA and autoscaling eligibility."],
                "Benchmark bounded autoscaling against the current fixed-size baseline.",
                {"coverage": 1.0, "completeness": 0.8, "sourceAuthority": 0.9},
            ))

    costs = datasets.get("azure_cost", [])
    if not costs:
        findings.append(_insufficient(
            "MON-UNOWNED-COST", "monitor-and-control-cost",
            "Ownership coverage cannot be assessed", "cost and ownership/tag evidence",
        ))
    else:
        unowned = []
        for item in costs:
            row = _record(item)
            amount = float(row.get("PreTaxCost", row.get("cost", 0)) or 0)
            tags = row.get("tags", row.get("Tags", {}))
            tags = tags if isinstance(tags, dict) else {}
            has_owner = any(tags.get(key) for key in ("Owner", "owner", "Team", "team"))
            if amount >= material and not has_owner:
                unowned.append({"sourceIdentifier": item.get("sourceIdentifier"), "cost": amount, "threshold": material})
        if unowned:
            findings.append(_finding(
                "MON-UNOWNED-COST", "monitor-and-control-cost", "candidate",
                "Material cost lacks accountable ownership", unowned, [],
                "Assign an accountable owner and required allocation tags prospectively.",
                {"coverage": 1.0, "completeness": 0.9, "attributionQuality": 0.4, "sourceAuthority": 1.0},
            ))

    jobs = datasets.get("job", [])
    if not jobs:
        findings.append(_insufficient(
            "WRK-JOB-COMPUTE", "design-cost-effective-workloads",
            "Scheduled workload compute cannot be assessed", "job and cluster-source evidence",
        ))
    else:
        all_purpose = []
        for item in jobs:
            row = _record(item)
            settings = row.get("settings", {}) if isinstance(row.get("settings"), dict) else row
            cluster_id = settings.get("existing_cluster_id", settings.get("existingClusterId"))
            schedule = settings.get("schedule") or row.get("schedule")
            if cluster_id and schedule:
                all_purpose.append({"sourceIdentifier": item.get("sourceIdentifier"), "existingClusterId": cluster_id})
        if all_purpose:
            findings.append(_finding(
                "OPT-JOB-COMPUTE", "choose-optimal-resources", "candidate",
                "Scheduled workload uses existing all-purpose compute", all_purpose,
                ["Confirm library, concurrency, and startup constraints."],
                "Benchmark job compute or serverless jobs for the scheduled workload.",
                {"coverage": 1.0, "completeness": 0.9, "sourceAuthority": 0.9},
            ))

    budgets = datasets.get("budget", [])
    if costs and not budgets:
        findings.append(_finding(
            "MON-MISSING-BUDGET", "monitor-and-control-cost", "candidate",
            "No budget evidence was collected for an active cost scope",
            [{"costRecordCount": len(costs)}], ["Budget inventory may be unavailable due to permissions."],
            "Validate budget coverage and create an accountable budget where absent.",
            {"coverage": 0.7, "completeness": 0.7, "sourceAuthority": 0.9},
        ))

    driver_on_spot = []
    for item in computes:
        row = _record(item)
        availability = str(row.get("driver_availability", row.get("driverAvailability", ""))).lower()
        driver_spot = row.get("driver_is_spot", row.get("driverIsSpot"))
        if driver_spot is True or availability in ("spot", "spot_with_fallback"):
            driver_on_spot.append({
                "sourceIdentifier": item.get("sourceIdentifier"),
                "availability": availability or "spot",
            })
    if driver_on_spot:
        findings.append(_finding(
            "WRK-DRIVER-ON-SPOT", "design-cost-effective-workloads", "candidate",
            "Workload driver is configured on spot capacity", driver_on_spot,
            ["Worker spot eligibility is separate and is not flagged by this detector."],
            "Move the driver to on-demand capacity while independently evaluating spot workers.",
            {"coverage": 1.0, "completeness": 0.9, "sourceAuthority": 0.9},
        ))
    return findings
