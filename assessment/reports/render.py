"""Render deterministic human-readable reports from assessment machine outputs."""

from __future__ import annotations

import csv
import io
import json
import math
from pathlib import Path
from typing import Any, Iterable

REPORT_FILES = (
    ("01-executive-summary.md", "Executive summary"),
    ("02-estate-topology-and-scope.md", "Estate topology and scope"),
    ("03-current-cost-baseline.md", "Current cost baseline and reconciliation"),
    ("04-top-cost-drivers.md", "Top cost drivers"),
    ("05-unattributed-cost.md", "Unattributed cost"),
    ("06-compute-right-sizing.md", "Compute and right-sizing"),
    ("07-sql-warehouse-query.md", "SQL Warehouse and query"),
    ("08-jobs-pipelines.md", "Jobs and pipelines"),
    ("09-spark-deep-dive-index.md", "Spark deep-dive index"),
    ("10-delta-data-layout.md", "Delta and data layout"),
    ("11-governance-finops.md", "Governance, policies, budgets, and FinOps"),
    ("12-commitment-readiness.md", "Commitment readiness"),
    ("13-telemetry-quality-limitations.md", "Telemetry quality and limitations"),
    ("14-prioritized-backlog.md", "Prioritized backlog"),
    ("15-30-60-90-roadmap.md", "30/60/90 roadmap"),
    ("16-benefits-realization.md", "Benefits realization"),
    ("17-human-validation-sign-off.md", "Human validation and sign-off"),
)

ENTITY_EVIDENCE = {
    "azure_cost": "../normalized/azure_cost.ndjson",
    "azure_resource": "../normalized/azure_resource.ndjson",
    "budget": "../normalized/budget.ndjson",
    "compute": "../normalized/compute.ndjson",
    "job": "../normalized/job.ndjson",
    "job_run": "../normalized/job_run.ndjson",
    "node_timeline": "../normalized/node_timeline.ndjson",
    "pipeline": "../normalized/pipeline.ndjson",
    "policy": "../normalized/policy.ndjson",
    "query": "../normalized/query.ndjson",
    "table": "../normalized/table.ndjson",
    "table_file_summary": "../normalized/table_file_summary.ndjson",
    "table_operation": "../normalized/table_operation.ndjson",
    "warehouse": "../normalized/warehouse.ndjson",
    "workspace": "../normalized/workspace.ndjson",
}


def _load_json(run_root: Path, name: str, default: Any) -> Any:
    path = run_root / name
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _load_ndjson(run_root: Path, entity: str) -> list[dict[str, Any]]:
    path = run_root / "normalized" / f"{entity}.ndjson"
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if line.strip():
            value = json.loads(line)
            if isinstance(value, dict):
                records.append(value)
    return records


def _normalized(item: dict[str, Any]) -> dict[str, Any]:
    value = item.get("normalized", item)
    return value if isinstance(value, dict) else {}


def _value(item: dict[str, Any], *names: str, default: Any = None) -> Any:
    lowered = {str(key).lower(): value for key, value in item.items()}
    for name in names:
        value = lowered.get(name.lower())
        if value is not None:
            return value
    return default


def _number(value: Any) -> float | None:
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def _text(value: Any) -> str:
    if value in (None, ""):
        return "Not available"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def _money(value: Any, currency: Any) -> str:
    number = _number(value)
    if number is None:
        return "Insufficient evidence"
    suffix = f" {_text(currency)}" if currency else " (currency unavailable)"
    return f"{number:,.2f}{suffix}"


def _percent(value: Any) -> str:
    number = _number(value)
    return "Insufficient evidence" if number is None else f"{number:,.2f}%"


def _link(label: str, target: str) -> str:
    return f"[{label}]({target.replace(' ', '%20')})"


def _table(headers: Iterable[str], rows: Iterable[Iterable[Any]]) -> str:
    header_values = list(headers)
    lines = [
        "| " + " | ".join(header_values) + " |",
        "| " + " | ".join("---" for _ in header_values) + " |",
    ]
    materialized = [list(row) for row in rows]
    if not materialized:
        materialized = [["Insufficient evidence"] + ["-" for _ in header_values[1:]]]
    lines.extend("| " + " | ".join(_text(value) for value in row) + " |" for row in materialized)
    return "\n".join(lines)


