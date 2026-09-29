"""Builds a replayable progress timeline for the Monitor view.

The real backend emits console output, not a structured progress stream. The
timeline below models what a Phase 2 progress adapter must produce by parsing
console output and polling `collection-status.json`, so the mock exercises the
same UI code path.
"""

from __future__ import annotations

from typing import Any

PHASES = [
    ("preflight", "Running the static read-only scanner over all assessment scripts"),
    ("collecting", "Collecting Azure and Databricks evidence"),
    ("normalizing", "Normalizing raw responses into the schema 1.0 model"),
    ("analyzing", "Correlating entities, reconciling cost, and scoring telemetry quality"),
    ("findings", "Evaluating detectors and building optimization candidates"),
    ("reporting", "Rendering the consolidated Markdown report and CSV exports"),
]


def build_timeline(results: dict[str, Any]) -> dict[str, Any]:
    """Interleave phase transitions, collector completions, and log lines."""
    events: list[dict[str, Any]] = []
    clock = 0.0

    def emit(event: dict[str, Any], advance: float) -> None:
        nonlocal clock
        events.append({**event, "offsetMs": int(clock * 1000)})
        clock += advance

    failed_run = results["manifest"]["status"] == "failed"

    emit({"type": "phase", "phase": "preflight", "message": PHASES[0][1]}, 0.6)
    emit(
        {
            "type": "log",
            "level": "info",
            "message": "AssessmentReadOnlySafety=PASS (34 PowerShell scripts parsed, 0 mutating calls found)",
        },
        0.5,
    )
    emit(
        {
            "type": "log",
            "level": "info",
            "message": "Read-only boundary confirmed: Azure GET plus approved Resource Graph and Cost Management POST only.",
        },
        0.4,
    )

    emit({"type": "phase", "phase": "collecting", "message": PHASES[1][1]}, 0.3)
    for entry in results["collection"]:
        emit(
            {
                "type": "log",
                "level": "info",
                "message": f"Starting {entry['name']}...",
            },
            0.35,
        )
        if entry["error"]:
            emit({"type": "log", "level": "error", "message": entry["error"]}, 0.2)
        for limitation in entry["limitations"]:
            emit({"type": "log", "level": "warn", "message": f"{entry['name']}: {limitation}"}, 0.15)
        emit({"type": "source", "source": entry}, 0.25)

    if failed_run:
        emit(
            {
                "type": "log",
                "level": "error",
                "message": "No cost baseline was collected. Cost-dependent analysis cannot run.",
            },
            0.4,
        )
        emit(
            {
                "type": "failed",
                "message": "Azure Cost Management failed with 403 Forbidden. Grant Cost Management Reader on the target subscription and re-run.",
            },
            0.0,
        )
        return {"runId": results["manifest"]["runId"], "events": events}

    for phase, message in PHASES[2:]:
        emit({"type": "phase", "phase": phase, "message": message}, 0.5)
        if phase == "analyzing":
            recon = results["reconciliation"]
            emit(
                {
                    "type": "log",
                    "level": "info",
                    "message": f"Cost reconciliation variance {recon['variancePercent']:.2f}% (within tolerance: {str(recon['withinTolerance']).lower()})",
                },
                0.4,
            )
            for limitation in recon["limitations"]:
                emit({"type": "log", "level": "warn", "message": limitation}, 0.3)
        if phase == "findings":
            candidates = results["candidates"]
            emit(
                {
                    "type": "log",
                    "level": "info",
                    "message": f"{candidates['candidateCount']} candidates and {candidates['insufficientEvidenceCount']} insufficient-evidence findings produced. No savings figure is inferred.",
                },
                0.4,
            )
        if phase == "reporting":
            emit(
                {
                    "type": "log",
                    "level": "info",
                    "message": "Wrote reports/assessment-report.md plus 3 CSV exports.",
                },
                0.3,
            )

    emit(
        {
            "type": "log",
            "level": "warn" if results["manifest"]["status"] == "partial" else "info",
            "message": (
                "Run completed with status partial: at least one source reported partial, failed, or pending telemetry."
                if results["manifest"]["status"] == "partial"
                else "Run completed with status passed: every source returned evidence."
            ),
        },
        0.3,
    )
    emit({"type": "completed", "runId": results["manifest"]["runId"]}, 0.0)
    return {"runId": results["manifest"]["runId"], "events": events}
