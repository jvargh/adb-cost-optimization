#!/usr/bin/env python3
"""Normalize and assess Azure Databricks collector output using Python 3 only."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ASSESSMENT_ROOT = Path(__file__).resolve().parents[1]
if str(ASSESSMENT_ROOT.parent) not in sys.path:
    sys.path.insert(0, str(ASSESSMENT_ROOT.parent))

from assessment.detectors import run_detectors
from assessment.model.core import (
    MODEL_VERSION,
    attribution_coverage,
    build_normalized_model,
    correlate_model,
    filter_databricks_scope,
    reconcile_costs,
    telemetry_quality,
)
from assessment.reports import render_reports


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def _write_ndjson(path: Path, values: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for value in values:
            handle.write(json.dumps(value, sort_keys=True, default=str) + "\n")


def run(config_path: Path, run_root: Path) -> int:
    config = json.loads(config_path.read_text(encoding="utf-8-sig"))
    manifest_path = run_root / "assessment-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig")) if manifest_path.exists() else {
        "runId": config.get("assessmentId"),
        "analysisWindow": config.get("analysis", {}),
    }
    datasets, errors, inventory = build_normalized_model(run_root, config, manifest)
    scope_filter = filter_databricks_scope(datasets, config)
    collection_status_path = run_root / "collection-status.json"
    if collection_status_path.exists():
        collection_status = json.loads(collection_status_path.read_text(encoding="utf-8-sig"))
        for result in collection_status if isinstance(collection_status, list) else []:
            status = str(result.get("status", "")).lower()
            if status in ("partial", "failed", "pending telemetry"):
                limitations = result.get("limitations") or []
                errors.append({
                    "source": result.get("name"),
                    "kind": "collector_status",
                    "status": status,
                    "message": result.get("error") or "; ".join(str(value) for value in limitations)
                    or f"Collector reported {status}.",
                })
    correlation = correlate_model(datasets)
    normalized_root = run_root / "normalized"
    for entity, records in sorted(datasets.items()):
        _write_ndjson(normalized_root / f"{entity}.ndjson", records)
    _write_json(normalized_root / "correlation.json", correlation)
    _write_json(run_root / "scope-filter.json", scope_filter)

    reconciliation = reconcile_costs(datasets, config)
    quality = telemetry_quality(inventory, datasets)
    reporting_basis = reconciliation.get("reportingBasis", "ActualCost")
    reporting_datasets = dict(datasets)
    reporting_datasets["azure_cost"] = [
        item for item in datasets.get("azure_cost", [])
        if str(item.get("normalized", {}).get("costBasis", "ActualCost")) == reporting_basis
    ]
    attribution = attribution_coverage(reporting_datasets)
    findings = run_detectors(reporting_datasets, config)
    candidates = {
        "schemaVersion": MODEL_VERSION,
        "analysisWindow": manifest.get("analysisWindow", config.get("analysis")),
        "findings": findings,
        "candidateCount": sum(item["status"] == "candidate" for item in findings),
        "insufficientEvidenceCount": sum(item["status"] == "insufficient_evidence" for item in findings),
    }
    backlog = {
        "schemaVersion": MODEL_VERSION,
        "items": [{
            "externalId": item["detectorId"],
            "title": item["title"],
            "type": "optimization" if item["status"] == "candidate" else "evidence-gap",
            "status": "proposed",
            "confidence": item["confidence"]["level"],
            "estimatedSavings": item["estimatedSavings"],
            "recommendedAction": item["recommendedAction"],
            "evidence": item["evidence"],
        } for item in findings],
    }
    baseline = {
        "schemaVersion": MODEL_VERSION,
        "baselineId": f"{manifest.get('runId', config.get('assessmentId'))}:v1",
        "createdAtUtc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "analysisWindow": manifest.get("analysisWindow", config.get("analysis")),
        "reportingBasis": reconciliation["reportingBasis"],
        "authoritativeCost": reconciliation["authoritativeTotal"],
        "currency": reconciliation["currency"],
        "workloadNormalization": {
            "method": "none",
            "reason": "No approved workload normalization factor was supplied.",
        },
        "realizedSavings": None,
    }
    _write_json(run_root / "source-inventory.json", {"schemaVersion": MODEL_VERSION, "sources": inventory})
    _write_json(run_root / "cost-reconciliation.json", reconciliation)
    _write_json(run_root / "telemetry-quality.json", quality)
    _write_json(run_root / "attribution-coverage.json", attribution)
    _write_json(run_root / "optimization-candidates.json", candidates)
    _write_json(run_root / "backlog-import.json", backlog)
    _write_json(run_root / "benefits-baseline.json", baseline)
    _write_json(run_root / "errors.json", {"schemaVersion": MODEL_VERSION, "errors": errors})
    render_reports(run_root)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--run-root", required=True, type=Path)
    args = parser.parse_args()
    try:
        return run(args.config.resolve(), args.run_root.resolve())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"assessment pipeline failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
