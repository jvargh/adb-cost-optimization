"""Evidence-based optional analyses. No network access and no third-party runtime."""
from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from assessment.model.core import confidence_from_metrics

VERSION = "1.0"
DEFAULT_RULES = {"idleCpuPercent": 10, "busyCpuPercent": 80, "highMemoryPercent": 80,
                 "minimumSamples": 30, "slowQuerySeconds": 60, "failureRatePercent": 10}
MODULES = ("utilization", "sizing", "jobs", "queries", "network", "posture", "assets", "commitments")
ASSETS = ("repos", "notebooks", "experiments", "serving-endpoints", "sql-alerts", "genie-spaces", "uc-volumes")


def number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError):
        return None


def timestamp(value: Any) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)) or str(value).isdigit():
        n = number(value)
        return n / 1000 if n is not None and n > 10**11 else n
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.replace(tzinfo=parsed.tzinfo or timezone.utc).timestamp()
    except ValueError:
        return None


def percentile(values: list[float], q: float = .95) -> float | None:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * q) - 1)] if ordered else None


def percentage(value: Any) -> float | None:
    value = number(value)
    return value if value is not None and 0 <= value <= 100 else None


def mapping(value: Any, field: str) -> dict:
    if isinstance(value, str) and value:
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{field} contains invalid JSON object evidence.") from exc
    if value is None or value == "":
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{field} must contain an object.")
    return value


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()[:24]


def validate_options(options: Any) -> dict:
    if options is None:
        options = {}
    if not isinstance(options, dict) or set(options) - {"profile", "concurrency", "assets", "rules", "modules"}:
        raise ValueError("Capabilities must contain only profile, concurrency, assets, rules and modules.")
    rules = options.get("rules", {})
    if not isinstance(rules, dict) or set(rules) - DEFAULT_RULES.keys():
        raise ValueError("Unknown analysis rule. Import only the supported rule fields.")
    rules = {**DEFAULT_RULES, **rules}
    for key, value in rules.items():
        maximum = 100000 if key in {"minimumSamples", "slowQuerySeconds"} else 100
        if number(value) is None or isinstance(value, str) or not 0 < value <= maximum:
            raise ValueError(f"{key} must be a number greater than 0 and at most {maximum}.")
    if not float(rules["minimumSamples"]).is_integer() or rules["idleCpuPercent"] >= rules["busyCpuPercent"]:
        raise ValueError("Minimum samples must be an integer; idle CPU must be below busy CPU.")
    profile = options.get("profile", "standard")
    concurrency = options.get("concurrency", 1)
    if profile not in ("standard", "extended", "custom") or type(concurrency) is not int or not 1 <= concurrency <= 4:
        raise ValueError("Profile must be standard/extended/custom; concurrency must be an integer from 1 to 4.")
    assets = options.get("assets", list(ASSETS) if profile == "extended" else [])
    modules = options.get("modules", list(MODULES))
    if not isinstance(assets, list) or any(a not in ASSETS for a in assets):
        raise ValueError("Unsupported asset type.")
    if not isinstance(modules, list) or any(m not in MODULES for m in modules):
        raise ValueError("Unsupported analysis module.")
    return {"profile": profile, "concurrency": concurrency, "assets": sorted(set(assets)),
            "modules": sorted(set(modules)), "rules": rules}


