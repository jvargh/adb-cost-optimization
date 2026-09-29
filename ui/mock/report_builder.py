"""Builds the consolidated Markdown report preview shown in the Review screen.

The section order mirrors `assessment/reports/render.py` exactly so reviewers
see the same document structure the backend produces.
"""

from __future__ import annotations

from typing import Any

SECTIONS = [
    "Executive summary",
    "Estate topology and scope",
    "Current cost baseline and reconciliation",
    "Top cost drivers",
    "Unattributed cost",
    "Compute and right-sizing",
    "SQL Warehouse and query assessment",
    "Jobs and pipelines assessment",
    "Spark deep-dive index",
    "Delta and data-layout assessment",
    "Governance, policies, budgets, and FinOps",
    "Commitment readiness",
    "Telemetry quality and limitations",
    "Prioritized optimization backlog",
    "30/60/90 roadmap",
    "Benefits realization",
    "Human validation and sign-off",
]


def _money(value: float, currency: str) -> str:
    return f"{value:,.2f} {currency}"


def build_report(results: dict[str, Any]) -> str:
    manifest = results["manifest"]
    recon = results["reconciliation"]
    attribution = results["attribution"]
    telemetry = results["telemetry"]
    candidates = results["candidates"]
    currency = recon["currency"]

    lines: list[str] = []
    lines.append("# Azure Databricks Cost Optimization Assessment Report")
    lines.append("")
    lines.append(f"- Run ID: `{manifest['runId']}`")
    lines.append(f"- Customer: `{manifest['customerId']}`")
    lines.append(f"- Run status: **{manifest['status']}**")
    lines.append(
        f"- Analysis window: {manifest['analysisWindow']['startUtc']} through "
        f"{manifest['analysisWindow']['endUtc']} ({manifest['analysisWindow']['timeZone']})"
    )
    lines.append(f"- Toolkit version: `{manifest['toolkitVersion']}`")
    lines.append("")
    lines.append("## Contents")
    lines.append("")
    for index, title in enumerate(SECTIONS, start=1):
        anchor = title.lower().replace(" ", "-").replace(",", "").replace("/", "")
        lines.append(f"{index}. [{title}](#{index}-{anchor})")
    lines.append("")

    lines.append("## 1. Executive summary")
    lines.append("")
    lines.append("### Assessment result")
    lines.append("")
    lines.append(
        f"The assessment completed with status **{manifest['status']}**. "
        f"Authoritative in-scope cost for the window is {_money(recon['authoritativeTotal'], currency)} "
        f"on an {recon['reportingBasis']} basis."
    )
    lines.append("")
    lines.append(
        f"{candidates['candidateCount']} candidate findings and "
        f"{candidates['insufficientEvidenceCount']} insufficient-evidence findings were produced."
    )
    lines.append("")
    lines.append("### Interpretation")
    lines.append("")
    lines.append(
        "Every finding in this report is a candidate that requires human validation. "
        "No savings figure is estimated or claimed, and no change has been made to the estate. "
        "This assessment is read-only."
    )
    lines.append("")
    lines.append("### Findings")
    lines.append("")
    lines.append("| Detector | Title | Status | Confidence | Estimated savings |")
    lines.append("| --- | --- | --- | --- | --- |")
    for f in candidates["findings"]:
        lines.append(
            f"| `{f['detectorId']}` | {f['title']} | {f['status']} | "
            f"{f['confidence']['level']} ({f['confidence']['score']:.2f}) | Not estimated |"
        )
    lines.append("")

    lines.append("## 2. Estate topology and scope")
    lines.append("")
    lines.append("### Declared scope")
    lines.append("")
    lines.append(f"- Tenant: `{manifest['scope']['tenantId']}`")
    for sub in manifest["scope"]["subscriptionIds"]:
        lines.append(f"- Subscription: `{sub}`")
    for rg in manifest["scope"]["resourceGroups"]:
        lines.append(f"- Resource group: `{rg}`")
    lines.append("")
    lines.append("### Observed topology")
    lines.append("")
    lines.append("| Workspace | Workspace ID | Resource group | Subscription |")
    lines.append("| --- | --- | --- | --- |")
    for ws in manifest["scope"]["workspaces"]:
        lines.append(
            f"| {ws['name']} | `{ws['workspaceId']}` | {ws['resourceGroup']} | `{ws['subscriptionId']}` |"
        )
    lines.append("")
    lines.append("### Azure Databricks scope filter")
    lines.append("")
    scope_filter = results["scopeFilter"]
    lines.append("| Entity | Input records | Included | Excluded |")
    lines.append("| --- | ---: | ---: | ---: |")
    for entity, counts in sorted(scope_filter["entities"].items()):
        lines.append(
            f"| `{entity}` | {counts['inputRecords']} | {counts['includedRecords']} | {counts['excludedRecords']} |"
        )
    lines.append("")

    lines.append("## 3. Current cost baseline and reconciliation")
    lines.append("")
    lines.append("| Measure | Value |")
    lines.append("| --- | ---: |")
    lines.append(f"| Authoritative total | {_money(recon['authoritativeTotal'], currency)} |")
    lines.append(f"| Collected total | {_money(recon['collectedTotal'], currency)} |")
    lines.append(f"| Matched | {_money(recon['matchedCost'], currency)} |")
    lines.append(f"| Unmatched | {_money(recon['unmatchedCost'], currency)} |")
    lines.append(f"| Excluded | {_money(recon['excludedCost'], currency)} |")
    lines.append(f"| Variance | {recon['variancePercent']:.2f}% |")
    lines.append(f"| Within tolerance | {str(recon['withinTolerance']).lower()} |")
    lines.append("")
    lines.append("### Duplicate prevention")
    lines.append("")
    lines.append(f"> {recon['duplicatePrevention']['rule']}")
    lines.append("")

    lines.append("## 4. Top cost drivers")
    lines.append("")
    lines.append("| Rank | Driver | Observed cost |")
    lines.append("| ---: | --- | ---: |")
    for driver in results["costDrivers"][:10]:
        lines.append(
            f"| {driver['rank']} | `{driver['displayName']}` | {_money(driver['observedCost'], currency)} |"
        )
    lines.append("")

    lines.append("## 5. Unattributed cost")
    lines.append("")
    lines.append(
        f"Spend attribution coverage is {attribution['spendCoveragePercent']:.1f}% of "
        f"{_money(attribution['totalSpend'], currency)}. "
        f"Resource attribution coverage is {attribution['resourceCoveragePercent']:.1f}% "
        f"across {attribution['resourceCount']} resources."
    )
    lines.append("")

    for index, title in enumerate(SECTIONS[5:12], start=6):
        lines.append(f"## {index}. {title}")
        lines.append("")
        lines.append("### Available datasets")
        lines.append("")
        related = [
            s for s in results["collection"] if _section_matches(title, s["name"])
        ]
        if related:
            lines.append("| Source | Status | Items |")
            lines.append("| --- | --- | ---: |")
            for s in related:
                lines.append(f"| {s['name']} | {s['status']} | {s['itemCount']} |")
        else:
            lines.append("No dataset was collected for this section in this run.")
        lines.append("")

    lines.append("## 13. Telemetry quality and limitations")
    lines.append("")
    lines.append(
        f"Overall telemetry quality is **{telemetry['overall']['level']}** "
        f"with a score of {telemetry['overall']['score']:.4f}."
    )
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("| --- | ---: |")
    for metric, value in sorted(telemetry["overall"]["metrics"].items()):
        lines.append(f"| {metric} | {value:.4f} |")
    lines.append("")
    lines.append("### Collection and parsing limitations")
    lines.append("")
    for gap in results["evidenceGaps"]:
        lines.append(f"- **{gap['source']}** ({gap['status']}): {gap['impact']}")
    lines.append("")

    lines.append("## 14. Prioritized optimization backlog")
    lines.append("")
    lines.append("### Provisional review order")
    lines.append("")
    lines.append("| Order | Detector | Confidence | Status |")
    lines.append("| ---: | --- | --- | --- |")
    ordered = sorted(
        candidates["findings"],
        key=lambda f: (f["status"] != "candidate", -f["confidence"]["score"]),
    )
    for order, f in enumerate(ordered, start=1):
        lines.append(
            f"| {order} | `{f['detectorId']}` | {f['confidence']['level']} | {f['status']} |"
        )
    lines.append("")

    lines.append("## 15. 30/60/90 roadmap")
    lines.append("")
    for horizon, heading in (
        ("0-30", "Days 0-30: validate evidence and ownership"),
        ("31-60", "Days 31-60: controlled validation"),
        ("61-90", "Days 61-90: scale or stop"),
    ):
        lines.append(f"### {heading}")
        lines.append("")
        for item in results["roadmap"]:
            if item["horizon"] == horizon:
                lines.append(f"- **{item['title']}** ({item['owner']}) — {item['detail']}")
        lines.append("")

    lines.append("## 16. Benefits realization")
    lines.append("")
    benefits = results["benefits"]
    lines.append(f"- Baseline ID: `{benefits['baselineId']}`")
    lines.append(f"- Authoritative cost: {_money(benefits['authoritativeCost'], currency)}")
    lines.append("- Realized savings: **null** (no change has been made, so nothing has been measured)")
    lines.append(f"- Workload normalization: {benefits['workloadNormalization']['method']} — {benefits['workloadNormalization']['reason']}")
    lines.append("")

    lines.append("## 17. Human validation and sign-off")
    lines.append("")
    lines.append(
        "No finding in this report may be acted upon until the reviewer, role, decision, "
        "and rationale columns below are completed by an accountable owner."
    )
    lines.append("")
    lines.append("| Finding | Reviewer | Role | Decision | Rationale |")
    lines.append("| --- | --- | --- | --- | --- |")
    for entry in results["review"]:
        lines.append(
            f"| `{entry['findingId']}` | {entry['reviewer'] or '_pending_'} | "
            f"{entry['role'] or '_pending_'} | {entry['decision']} | {entry['rationale'] or '_pending_'} |"
        )
    lines.append("")
    return "\n".join(lines)


def _section_matches(section_title: str, source_name: str) -> bool:
    keywords = {
        "Compute and right-sizing": ["compute"],
        "SQL Warehouse and query assessment": ["SQL"],
        "Jobs and pipelines assessment": ["workloads"],
        "Spark deep-dive index": ["Spark"],
        "Delta and data-layout assessment": ["Unity Catalog"],
        "Governance, policies, budgets, and FinOps": ["governance", "budgets", "policy"],
        "Commitment readiness": ["quotas", "commitments"],
    }
    for keyword in keywords.get(section_title, []):
        if keyword.lower() in source_name.lower():
            return True
    return False