def _report(title: str, purpose: str, body: str, evidence: Iterable[tuple[str, str]]) -> str:
    links = sorted(set(evidence), key=lambda item: (item[0].lower(), item[1]))
    evidence_lines = "\n".join(f"- {_link(label, path)}" for label, path in links)
    if not evidence_lines:
        evidence_lines = "- Insufficient evidence: no machine-readable evidence file was available."
    return (
        f"# {title}\n\n"
        f"{purpose}\n\n"
        "> Automated output is advisory and requires human validation. "
        "No finding or savings estimate should be treated as approved until sign-off is recorded.\n\n"
        f"{body.rstrip()}\n\n"
        "## Evidence files\n\n"
        f"{evidence_lines}\n"
    )


def _finding_evidence_entities(finding_id: str) -> tuple[str, ...]:
    mapping = {
        "OPT-INTERACTIVE-AUTOTERMINATION": ("compute",),
        "DYN-AUTOSCALING": ("compute", "node_timeline"),
        "MON-UNOWNED-COST": ("azure_cost",),
        "OPT-JOB-COMPUTE": ("job", "compute"),
        "MON-MISSING-BUDGET": ("azure_cost", "budget"),
        "WRK-DRIVER-ON-SPOT": ("compute",),
    }
    return mapping.get(finding_id, ())


def _finding_evidence_links(finding_id: str) -> str:
    links = [_link("finding record", "../optimization-candidates.json")]
    links.extend(
        _link(f"{entity} evidence", ENTITY_EVIDENCE[entity])
        for entity in _finding_evidence_entities(finding_id)
    )
    return "; ".join(links)


def _findings_section(findings: list[dict[str, Any]], ids: set[str] | None = None) -> str:
    selected = [
        item for item in findings
        if ids is None or str(item.get("detectorId")) in ids
    ]
    selected.sort(key=lambda item: str(item.get("detectorId", "")))
    if not selected:
        return (
            "## Findings\n\n"
            "**Insufficient evidence:** no applicable automated finding was produced. "
            "This is not evidence that the estate is optimized.\n"
        )
    rows = []
    details = []
    for item in selected:
        finding_id = str(item.get("findingId") or item.get("detectorId", "unknown"))
        confidence = item.get("confidence", {})
        savings = item.get("estimatedSavings")
        savings_text = (
            _money(savings, item.get("savingsCurrency"))
            if savings is not None else "Not estimated"
        )
        rows.append((
            finding_id,
            item.get("status"),
            confidence.get("level"),
            savings_text,
            item.get("title"),
        ))
        evidence = item.get("evidence") or []
        evidence_text = (
            "; ".join(json.dumps(value, sort_keys=True, separators=(",", ":")) for value in evidence)
            if evidence else "No finding-level evidence was collected."
        )
        limitations = item.get("limitations") or ["None recorded."]
        details.append(
            f"### {finding_id}: {_text(item.get('title'))}\n\n"
            f"- **Status:** {_text(item.get('status'))}\n"
            f"- **Recommended action:** {_text(item.get('recommendedAction'))}\n"
            f"- **Evidence:** {_text(evidence_text)}\n"
            f"- **Evidence files:** {_finding_evidence_links(finding_id)}\n"
            f"- **Limitations:** {_text('; '.join(str(value) for value in limitations))}\n"
        )
    return (
        "## Findings\n\n"
        + _table(("Finding ID", "Status", "Confidence", "Estimated savings", "Finding"), rows)
        + "\n\n"
        + "\n".join(details)
    )


def _dataset_summary(datasets: dict[str, list[dict[str, Any]]], entities: Iterable[str]) -> str:
    return _table(
        ("Dataset", "Records", "Evidence"),
        (
            (entity, len(datasets.get(entity, [])), _link(f"{entity}.ndjson", ENTITY_EVIDENCE[entity]))
            for entity in entities
        ),
    )


def _cost_driver_rows(costs: list[dict[str, Any]], aggregate_allowed: bool) -> list[dict[str, Any]]:
    if not aggregate_allowed:
        return []
    grouped: dict[tuple[str, str], float] = {}
    for item in costs:
        row = _normalized(item)
        amount = _number(_value(row, "PreTaxCost", "Cost", "cost")) or 0.0
        currency = str(_value(row, "Currency", "currency", default=""))
        label = str(_value(
            row, "ResourceName", "resourceName", "ResourceId", "resourceId",
            "ServiceName", "serviceName", default=item.get("sourceIdentifier", "Unknown"),
        ))
        grouped[(currency, label)] = grouped.get((currency, label), 0.0) + amount
    rows = [
        {"rank": 0, "driver": label, "cost": round(cost, 6), "currency": currency}
        for (currency, label), cost in grouped.items()
    ]
    rows.sort(key=lambda item: (-item["cost"], item["currency"], item["driver"].lower()))
    for rank, row in enumerate(rows, 1):
        row["rank"] = rank
    return rows