def analyze(datasets: dict[str, list[dict]], config: dict, sources: list[dict] | None = None) -> dict:
    options = validate_options(config.get("capabilities"))
    rules = options["rules"]
    window = config.get("analysis", {})
    start, end = timestamp(window.get("startUtc")), timestamp(window.get("endUtc"))
    workspaces = {str(w.get("workspaceId")): w for w in config.get("databricks", {}).get("workspaces", []) if w.get("include", True)}
    rows: dict[str, list[dict]] = {name: [] for name in MODULES}
    findings: list[dict] = []
    limitations = ["Metrics describe collected samples, not guaranteed whole-window coverage.",
                   "Detailed Spark stage/task/executor evidence is not supplied.",
                   "Sizing is an experiment candidate, not a savings or resize instruction."]
    aliases = {str(w.get("workspaceUrl", "")).removeprefix("https://").rstrip("/"): key for key, w in workspaces.items()}

    def values(entity: str) -> list[dict]:
        result = []
        for record in datasets.get(entity, []):
            value = dict(record.get("normalized", record))
            scope = record.get("customerScope") or {}
            ws = str(value.get("workspace_id") or value.get("workspaceId") or value.get("workspaceKey") or scope.get("workspaceKey") or "")
            ws = aliases.get(ws, ws)
            if not ws or (workspaces and ws not in workspaces):
                continue
            value["_ws"] = ws
            value["_source"] = (record.get("provenance") or {}).get("sourceFile", f"normalized/{entity}.ndjson")
            result.append(value)
        return result

    def base(value: dict, identity: Any, name: Any = None) -> dict:
        ws = value["_ws"]
        return {"key": digest([config.get("azure", {}).get("tenantId"), config.get("databricks", {}).get("accountId"), ws, identity]),
                "workspaceId": ws, "workspaceName": workspaces.get(ws, {}).get("name", ws),
                "subscriptionId": workspaces.get(ws, {}).get("subscriptionId"),
                "resourceGroup": workspaces.get(ws, {}).get("resourceGroup"),
                "resourceId": str(identity), "name": str(name or identity), "evidence": value["_source"]}

    def finding(domain: str, row: dict, title: str, explanation: str, action: str) -> None:
        rule_id = f"CAP-{domain.upper()}"
        confidence = confidence_from_metrics({"coverage": 0.0, "completeness": 1.0,
            "sourceAuthority": 0.5 if config.get("evidenceOrigin") == "imported" else 1.0}, ("coverage", "completeness"))
        confidence["missingRequiredMetrics"].append("Complete-window coverage and business validation")
        findings.append({
            "schemaVersion": VERSION, "findingId": digest([rule_id, row["key"], title, rules]),
            "detectorId": rule_id, "domain": domain, "title": title,
            "category": "monitor-and-control-cost", "status": "candidate",
            "explanation": explanation, "recommendedAction": action,
            "confidence": confidence,
            "evidence": [{k: v for k, v in row.items() if isinstance(v, (str, int, float, bool)) or v is None}],
            "limitations": ["Human validation required; no resource changes are performed."],
            "humanValidationRequired": True, "estimatedSavings": None, "savingsCurrency": None,
            "scope": {"workspaceId": row["workspaceId"], "workspaceName": row["workspaceName"],
                      "subscriptionId": row.get("subscriptionId"), "resourceGroup": row.get("resourceGroup"), "workload": row["name"]},
            "evidenceFiles": ["capability-analysis.json", row["evidence"]], "ruleVersion": digest(rules)})

    nodes: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for value in values("node_timeline"):
        a, b = timestamp(value.get("start_time")), timestamp(value.get("end_time"))
        if a is None or b is None or b <= a or (start is not None and b <= start) or (end is not None and a >= end):
            continue
        clipped = dict(value, _seconds=min(b, end or b) - max(a, start or a), _intervalSeconds=b - a)
        nodes[value["_ws"], str(value.get("cluster_id"))].append(clipped)
    clusters = {}
    for value in values("compute"):
        key = value["_ws"], str(value.get("cluster_id"))
        if key not in clusters or (timestamp(value.get("change_time")) or 0) > (timestamp(clusters[key].get("change_time")) or 0):
            clusters[key] = value
    for key, cluster in clusters.items():
        samples = nodes.get(key, [])
        row = base(cluster, key[1], cluster.get("cluster_name"))
        series = []
        for sample in samples:
            cpu = percentage(sample.get("cpu_user_percent"))
            system = percentage(sample.get("cpu_system_percent"))
            series.append({"start": sample.get("start_time"), "instanceId": sample.get("instance_id"), "role": "driver" if sample.get("driver") in (True, "true", "True", 1) else "worker",
                           "cpuPercent": percentage(cpu + system) if cpu is not None and system is not None else None,
                           "memoryPercent": percentage(sample.get("mem_used_percent")), "cpuWaitPercent": percentage(sample.get("cpu_wait_percent")),
                           "seconds": sample["_seconds"], "intervalSeconds": sample["_intervalSeconds"],
                           "receivedMiB": (number(sample.get("network_received_bytes")) / 1048576) if number(sample.get("network_received_bytes")) is not None else None,
                           "sentMiB": (number(sample.get("network_sent_bytes")) / 1048576) if number(sample.get("network_sent_bytes")) is not None else None})
        series.sort(key=lambda sample: (timestamp(sample["start"]), str(sample["instanceId"])))
        def mean(field: str) -> float | None:
            valid = [s for s in series if s[field] is not None]
            return sum(s[field] * s["seconds"] for s in valid) / sum(s["seconds"] for s in valid) if valid else None
        cpus = [s["cpuPercent"] for s in series if s["cpuPercent"] is not None]
        cpu, memory = mean("cpuPercent"), mean("memoryPercent")
        adequate = len(cpus) >= rules["minimumSamples"]
        memory_adequate = sum(s["memoryPercent"] is not None for s in series) >= rules["minimumSamples"]
        category = "Insufficient evidence" if not adequate else "Low utilization" if cpu < rules["idleCpuPercent"] else "Busy" if cpu >= rules["busyCpuPercent"] else "Moderate"
        idle_samples = [s for s in series if s["cpuPercent"] is not None]
        idle = sum(s["seconds"] for s in idle_samples if s["cpuPercent"] < rules["idleCpuPercent"]) * 100 / sum(s["seconds"] for s in idle_samples) if idle_samples else None
        utilization = {**row, "cpuPercent": cpu, "cpuP95Percent": percentile(cpus), "peakCpuPercent": max(cpus) if cpus else None,
                       "memoryPercent": memory, "cpuWaitPercent": mean("cpuWaitPercent"), "idlePercent": idle,
                       "samples": len(samples), "cpuSamples": len(cpus), "status": category,
                       "detail": {"method": "Node-duration weighted means; nearest-rank p95; coverage denominator unknown.",
                                  "limitations": "Missing or out-of-range percentages are unavailable, not zero.",
                                  "driverSamples": sum(s["role"] == "driver" for s in series), "series": series}}
        rows["utilization"].append(utilization)
        network = {**row, "receivedMiB": sum(s["receivedMiB"] for s in series if s["receivedMiB"] is not None) if any(s["receivedMiB"] is not None for s in series) else None,
                   "sentMiB": sum(s["sentMiB"] for s in series if s["sentMiB"] is not None) if any(s["sentMiB"] is not None for s in series) else None,
                   "cpuWaitPercent": mean("cpuWaitPercent"), "samples": len(samples), "status": "Observed node traffic" if samples else "No telemetry",
                   "detail": {"limitations": "Not billed Azure egress. Interval byte totals include boundary intervals; no proportional byte estimates.",
                              "series": [{**s, "receivedMiBPerSecond": s["receivedMiB"] / s["intervalSeconds"] if s["receivedMiB"] is not None else None} for s in series]}}
        rows["network"].append(network)
        autoscale = mapping(cluster.get("autoscale"), "autoscale")
        sizing = {**row, "minWorkers": autoscale.get("min_workers", cluster.get("num_workers")),
                  "maxWorkers": autoscale.get("max_workers", cluster.get("num_workers")),
                  "nodeType": cluster.get("node_type_id"), "singleNode": cluster.get("num_workers") == 0,
                  "status": "Benchmark candidate" if adequate and memory_adequate and cpu < rules["idleCpuPercent"] and memory is not None and memory < rules["highMemoryPercent"] else "No supported resize recommendation",
                  "detail": {"cpuPercent": cpu, "memoryPercent": memory, "samples": len(samples),
                             "nextStep": "Validate peak concurrency, memory, workload SLA and a reversible benchmark. No resize quantity or savings is inferred."}}
        rows["sizing"].append(sizing)
        if sizing["status"] == "Benchmark candidate":
            finding("sizing", sizing, "Validate low-utilization compute", "Collected CPU and memory are below configured review thresholds.", "Record an SLA-aware sizing benchmark; do not resize from averages alone.")

    for value in values("query"):
        started = timestamp(value.get("start_time"))
        if started is None:
            limitations.append("A query without a valid start time was excluded; it cannot be placed in the analysis window.")
            continue
        if (start is not None and started < start) or (end is not None and started >= end):
            continue
        row = base(value, value.get("statement_id", value.get("query_id", digest(value))))
        duration = number(value.get("total_duration_ms", value.get("duration_ms")))
        queue = number(value.get("waiting_at_capacity_duration_ms"))
        compute = mapping(value.get("compute"), "query compute")
        row.update(warehouseId=value.get("warehouse_id") or compute.get("warehouse_id"),
                   status=value.get("execution_status", value.get("status", "Unknown")), start=value.get("start_time"),
                   durationSeconds=duration / 1000 if duration is not None else None,
                   queueSeconds=queue / 1000 if queue is not None else None,
                   user=value.get("executed_by"), detail={"queryText": value.get("statement_text"),
                   "failure": value.get("error_message"), "spillBytes": value.get("spilled_local_bytes"),
                   "cost": "Not allocated; DBUs are not currency."})
        rows["queries"].append(row)
    warehouses: dict[tuple[str, str], list] = defaultdict(list)
    for query in rows["queries"]:
        warehouses[query["workspaceId"], str(query.get("warehouseId") or "Unattributed")].append(query)
    for (ws, warehouse), queries in warehouses.items():
        durations = [q["durationSeconds"] for q in queries if q["durationSeconds"] is not None]
        p95 = percentile(durations)
        if p95 is not None and p95 > rules["slowQuerySeconds"]:
            row = {**queries[0], "key": digest([ws, warehouse]), "name": warehouse, "durationP95Seconds": p95}
            finding("queries", row, "Review slow warehouse queries", f"Collected duration p95 exceeds {rules['slowQuerySeconds']} seconds.", "Inspect queue versus execution time and benchmark changes. No per-query monetary allocation is inferred.")
    for value in values("job"):
        identity = str(value.get("job_id"))
        settings = mapping(value.get("settings") or value, "job settings")
        tasks = settings.get("tasks") or []
        if isinstance(tasks, dict):
            tasks = [tasks]
        if not isinstance(tasks, list) or any(not isinstance(task, dict) for task in tasks):
            raise ValueError("Job tasks must contain a task object or an array of task objects.")
        def failure_alert(obj: dict) -> bool | None:
            email = obj.get("email_notifications")
            webhook = mapping(obj.get("webhook_notifications"), "webhook notifications")
            if isinstance(email, str) and not email.lstrip().startswith("{"):
                limitations.append("Legacy redacted email notification objects cannot prove failure routing; unknown is not unconfigured.")
                return True if webhook.get("on_failure") else None
            return bool(mapping(email, "email notifications").get("on_failure") or webhook.get("on_failure"))
        job_alert, task_alerts = failure_alert(settings), [failure_alert(t) for t in tasks]
        alert = True if job_alert is True or (tasks and all(a is True for a in task_alerts)) else None if job_alert is None or None in task_alerts else False
        runs = [r for r in values("job_run") if r["_ws"] == value["_ws"] and str(r.get("job_id")) == identity]
        runs = [r for r in runs if timestamp(r.get("start_time")) is not None and
                (start is None or timestamp(r["start_time"]) >= start) and (end is None or timestamp(r["start_time"]) < end)]
        failures = sum(str((r.get("state") or {}).get("result_state", "")).upper() in ("FAILED", "TIMEDOUT", "INTERNAL_ERROR") for r in runs)
        row = {**base(value, identity, settings.get("name")), "runs": len(runs), "failedRuns": failures,
               "failureAlerts": "Unknown" if alert is None else "Configured" if alert else "Not observed", "tasks": len(tasks),
               "retryPolicy": "Review task policies" if tasks else str(settings.get("max_retries", "Unknown")),
               "status": "Unknown failure routing" if alert is None else "Review failure routing" if failures and not alert else "Observed configuration",
               "detail": {"tasks": tasks, "runs": runs, "notifications": settings.get("email_notifications"),
                          "webhooks": settings.get("webhook_notifications"),
                          "limitation": "Task pagination and inherited routing must be verified; zero runs is not a health guarantee."}}
        rows["jobs"].append(row)
        if failures and alert is False:
            finding("jobs", row, "Verify failure notifications", "Failed runs were collected without complete observed failure notification coverage.", "Verify job/task email and webhook routing; document intentional retry policy.")
        if runs and failures * 100 / len(runs) >= rules["failureRatePercent"]:
            finding("jobs", row, "Review failed job runs", "Observed failure rate exceeds the configured review threshold.", "Inspect run errors and SLA context before proposing retry or compute changes.")

    controls = [("workspace_settings", "enableIpAccessLists", "NET-001", "Network", True),
                ("metastore", "metastore_id", "GOV-001", "Governance", None)]
    for ws, workspace in workspaces.items():
        for entity, field, control, category, expected in controls:
            evidence = [v for v in values(entity) if v["_ws"] == ws]
            observed = evidence[0].get(field) if evidence else None
            passed = bool(observed) if expected is None else str(observed).lower() == "true"
            outcome = "Unknown" if observed is None else "Pass" if passed else "Fail"
            row = {**base({"_ws": ws, "_source": f"normalized/{entity}.ndjson"}, control, field),
                   "category": category, "status": outcome, "observed": observed, "severity": "Review",
                   "detail": {"applicability": "Azure workspace configuration; posture review, not compliance certification.",
                              "expected": "Enabled" if expected else "Unity Catalog metastore assigned"}}
            rows["posture"].append(row)
            if outcome == "Fail":
                finding("posture", row, f"Review {field}", "Observed workspace setting differs from the review baseline.", "Validate applicability and an approved exception or remediation; no grants are applied.")
    for asset_type in ASSETS:
        for value in values(asset_type):
            identity = value.get("id") or value.get("volume_id") or value.get("experiment_id") or value.get("space_id") or value.get("path") or value.get("name") or digest(value)
            rows["assets"].append({**base(value, f"{asset_type}:{identity}", value.get("name") or value.get("path")),
                                   "assetType": asset_type, "status": "Inventory only", "detail": {k: v for k, v in value.items() if not k.startswith("_")}})
    for value in values("commitment_demand"):
        rows["commitments"].append({**base(value, digest([value.get(k) for k in ("region", "sku", "currency", "hour")]), value.get("sku")), **{k: value.get(k) for k in
            ("region", "sku", "currency", "hour", "eligibleNodes", "coveredNodes", "onDemandHourlyRate", "commitmentHourlyRate")},
            "status": "Scenario input; validate financial eligibility"})
    for module in MODULES:
        if module not in options["modules"]:
            rows[module] = []
    findings = [f for f in findings if f["domain"] in options["modules"]]
    def coverage(module, data):
        available = bool(data)
        if module == "posture":
            available = any(row["status"] != "Unknown" for row in data)
        elif module in ("utilization", "network"):
            available = any(row.get(field) is not None for row in data for field in
                            (("cpuPercent", "memoryPercent") if module == "utilization" else ("receivedMiB", "sentMiB")))
        return {"rows": len(data), "status": "not selected" if module not in options["modules"] else
                "collected samples" if available else "unavailable", "completeWindow": False}
    return {"schemaVersion": VERSION, "origin": config.get("evidenceOrigin", "native"), "ruleVersion": digest(rules),
            "options": options, "analysisWindow": {"startUtc": window.get("startUtc"), "endUtc": window.get("endUtc")},
            "datasets": rows, "findings": findings, "limitations": list(dict.fromkeys(limitations)),
            "sources": sources or [], "coverage": {name: coverage(name, data) for name, data in rows.items()},
            "workspaceCoverage": [{"workspaceId": ws, "workspaceName": w.get("name", ws),
                "modules": {name: coverage(name, [row for row in data if row["workspaceId"] == ws]) for name, data in rows.items()}}
                for ws, w in workspaces.items()]}


