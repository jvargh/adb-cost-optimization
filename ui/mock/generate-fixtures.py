"""Generates the UI mock fixtures.

Usage:  python mock/generate-fixtures.py

Writes deterministic JSON into mock/fixtures/. The Phase 1 mock backend reads
these files; no Azure or Databricks call is ever made.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import scenario_enterprise  # noqa: E402
import scenario_variants  # noqa: E402
from estate import ESTATE, default_config  # noqa: E402
from run_timeline import build_timeline  # noqa: E402

FIXTURES = HERE / "fixtures"

SCENARIOS = {
    "contoso-partial": {
        "label": "Contoso — multi-subscription estate (partial)",
        "description": "Four workspaces across three subscriptions. Several collectors return partial or pending telemetry, which is the most common real-world outcome.",
        "builder": scenario_enterprise.enterprise,
    },
    "contoso-clean": {
        "label": "Contoso — single workspace (all sources passed)",
        "description": "A focused, healthy engagement where every collector succeeded and two findings already carry a recorded review decision.",
        "builder": scenario_variants.clean,
    },
    "fabrikam-failed": {
        "label": "Fabrikam — cost collection failed",
        "description": "The signed-in principal lacks Cost Management Reader, so no cost baseline exists. Demonstrates honest failure reporting instead of an empty dashboard.",
        "builder": scenario_variants.failed,
    },
}


def write_json(name: str, payload: object) -> Path:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    path = FIXTURES / name
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def main() -> int:
    written: list[Path] = []
    runs = []

    for scenario_id, meta in SCENARIOS.items():
        results = meta["builder"]()
        written.append(write_json(f"{scenario_id}.results.json", results))
        written.append(
            write_json(f"{scenario_id}.timeline.json", build_timeline(results))
        )

        manifest = results["manifest"]
        runs.append(
            {
                "runId": manifest["runId"],
                "customerId": manifest["customerId"],
                "status": manifest["status"],
                "startedAtUtc": manifest["startedAtUtc"],
                "completedAtUtc": manifest["completedAtUtc"],
                "analysisWindow": manifest["analysisWindow"],
                "authoritativeCost": results["reconciliation"]["authoritativeTotal"],
                "currency": results["reconciliation"]["currency"],
                "findingCount": results["candidates"]["candidateCount"]
                + results["candidates"]["insufficientEvidenceCount"],
                "subscriptionIds": manifest["scope"]["subscriptionIds"],
                "workspaceNames": [w["name"] for w in manifest["scope"]["workspaces"]],
                "scenarioId": scenario_id,
            }
        )

    written.append(write_json("estate.json", ESTATE))
    written.append(write_json("default-config.json", default_config()))
    written.append(
        write_json(
            "runs.json",
            sorted(runs, key=lambda r: r["startedAtUtc"], reverse=True),
        )
    )
    written.append(
        write_json(
            "scenarios.json",
            [
                {"id": sid, "label": meta["label"], "description": meta["description"]}
                for sid, meta in SCENARIOS.items()
            ],
        )
    )

    for path in written:
        print(f"wrote {path.relative_to(HERE.parent)} ({path.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