def _csv_text(headers: list[str], rows: Iterable[Iterable[Any]]) -> str:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(headers)
    writer.writerows(rows)
    return output.getvalue()


def _raw_evidence_links(source_inventory: dict[str, Any], token: str) -> list[tuple[str, str]]:
    sources = source_inventory.get("sources", source_inventory)
    return [
        (path, f"../{path.replace(chr(92), '/')}")
        for path in sorted(sources)
        if token.lower() in path.lower()
    ]


def render_reports(run_root: Path) -> list[Path]:
    """Render all reports from persisted machine-readable outputs."""
    run_root = Path(run_root)
    reports_root = run_root / "reports"
    reports_root.mkdir(parents=True, exist_ok=True)

    manifest = _load_json(run_root, "assessment-manifest.json", {})
    source_inventory = _load_json(run_root, "source-inventory.json", {"sources": {}})
    reconciliation = _load_json(run_root, "cost-reconciliation.json", {})
    quality = _load_json(run_root, "telemetry-quality.json", {})
    attribution = _load_json(run_root, "attribution-coverage.json", {})
    candidates = _load_json(run_root, "optimization-candidates.json", {"findings": []})
    scope_filter = _load_json(run_root, "scope-filter.json", {"allowedResourceGroups": [], "entities": {}})
    backlog = _load_json(run_root, "backlog-import.json", {"items": []})
    baseline = _load_json(run_root, "benefits-baseline.json", {})
    errors = _load_json(run_root, "errors.json", {"errors": []})
    findings = candidates.get("findings", [])
    findings = findings if isinstance(findings, list) else []
    datasets = {entity: _load_ndjson(run_root, entity) for entity in ENTITY_EVIDENCE}
    currency = reconciliation.get("currency")
    aggregate_allowed = reconciliation.get("currencyAggregationAllowed") is True
    reporting_basis = reconciliation.get("reportingBasis", "ActualCost")
    reporting_costs = [
        item for item in datasets["azure_cost"]
        if str(_value(_normalized(item), "costBasis", default="ActualCost")) == reporting_basis
    ]
    cost_rows = _cost_driver_rows(reporting_costs, aggregate_allowed)

    common = [
        ("Assessment manifest", "../assessment-manifest.json"),
        ("Optimization candidates", "../optimization-candidates.json"),
    ]
    reports: dict[str, str] = {}

    candidate_count = sum(item.get("status") == "candidate" for item in findings)
    evidence_gap_count = sum(item.get("status") == "insufficient_evidence" for item in findings)
    total_text = (
        _money(reconciliation.get("authoritativeTotal"), currency)
        if aggregate_allowed else "Not reportable across multiple currencies"
    )
    executive_body = (
        "## Assessment result\n\n"
        + _table(
            ("Measure", "Result"),
            (
                ("Run ID", manifest.get("runId")),
                ("Analysis window", f"{_text((manifest.get('analysisWindow') or {}).get('startUtc'))} to {_text((manifest.get('analysisWindow') or {}).get('endUtc'))}"),
                ("Authoritative cost", total_text),
                ("Reporting basis", reconciliation.get("reportingBasis")),
                ("Candidate findings", candidate_count),
                ("Evidence gaps", evidence_gap_count),
                ("Telemetry confidence", (quality.get("overall") or {}).get("level")),
            ),
        )
        + "\n\n## Interpretation\n\n"
        + (
            "No evidence-backed savings estimate is available. Validate each candidate before making a financial claim."
            if not any(item.get("estimatedSavings") is not None for item in findings)
            else "Savings values shown in the backlog originate from machine outputs and still require approval."
        )
        + "\n\n"
        + _findings_section(findings)
    )
    reports["01-executive-summary.md"] = _report(
        "Executive summary",
        "Summary of machine-observed cost, confidence, candidates, and evidence gaps.",
        executive_body,
        common + [
            ("Cost reconciliation", "../cost-reconciliation.json"),
            ("Telemetry quality", "../telemetry-quality.json"),
        ],
    )

    scope = manifest.get("scope") or {}
    topology_rows = []
    for entity in ("azure_resource", "workspace"):
        for item in sorted(datasets[entity], key=lambda value: str(value.get("sourceIdentifier", ""))):
            row = _normalized(item)
            topology_rows.append((
                entity,
                item.get("sourceIdentifier"),
                _value(row, "name", "workspaceName", "workspace_name"),
                _value(row, "resourceGroup", "resource_group"),
                (item.get("correlation") or {}).get("status"),
            ))
    estate_body = (
        "## Declared scope\n\n"
        + _table(
            ("Scope type", "Values"),
            (
                ("Subscriptions", ", ".join(str(value) for value in scope.get("subscriptions", [])) or "Not available"),
                ("Resource groups", ", ".join(str(value) for value in scope.get("resourceGroups", [])) or "Not available"),
                ("Resource group IDs", ", ".join(str(value) for value in scope.get("resourceGroupIds", [])) or "No qualified group limit declared"),
                ("Workspaces", ", ".join(str(value) for value in scope.get("workspaces", [])) or "Not available"),
            ),
        )
        + "\n\n## Observed topology\n\n"
        + _table(("Type", "Source ID", "Name", "Resource group", "Correlation"), topology_rows)
        + "\n\nAn absent observed resource means evidence was not collected; it does not prove the resource is absent."
        + "\n\n## Azure Databricks scope filter\n\n"
        + _table(
            ("Measure", "Value"),
            (
                ("Allowed resource groups", ", ".join(scope_filter.get("allowedResourceGroups", [])) or "Not available"),
                ("Allowed resource group IDs", ", ".join(scope_filter.get("allowedResourceGroupIds", [])) or "Not available"),
                ("Scope limitations", "; ".join(scope_filter.get("limitations", [])) or "None reported"),
                ("Azure resources excluded as unrelated", (scope_filter.get("entities", {}).get("azure_resource", {}) or {}).get("excludedRecords")),
                ("Azure cost rows excluded as unrelated", (scope_filter.get("entities", {}).get("azure_cost", {}) or {}).get("excludedRecords")),
            ),
        )
    )
    reports["02-estate-topology-and-scope.md"] = _report(
        "Estate topology and scope",
        "Declared assessment scope and observed Azure Databricks estate records.",
        estate_body,
        [
            ("Assessment manifest", "../assessment-manifest.json"),
            ("Source inventory", "../source-inventory.json"),
            ("Azure resources", ENTITY_EVIDENCE["azure_resource"]),
            ("Workspaces", ENTITY_EVIDENCE["workspace"]),
            ("Correlation", "../normalized/correlation.json"),
            ("Azure Databricks scope filter", "../scope-filter.json"),
        ],
    )

    baseline_body = (
        "## Reconciliation\n\n"
        + _table(
            ("Measure", "Value"),
            (
                ("Reporting basis", reconciliation.get("reportingBasis")),
                ("Authoritative total", total_text),
                ("Collected total", _money(reconciliation.get("collectedTotal"), currency) if aggregate_allowed else "Not reportable across multiple currencies"),
                ("Variance", _money(reconciliation.get("varianceAmount"), currency) if aggregate_allowed else "Not reportable across multiple currencies"),
                ("Variance percent", _percent(reconciliation.get("variancePercent")) if aggregate_allowed else "Not reportable across multiple currencies"),
                ("Matched cost", _money(reconciliation.get("matchedCost"), currency) if aggregate_allowed else "Not reportable across multiple currencies"),
                ("Unmatched cost", _money(reconciliation.get("unmatchedCost"), currency) if aggregate_allowed else "Not reportable across multiple currencies"),
                ("Allocated shared cost", _money(reconciliation.get("allocatedSharedCost"), currency) if aggregate_allowed else "Not reportable across multiple currencies"),
                ("Excluded cost", _money(reconciliation.get("excludedCost"), currency) if aggregate_allowed else "Not reportable across multiple currencies"),
                ("Within tolerance", reconciliation.get("withinTolerance")),
                ("Tax included", reconciliation.get("taxIncluded")),
            ),
        )
        + "\n\n## Duplicate prevention\n\n"
        + _text((reconciliation.get("duplicatePrevention") or {}).get("rule"))
        + "\n\n## Limitations\n\n"
        + "\n".join(f"- {_text(value)}" for value in (reconciliation.get("limitations") or ["Tax treatment is not available."]))
        + "\n- Azure resource and cost totals are filtered to the selected workspace resource groups and their managed resource groups."
    )
    reports["03-current-cost-baseline.md"] = _report(
        "Current cost baseline and reconciliation",
        "Current-state cost totals exactly as represented by the machine reconciliation output.",
        baseline_body,
        [
            ("Cost reconciliation", "../cost-reconciliation.json"),
            ("Azure Databricks scope filter", "../scope-filter.json"),
            ("Benefits baseline", "../benefits-baseline.json"),
            ("Azure cost records", ENTITY_EVIDENCE["azure_cost"]),
        ],
    )

    if aggregate_allowed and cost_rows:
        drivers_body = (
            "## Ranked observed drivers\n\n"
            + _table(
                ("Rank", "Driver", "Observed cost", "Currency"),
                ((row["rank"], row["driver"], f"{row['cost']:,.2f}", row["currency"] or "Not available") for row in cost_rows),
            )
            + "\n\nRanking reflects observed cost records only; it is not a savings estimate."
        )
    else:
        drivers_body = (
            "## Ranked observed drivers\n\n"
            "**Insufficient evidence:** cost drivers cannot be ranked because no cost records were collected "
            "or multiple currencies cannot be aggregated without an approved conversion source."
        )
    reports["04-top-cost-drivers.md"] = _report(
        "Top cost drivers",
        "Deterministic ranking of observed cost records by resource or service label.",
        drivers_body,
        [("Azure cost records", ENTITY_EVIDENCE["azure_cost"]), ("Cost reconciliation", "../cost-reconciliation.json")],
    )

    unattributed_by_resource: dict[tuple[str, str], float] = {}
    for item in reporting_costs:
        row = _normalized(item)
        tags = _value(row, "tags", "Tags", default={})
        tags = tags if isinstance(tags, dict) else {}
        if not any(_value(tags, key) not in (None, "") for key in ("Owner", "Team", "BusinessUnit", "Project", "Environment", "CostCenter")):
            resource = _text(_value(row, "ResourceId", "resourceId", "ResourceName", "resourceName"))
            row_currency = _text(_value(row, "Currency", "currency", default=currency))
            cost = _number(_value(row, "PreTaxCost", "Cost", "cost")) or 0.0
            key = (resource, row_currency)
            unattributed_by_resource[key] = unattributed_by_resource.get(key, 0.0) + cost
    unattributed = [
        (resource, _money(cost, row_currency))
        for (resource, row_currency), cost in sorted(
            unattributed_by_resource.items(),
            key=lambda value: (-value[1], value[0][0].lower()),
        )
    ]
    unattributed_limit = 100
    unattributed_display = unattributed[:unattributed_limit]
    unattributed_body = (
        "## Coverage\n\n"
        + _table(
            ("Measure", "Value"),
            (
                ("Resource coverage", _percent(attribution.get("resourceCoveragePercent"))),
                ("Spend coverage", _percent(attribution.get("spendCoveragePercent"))),
                ("Unmatched reconciliation cost", _money(reconciliation.get("unmatchedCost"), currency) if aggregate_allowed else "Not reportable across multiple currencies"),
            ),
        )
        + "\n\n## Cost records without approved allocation tags\n\n"
        + _table(("Resource", "Observed cost"), unattributed_display)
        + (
            f"\n\nShowing the top {unattributed_limit} of {len(unattributed)} unattributed resources. "
            "Use the normalized Azure cost evidence for the complete record set."
            if len(unattributed) > unattributed_limit else ""
        )
        + "\n\nUnattributed and unmatched are separate concepts: attribution uses approved ownership tags; reconciliation matching uses resource correlation."
        + "\n\n"
        + _findings_section(findings, {"MON-UNOWNED-COST"})
    )
    reports["05-unattributed-cost.md"] = _report(
        "Unattributed cost",
        "Ownership/allocation coverage and cost records lacking approved attribution tags.",
        unattributed_body,
        [
            ("Attribution coverage", "../attribution-coverage.json"),
            ("Cost reconciliation", "../cost-reconciliation.json"),
            ("Azure cost records", ENTITY_EVIDENCE["azure_cost"]),
            ("Optimization candidates", "../optimization-candidates.json"),
        ],
    )

    reports["06-compute-right-sizing.md"] = _report(
        "Compute and right-sizing",
        "Compute inventory and evidence-backed sizing or configuration candidates.",
        "## Available datasets\n\n"
        + _dataset_summary(datasets, ("compute", "node_timeline"))
        + "\n\n"
        + _findings_section(findings, {"OPT-INTERACTIVE-AUTOTERMINATION", "DYN-AUTOSCALING", "WRK-DRIVER-ON-SPOT"}),
        common + [("Compute", ENTITY_EVIDENCE["compute"]), ("Node timeline", ENTITY_EVIDENCE["node_timeline"])],
    )
    reports["07-sql-warehouse-query.md"] = _report(
        "SQL Warehouse and query assessment",
        "Available SQL Warehouse and query evidence without inferred performance conclusions.",
        "## Available datasets\n\n"
        + _dataset_summary(datasets, ("warehouse", "query"))
        + "\n\n**Insufficient evidence:** no SQL-specific detector output contract is currently present. "
        "Warehouse sizing, queueing, query efficiency, and savings require validated workload metrics.",
        [("SQL Warehouses", ENTITY_EVIDENCE["warehouse"]), ("Query history", ENTITY_EVIDENCE["query"]), ("Source inventory", "../source-inventory.json")],
    )
    reports["08-jobs-pipelines.md"] = _report(
        "Jobs and pipelines assessment",
        "Scheduled workload inventory and evidence-backed findings.",
        "## Available datasets\n\n"
        + _dataset_summary(datasets, ("job", "job_run", "pipeline"))
        + "\n\n"
        + _findings_section(findings, {"OPT-JOB-COMPUTE"}),
        common + [
            ("Jobs", ENTITY_EVIDENCE["job"]),
            ("Job runs", ENTITY_EVIDENCE["job_run"]),
            ("Pipelines", ENTITY_EVIDENCE["pipeline"]),
        ],
    )

    spark_links = _raw_evidence_links(source_inventory, "spark-")
    spark_body = (
        "## Deep-dive evidence index\n\n"
        + (
            "\n".join(f"- {_link(label, target)}" for label, target in spark_links)
            if spark_links else "**Insufficient evidence:** no selected Spark deep-dive evidence pack was collected."
        )
        + "\n\nFull Spark stage, task, executor, spill, skew, and SQL execution conclusions require approved event-log or Spark UI metric exports."
    )
    reports["09-spark-deep-dive-index.md"] = _report(
        "Spark deep-dive index",
        "Index of collected deep-dive evidence; no missing Spark metrics are inferred.",
        spark_body,
        [("Source inventory", "../source-inventory.json")] + spark_links,
    )
    reports["10-delta-data-layout.md"] = _report(
        "Delta and data-layout assessment",
        "Available table metadata, file-summary, and operation evidence.",
        "## Available datasets\n\n"
        + _dataset_summary(datasets, ("table", "table_file_summary", "table_operation"))
        + "\n\n**Insufficient evidence:** no Delta/data-layout detector output contract is currently present. "
        "Do not infer small-file, partitioning, compaction, or retention findings from record counts alone.",
        [
            ("Tables", ENTITY_EVIDENCE["table"]),
            ("Table file summaries", ENTITY_EVIDENCE["table_file_summary"]),
            ("Table operations", ENTITY_EVIDENCE["table_operation"]),
        ],
    )
    reports["11-governance-finops.md"] = _report(
        "Governance, policies, budgets, and FinOps",
        "Policy, budget, and ownership evidence with applicable monitor-and-control findings.",
        "## Available datasets\n\n"
        + _dataset_summary(datasets, ("policy", "budget"))
        + "\n\n"
        + _findings_section(findings, {"MON-UNOWNED-COST", "MON-MISSING-BUDGET"}),
        common + [
            ("Policies", ENTITY_EVIDENCE["policy"]),
            ("Budgets", ENTITY_EVIDENCE["budget"]),
            ("Attribution coverage", "../attribution-coverage.json"),
        ],
    )
    reports["12-commitment-readiness.md"] = _report(
        "Commitment readiness",
        "Evidence gate for reserved-capacity or committed-use decisions.",
        "## Readiness result\n\n"
        "**Insufficient evidence:** the machine outputs do not contain an approved demand forecast, "
        "stable SKU-level utilization baseline, contract pricing, architecture approval, or risk-adjusted break-even analysis. "
        "No commitment recommendation is made.\n\n"
        "Required validation: representative demand history, workload growth forecast, eligible SKU/region mapping, "
        "contract terms, break-even horizon, portability constraints, and executive approval.",
        [
            ("Cost reconciliation", "../cost-reconciliation.json"),
            ("Benefits baseline", "../benefits-baseline.json"),
            ("Telemetry quality", "../telemetry-quality.json"),
        ],
    )

    source_rows = []
    for item in sorted(quality.get("sources", []), key=lambda value: str(value.get("source", "")).lower()):
        source_rows.append((item.get("source"), item.get("level"), item.get("score"), ", ".join(item.get("missingRequiredMetrics", [])) or "None"))
    error_rows = [
        (item.get("kind"), item.get("source"), item.get("message"))
        for item in sorted(errors.get("errors", []), key=lambda value: (str(value.get("source", "")), str(value.get("kind", "")), str(value.get("message", ""))))
    ]
    telemetry_body = (
        "## Overall quality\n\n"
        + _table(
            ("Level", "Score", "Missing required metrics"),
            (((quality.get("overall") or {}).get("level"), (quality.get("overall") or {}).get("score"), ", ".join((quality.get("overall") or {}).get("missingRequiredMetrics", [])) or "None"),),
        )
        + "\n\n## Source quality\n\n"
        + _table(("Source", "Level", "Score", "Missing required metrics"), source_rows)
        + "\n\n## Collection and parsing limitations\n\n"
        + _table(("Kind", "Source", "Message"), error_rows)
        + "\n\nMissing permission, an empty source, and absent data require separate human interpretation; none is treated as healthy behavior."
    )
    reports["13-telemetry-quality-limitations.md"] = _report(
        "Telemetry quality and limitations",
        "Coverage, confidence, and explicit collection or parsing limitations.",
        telemetry_body,
        [
            ("Telemetry quality", "../telemetry-quality.json"),
            ("Source inventory", "../source-inventory.json"),
            ("Errors", "../errors.json"),
            ("Collection status", "../collection-status.json"),
        ],
    )

    ranked = sorted(
        findings,
        key=lambda item: (
            item.get("status") != "candidate",
            -float((item.get("confidence") or {}).get("score") or 0),
            str(item.get("detectorId", "")),
        ),
    )
    backlog_rows = []
    for rank, item in enumerate(ranked, 1):
        backlog_rows.append((
            rank,
            item.get("findingId") or item.get("detectorId"),
            "Validation queue" if item.get("status") == "candidate" else "Evidence gap",
            item.get("status"),
            (item.get("confidence") or {}).get("level"),
            "Not estimated" if item.get("estimatedSavings") is None else _money(item.get("estimatedSavings"), item.get("savingsCurrency")),
            item.get("recommendedAction"),
        ))
    backlog_body = (
        "## Provisional review order\n\n"
        "Order is deterministic: candidates first, then confidence score, then finding ID. "
        "It is not an ROI ranking because savings, effort, risk, owner, and approval are not available.\n\n"
        + _table(("Order", "Finding ID", "Queue", "Status", "Confidence", "Estimated savings", "Action"), backlog_rows)
    )
    reports["14-prioritized-backlog.md"] = _report(
        "Prioritized optimization backlog",
        "Conservative validation queue derived from machine findings.",
        backlog_body,
        [("Backlog import", "../backlog-import.json"), ("Optimization candidates", "../optimization-candidates.json")],
    )

    finding_ids = ", ".join(str(item.get("findingId") or item.get("detectorId")) for item in ranked) or "None produced"
    roadmap_body = (
        "## Days 0-30: validate evidence and ownership\n\n"
        f"- Review finding IDs: {finding_ids}.\n"
        "- Assign workload owner, reviewer, approver, SLA context, and validation experiment.\n"
        "- Close telemetry gaps before accepting insufficient-evidence items.\n\n"
        "## Days 31-60: controlled validation\n\n"
        "- Pilot only findings accepted during human review.\n"
        "- Capture pre-change performance, reliability, and cost baselines; no item is pre-approved by this roadmap.\n\n"
        "## Days 61-90: scale or stop\n\n"
        "- Expand only validated changes with no unacceptable SLA, security, or governance impact.\n"
        "- Compare actual results with the versioned baseline and record final sign-off.\n\n"
        "**Scheduling limitation:** machine outputs contain no approved owners, dates, effort estimates, or dependencies; "
        "therefore individual findings are not assigned to a delivery phase."
    )
    reports["15-30-60-90-roadmap.md"] = _report(
        "30/60/90 roadmap",
        "Evidence-first delivery gates without invented schedules or savings.",
        roadmap_body,
        [("Prioritized backlog", "14-prioritized-backlog.md"), ("Optimization candidates", "../optimization-candidates.json")],
    )

    realized = baseline.get("realizedSavings")
    benefits_body = (
        "## Baseline\n\n"
        + _table(
            ("Measure", "Value"),
            (
                ("Baseline ID", baseline.get("baselineId")),
                ("Reporting basis", baseline.get("reportingBasis")),
                ("Authoritative cost", _money(baseline.get("authoritativeCost"), baseline.get("currency")) if aggregate_allowed else "Not reportable across multiple currencies"),
                ("Normalization method", (baseline.get("workloadNormalization") or {}).get("method")),
                ("Normalization rationale", (baseline.get("workloadNormalization") or {}).get("reason")),
                ("Realized savings", _money(realized, baseline.get("currency")) if realized is not None else "Insufficient evidence - no post-change comparison"),
            ),
        )
        + "\n\nA benefits claim requires an approved change, a comparable post-change window, workload normalization, "
        "and validation that performance, reliability, security, and governance outcomes remain acceptable."
    )
    reports["16-benefits-realization.md"] = _report(
        "Benefits realization",
        "Versioned baseline and status of post-change savings validation.",
        benefits_body,
        [("Benefits baseline", "../benefits-baseline.json"), ("Cost reconciliation", "../cost-reconciliation.json")],
    )

    signoff_rows = [
        (
            item.get("findingId") or item.get("detectorId"),
            item.get("title"),
            _finding_evidence_links(str(item.get("detectorId", ""))),
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
        )
        for item in sorted(findings, key=lambda value: str(value.get("detectorId", "")))
    ]
    signoff_body = (
        "## Review register\n\n"
        "Complete every field before treating a finding as accepted. Allowed decisions: accept, reject, defer, or needs more evidence.\n\n"
        + _table(
            (
                "Finding ID", "Finding", "Evidence links", "Reviewer", "Role", "Reviewed at UTC", "Decision",
                "Business/SLA context", "Performance/reliability risk", "Security/governance impact",
                "Validation experiment", "Owner/approver", "Rationale",
            ),
            signoff_rows,
        )
        + "\n\n## Required sign-off coverage\n\n"
        "- Databricks platform owner\n"
        "- Workload owner\n"
        "- Data engineering or SQL owner\n"
        "- FinOps owner\n"
        "- Security/governance reviewer where applicable\n"
        "- Executive sponsor for commitment or architecture decisions"
    )
    reports["17-human-validation-sign-off.md"] = _report(
        "Human validation and sign-off",
        "Review template linking every machine finding to its evidence and decision record.",
        signoff_body,
        [("Optimization candidates", "../optimization-candidates.json"), ("Backlog import", "../backlog-import.json")],
    )

    table_of_contents = "\n".join(
        f"{number}. [{title}](#{number}-{title.lower().replace('/', '').replace(' ', '-')})"
        for number, (_, title) in enumerate(REPORT_FILES, 1)
    )
    sections = []
    for number, (filename, _) in enumerate(REPORT_FILES, 1):
        content = reports[filename]
        lines = content.splitlines()
        demoted = [
            f"#{line}" if line.startswith("#") else line
            for line in lines
        ]
        if demoted and demoted[0].startswith("## "):
            demoted[0] = f"## {number}. {demoted[0][3:]}"
        sections.append("\n".join(demoted).rstrip())

    consolidated = (
        "# Azure Databricks Cost Optimization Assessment Report\n\n"
        "This consolidated report is generated from the machine-readable evidence in the parent run directory. "
        "Do not edit generated findings by hand; record human decisions in the sign-off section or CSV export.\n\n"
        "## Contents\n\n"
        f"{table_of_contents}\n\n"
        "## Supporting exports\n\n"
        "- [Top cost drivers CSV](top-cost-drivers.csv)\n"
        "- [Prioritized backlog CSV](prioritized-backlog.csv)\n"
        "- [Human validation and sign-off CSV](human-validation-sign-off.csv)\n\n"
        + "\n\n---\n\n".join(sections)
        + "\n"
    )

    for stale in reports_root.glob("*.md"):
        stale.unlink()

    written = []
    report_path = reports_root / "assessment-report.md"
    report_path.write_text(consolidated, encoding="utf-8", newline="\n")
    written.append(report_path)

    csv_outputs = {
        "top-cost-drivers.csv": _csv_text(
            ["rank", "driver", "observedCost", "currency"],
            ((row["rank"], row["driver"], row["cost"], row["currency"]) for row in cost_rows),
        ),
        "prioritized-backlog.csv": _csv_text(
            ["order", "findingId", "queue", "status", "confidence", "estimatedSavings", "recommendedAction"],
            backlog_rows,
        ),
        "human-validation-sign-off.csv": _csv_text(
            [
                "findingId", "finding", "evidenceLinks", "reviewer", "role", "reviewedAtUtc", "decision",
                "businessSlaContext", "performanceReliabilityRisk", "securityGovernanceImpact",
                "validationExperiment", "ownerApprover", "rationale",
            ],
            signoff_rows,
        ),
    }
    for name, content in sorted(csv_outputs.items()):
        path = reports_root / name
        path.write_text(content, encoding="utf-8", newline="\n")
        written.append(path)
    return sorted(written)