def write_analysis(run_root: Path, datasets: dict, config: dict) -> dict:
    sources_path = run_root / "collection-status.json"
    sources = json.loads(sources_path.read_text(encoding="utf-8-sig")) if sources_path.exists() else []
    result = analyze(datasets, config, sources)
    (run_root / "capability-analysis.json").write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    return result


def commitment_scenario(rows: list[dict], quantity: Any) -> dict:
    q = number(quantity)
    if q is None or q < 1 or not q.is_integer():
        raise ValueError("Quantity must be a positive integer.")
    if not rows:
        raise ValueError("Hourly eligible demand, existing coverage and both hourly prices are required.")
    identities = {(r.get("region"), r.get("sku"), r.get("currency")) for r in rows}
    if len(identities) != 1 or any(not x for x in next(iter(identities))):
        raise ValueError("A scenario must contain one explicit region, eligible SKU and currency.")
    hours = set()
    baseline = proposed = covered = 0.0
    for row in rows:
        hour = timestamp(row.get("hour"))
        nums = [number(row.get(k)) for k in ("eligibleNodes", "coveredNodes", "onDemandHourlyRate", "commitmentHourlyRate")]
        if hour is None or hour in hours or any(n is None or n < 0 for n in nums):
            raise ValueError("Every hour must be unique with nonnegative demand, coverage and prices.")
        hours.add(hour)
        demand, existing, ondemand, committed = nums
        if existing > demand:
            raise ValueError("Existing coverage exceeds eligible demand.")
        uncovered = demand - existing
        used = min(q, uncovered)
        baseline += uncovered * ondemand
        proposed += q * committed + max(0, uncovered - q) * ondemand
        covered += used
    return {"quantity": int(q), "hours": len(hours), "currency": next(iter(identities))[2],
            "baselineUncoveredCost": baseline, "scenarioCost": proposed, "estimatedDifference": baseline - proposed,
            "benefitUtilizationPercent": covered / (q * len(hours)) * 100,
            "limitations": "Saved sampled hours only; not extrapolated to a term. Eligibility, discount terms and taxes require financial approval. No purchase is made."}
