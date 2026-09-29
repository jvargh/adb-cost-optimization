"""Shared helpers for building deterministic UI mock fixtures.

These fixtures are representative data for human review of the UI. They are NOT
assessment output and must never be presented as customer evidence.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any

SCHEMA = "1.0"
TOOLKIT_VERSION = "0.1.0"

WINDOW_START = "2026-08-26T00:00:00Z"
WINDOW_END = "2026-09-26T00:00:00Z"


def stable_float(seed: str, low: float, high: float, places: int = 2) -> float:
    """Deterministic pseudo-random float derived from a seed string."""
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    fraction = int(digest[:12], 16) / float(0xFFFFFFFFFFFF)
    return round(low + fraction * (high - low), places)


def stable_int(seed: str, low: int, high: int) -> int:
    digest = hashlib.sha256(("i:" + seed).encode("utf-8")).hexdigest()
    span = max(1, high - low + 1)
    return low + (int(digest[:12], 16) % span)


def window_days(start_utc: str = WINDOW_START, end_utc: str = WINDOW_END) -> list[str]:
    start = datetime.fromisoformat(start_utc.replace("Z", "+00:00"))
    end = datetime.fromisoformat(end_utc.replace("Z", "+00:00"))
    days: list[str] = []
    cursor = start
    while cursor < end:
        days.append(cursor.strftime("%Y-%m-%d"))
        cursor += timedelta(days=1)
    return days


def iso(offset_seconds: int, base: str = "2026-09-26T21:49:49.874Z") -> str:
    moment = datetime.fromisoformat(base.replace("Z", "+00:00")) + timedelta(
        seconds=offset_seconds
    )
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def analysis_window() -> dict[str, str]:
    return {"startUtc": WINDOW_START, "endUtc": WINDOW_END, "timeZone": "UTC"}


def confidence(level: str, score: float, **metrics: float) -> dict[str, Any]:
    base = {
        "completeness": 0.8,
        "coverage": 0.8,
        "sourceAuthority": 0.9,
        "freshness": 1.0,
        "consistency": 1.0,
        "sampleAdequacy": 1.0,
        "attributionQuality": 0.8,
        "collectionSuccess": 0.9,
    }
    base.update(metrics)
    return {
        "level": level,
        "score": round(score, 4),
        "metrics": {k: round(v, 4) for k, v in base.items()},
        "missingRequiredMetrics": [],
    }


def source(
    name: str,
    status: str,
    domain: str,
    item_count: int,
    outputs: list[str],
    *,
    limitations: list[str] | None = None,
    error: str = "",
    workspace_key: str | None = None,
    started: int = 0,
    duration: int = 5,
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "name": name,
        "status": status,
        "startedAtUtc": iso(started),
        "completedAtUtc": iso(started + duration),
        "itemCount": item_count,
        "outputs": outputs,
        "limitations": limitations or [],
        "error": error,
        "domain": domain,
    }
    if workspace_key:
        entry["workspaceKey"] = workspace_key
    return entry


def finding(
    detector_id: str,
    title: str,
    category: str,
    status: str,
    explanation: str,
    action: str,
    conf: dict[str, Any],
    evidence: list[dict[str, Any]],
    limitations: list[str],
    scope: dict[str, Any],
    evidence_files: list[str],
) -> dict[str, Any]:
    """Build a finding. `estimatedSavings` is deliberately always null: the
    backend does not infer savings and the UI must not invent them."""
    return {
        "schemaVersion": SCHEMA,
        "detectorId": detector_id,
        "title": title,
        "category": category,
        "status": status,
        "explanation": explanation,
        "recommendedAction": action,
        "confidence": conf,
        "evidence": evidence,
        "limitations": limitations,
        "humanValidationRequired": True,
        "estimatedSavings": None,
        "savingsCurrency": None,
        "scope": scope,
        "evidenceFiles": evidence_files,
    }


def review_entry(f: dict[str, Any]) -> dict[str, Any]:
    return {
        "findingId": f["detectorId"],
        "finding": f["title"],
        "evidenceLinks": f["evidenceFiles"],
        "reviewer": "",
        "role": "",
        "reviewedAtUtc": None,
        "decision": "pending",
        "businessSlaContext": "",
        "performanceReliabilityRisk": "",
        "securityGovernanceImpact": "",
        "validationExperiment": "",
        "ownerApprover": "",
        "rationale": "",
    }


def export_artifact(
    name: str, path: str, kind: str, description: str, size: int, sensitivity: str
) -> dict[str, Any]:
    return {
        "name": name,
        "relativePath": path,
        "kind": kind,
        "description": description,
        "sizeBytes": size,
        "sensitivity": sensitivity,
    }


STANDARD_EXPORTS = [
    export_artifact(
        "Consolidated assessment report",
        "reports/assessment-report.md",
        "markdown",
        "Single consolidated Markdown report with all 17 ordered sections.",
        34838,
        "sensitive",
    ),
    export_artifact(
        "Top cost drivers",
        "reports/top-cost-drivers.csv",
        "csv",
        "Ranked observed cost drivers within the approved scope.",
        1277,
        "sensitive",
    ),
    export_artifact(
        "Prioritized backlog",
        "reports/prioritized-backlog.csv",
        "csv",
        "Provisional review order for candidate findings.",
        216,
        "sensitive",
    ),
    export_artifact(
        "Human validation sign-off",
        "reports/human-validation-sign-off.csv",
        "csv",
        "Sign-off register that must be completed before any change is made.",
        426,
        "sensitive",
    ),
    export_artifact(
        "Optimization candidates",
        "optimization-candidates.json",
        "json",
        "Machine-readable findings with confidence and evidence.",
        1232,
        "sensitive",
    ),
    export_artifact(
        "Cost reconciliation",
        "cost-reconciliation.json",
        "json",
        "Authoritative vs collected cost with duplicate-prevention rules.",
        929,
        "sensitive",
    ),
    export_artifact(
        "Telemetry quality",
        "telemetry-quality.json",
        "json",
        "Per-source and overall evidence quality scoring.",
        18287,
        "sensitive",
    ),
    export_artifact(
        "Collection status",
        "collection-status.json",
        "json",
        "Per-collector status, item counts, limitations, and errors.",
        16755,
        "sensitive",
    ),
    export_artifact(
        "Scope filter proof",
        "scope-filter.json",
        "json",
        "Included and excluded record counts proving scope isolation.",
        867,
        "sensitive",
    ),
    export_artifact(
        "Benefits baseline",
        "benefits-baseline.json",
        "json",
        "Baseline for later benefits realization. Realized savings is null.",
        537,
        "sensitive",
    ),
]
