"""Dependency-free normalization, correlation, quality, and cost modeling."""

from __future__ import annotations

import json
import math
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

MODEL_VERSION = "1.0"

DATASET_MAP = {
    "resource-inventory": "azure_resource",
    "managed-resource-inventory": "azure_resource",
    "databricks-workspaces": "workspace",
    "workspace-inventory": "workspace",
    "account-workspaces": "workspace",
    "tags-ownership-inputs": "owner",
    "cost-management": "azure_cost",
    "billing-usage": "databricks_usage",
    "billing-list-prices": "list_price",
    "clusters": "compute",
    "cluster-events": "compute_event",
    "node-timeline": "node_timeline",
    "instance-pools": "pool",
    "jobs": "job",
    "system-jobs": "job",
    "job-runs": "job_run",
    "job-run-timeline": "job_run",
    "pipelines": "pipeline",
    "pipeline-details": "pipeline",
    "sql-warehouses": "warehouse",
    "query-history": "query",
    "uc-tables": "table",
    "table-metadata": "table",
    "table-detail": "table_file_summary",
    "table-history": "table_operation",
    "cluster-policies": "policy",
    "governance-compute-policies": "policy",
    "account-budgets": "budget",
    "budgets-commitments": "budget",
    "policy-inventory": "policy",
    "workspace-settings": "workspace_settings",
    "metastore-assignment": "metastore",
    "repos": "repos",
    "notebooks": "notebooks",
    "experiments": "experiments",
    "serving-endpoints": "serving-endpoints",
    "sql-alerts": "sql-alerts",
    "genie-spaces": "genie-spaces",
    "uc-volumes": "uc-volumes",
    "commitment-demand": "commitment_demand",
}

ID_FIELDS = {
    "azure_resource": ("id", "resourceId"),
    "workspace": ("workspace_id", "workspaceId", "id", "workspace_url", "workspaceUrl"),
    "azure_cost": ("ResourceId", "resourceId", "id"),
    "databricks_usage": ("record_id", "usage_id", "workspace_id"),
    "list_price": ("sku_name", "skuName"),
    "compute": ("cluster_id", "clusterId"),
    "compute_event": ("cluster_id", "clusterId"),
    "node_timeline": ("instance_id", "cluster_id"),
    "pool": ("instance_pool_id", "pool_id"),
    "job": ("job_id", "jobId"),
    "job_run": ("run_id", "runId"),
    "pipeline": ("pipeline_id", "pipelineId"),
    "warehouse": ("id", "warehouse_id"),
    "query": ("statement_id", "query_id"),
    "table": ("table_id", "full_name"),
    "policy": ("policy_id", "id"),
    "budget": ("budget_id", "id"),
    "owner": ("resourceId", "resource_id"),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _get(record: dict[str, Any], *names: str, default: Any = None) -> Any:
    lowered = {str(key).lower(): value for key, value in record.items()}
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


def canonical_azure_id(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().rstrip("/").lower().replace("\\", "/")
    return normalized or None


def read_records(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Read JSON arrays/objects or NDJSON, retaining valid rows after line errors."""
    errors: list[dict[str, Any]] = []
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        return [], [{"source": str(path), "message": str(exc), "kind": "read_error"}]
    if not text.strip():
        return [], []
    try:
        value = json.loads(text)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)], []
        if isinstance(value, dict):
            for key in ("value", "items", "rows"):
                if isinstance(value.get(key), list):
                    return [item for item in value[key] if isinstance(item, dict)], []
            return [value], []
        return [], [{"source": str(path), "message": "JSON root is not an object or array", "kind": "shape_error"}]
    except json.JSONDecodeError:
        records: list[dict[str, Any]] = []
        for line_number, line in enumerate(text.splitlines(), 1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
                if isinstance(item, dict):
                    records.append(item)
                else:
                    errors.append({
                        "source": str(path), "line": line_number,
                        "message": "NDJSON row is not an object", "kind": "shape_error",
                    })
            except json.JSONDecodeError as exc:
                errors.append({
                    "source": str(path), "line": line_number,
                    "message": str(exc), "kind": "parse_error",
                })
        return records, errors


def _dataset_name(path: Path) -> str:
    name = path.name.lower()
    for suffix in (".ndjson", ".json"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
    match = re.fullmatch(r"(table-detail|table-history)-[0-9a-f]{16}", name)
    if match:
        return match.group(1)
    return name


def _workspace_hint(path: Path, run_root: Path) -> str | None:
    try:
        relative = path.relative_to(run_root / "raw" / "databricks")
        return relative.parts[0] if len(relative.parts) > 1 else None
    except ValueError:
        return None


def _source_id(entity: str, record: dict[str, Any], ordinal: int) -> str:
    for field in ID_FIELDS.get(entity, ()):
        value = _get(record, field)
        if value not in (None, ""):
            return str(value)
    return f"row:{ordinal}"


def normalize_record(
    entity: str,
    record: dict[str, Any],
    *,
    ordinal: int,
    path: Path,
    run_root: Path,
    config: dict[str, Any],
    manifest: dict[str, Any],
) -> dict[str, Any]:
    source_system = "azure" if "azure" in [part.lower() for part in path.parts] else "databricks"
    extracted = _get(record, "extractedAtUtc", "extracted_at_utc", "timestamp")
    if not extracted:
        extracted = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat().replace("+00:00", "Z")
    source_identifier = _source_id(entity, record, ordinal)
    workspace_hint = _workspace_hint(path, run_root)
    normalized = dict(record)
    if entity in ("azure_resource", "azure_cost", "owner"):
        resource_id = _get(record, "id", "ResourceId", "resourceId", "resource_id")
        normalized["canonicalResourceId"] = canonical_azure_id(resource_id)
    if workspace_hint and not _get(normalized, "workspace_id", "workspaceId"):
        normalized["workspaceKey"] = workspace_hint
    return {
        "schemaVersion": MODEL_VERSION,
        "entityType": entity,
        "assessmentRunId": manifest.get("runId") or config.get("assessmentId"),
        "sourceSystem": source_system,
        "sourceIdentifier": source_identifier,
        "sourceExtractionTimestamp": extracted,
        "effectiveStartUtc": _get(
            record, "usage_start_time", "start_time", "windowStartUtc", "price_start_time"
        ),
        "effectiveEndUtc": _get(
            record, "usage_end_time", "end_time", "windowEndUtc", "price_end_time"
        ),
        "customerScope": {
            "customerId": config.get("customerId"),
            "assessmentId": config.get("assessmentId"),
            "workspaceKey": workspace_hint,
        },
        "collectionStatus": "passed",
        "qualityFlags": [],
        "sensitivityClassification": "customer-approved-metadata",
        "normalized": normalized,
        "provenance": {
            "sourceFile": str(path.relative_to(run_root)),
            "sourceRecordOrdinal": ordinal,
            "raw": record,
        },
    }


def build_normalized_model(
    run_root: Path, config: dict[str, Any], manifest: dict[str, Any]
) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]], dict[str, dict[str, Any]]]:
    datasets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    errors: list[dict[str, Any]] = []
    inventory: dict[str, dict[str, Any]] = {}
    raw_root = run_root / "raw"
    if not raw_root.exists():
        errors.append({"source": str(raw_root), "kind": "missing_source", "message": "Raw input directory does not exist"})
        return dict(datasets), errors, inventory
    for path in sorted(raw_root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in (".json", ".ndjson"):
            continue
        name = _dataset_name(path)
        records, file_errors = read_records(path)
        errors.extend(file_errors)
        if name == "budgets-commitments":
            budgets = []
            for record in records:
                values = record.get("budgets")
                if not isinstance(values, list) or not all(isinstance(value, dict) for value in values):
                    errors.append({"source": str(path), "kind": "shape_error", "message": "Azure financial inventory requires a budgets array of objects."})
                    continue
                budgets.extend(values)
            records = budgets
        inventory[str(path.relative_to(run_root))] = {
            "recordCount": len(records),
            "parseErrorCount": len(file_errors),
            "mappedEntity": DATASET_MAP.get(name),
            "reportedStatuses": [
                str(_get(record, "status")).lower()
                for record in records
                if _get(record, "status")
            ] if name.endswith("source-status") else [],
        }
        entity = DATASET_MAP.get(name)
        if not entity or name.endswith("source-status"):
            continue
        for ordinal, record in enumerate(records, 1):
            datasets[entity].append(normalize_record(
                entity, record, ordinal=ordinal, path=path, run_root=run_root,
                config=config, manifest=manifest,
            ))
    return dict(datasets), errors, inventory


def _norm_value(item: dict[str, Any], *names: str, default: Any = None) -> Any:
    return _get(item.get("normalized", {}), *names, default=default)


def _resource_group_id(value: Any) -> str | None:
    resource_id = canonical_azure_id(value)
    match = re.match(r"^(/subscriptions/[^/]+/resourcegroups/[^/]+)(?:/|$)", resource_id or "")
    return match.group(1) if match else None


def _record_group_id(record: dict[str, Any]) -> str | None:
    group_id = _resource_group_id(_get(
        record, "canonicalResourceId", "workspaceResourceId", "resourceId", "resource_id", "id"
    ))
    if group_id:
        return group_id
    subscription = _get(record, "subscriptionId", "subscription_id")
    group = _get(record, "resourceGroup", "resource_group")
    if subscription and group:
        return canonical_azure_id(f"/subscriptions/{subscription}/resourceGroups/{group}")
    return None


def filter_databricks_scope(
    datasets: dict[str, list[dict[str, Any]]],
    config: dict[str, Any],
) -> dict[str, Any]:
    """Keep Azure resources and costs attributable to selected Databricks workspaces.

    The selected resource groups plus every selected workspace managed resource group
    form the Azure Databricks cost boundary. Excluded subscription cost remains
    countable in the audit output but is not used in reconciliation or reports.
    """
    azure_config = config.get("azure", {})
    databricks_config = config.get("databricks", {})
    subscriptions = {str(value).lower() for value in azure_config.get("subscriptions", [])}
    qualified_scope = "resourceGroupIds" in azure_config
    selected_group_ids: set[str] = set()
    legacy_groups: set[str] = set()
    if qualified_scope:
        for value in azure_config["resourceGroupIds"]:
            group_id = _resource_group_id(value)
            if not group_id or group_id != canonical_azure_id(value):
                raise ValueError(f"Invalid Azure resource group ID: {value!r}")
            if subscriptions and group_id.split("/")[2] not in subscriptions:
                raise ValueError(f"Resource group is outside the selected subscriptions: {value!r}")
            selected_group_ids.add(group_id)
    else:
        names = {str(value).lower() for value in azure_config.get("resourceGroups", []) if value}
        if subscriptions:
            selected_group_ids = {
                f"/subscriptions/{subscription}/resourcegroups/{name}"
                for subscription in subscriptions for name in names
            }
        else:
            legacy_groups = names
    allowed_group_ids = set(selected_group_ids)
    allowed_legacy_groups = set(legacy_groups)
    configured_workspaces = databricks_config.get("workspaces", [])
    selected_workspaces = [value for value in configured_workspaces if value.get("include", True)]

    def in_declared_scope(record: dict[str, Any]) -> bool:
        group_id = _record_group_id(record)
        if group_id:
            if subscriptions and group_id.split("/")[2] not in subscriptions:
                return False
            if selected_group_ids:
                return group_id in selected_group_ids
            if legacy_groups:
                return group_id.split("/")[-1] in legacy_groups
            return True
        group = str(_get(record, "resourceGroup", "resource_group", default="")).lower()
        return bool(not qualified_scope and not subscriptions and group
                    and (not legacy_groups or group in legacy_groups))

    def matches_workspace(record: dict[str, Any], selected: dict[str, Any]) -> bool:
        record_arm_id = canonical_azure_id(_get(record, "workspaceResourceId", "resourceId", "resource_id", "id"))
        selected_arm_id = canonical_azure_id(_get(selected, "workspaceResourceId", "resourceId"))
        if selected_arm_id and record_arm_id and record_arm_id.startswith("/subscriptions/"):
            return record_arm_id == selected_arm_id
        properties = _get(record, "properties", default={})
        for keys in (("workspaceId", "workspace_id"), ("workspaceUrl", "workspace_url")):
            actual = _get(record, *keys)
            if not actual and isinstance(properties, dict):
                actual = _get(properties, *keys)
            expected = _get(selected, *keys)
            if actual and expected:
                return str(actual).rstrip("/").lower() == str(expected).rstrip("/").lower()
        actual_group = _record_group_id(record)
        expected_group = _record_group_id(selected)
        if expected_group and actual_group != expected_group:
            return False
        name = str(_get(record, "name", "workspaceName", "workspace_name", default="")).lower()
        if not name or name != str(selected.get("name", "")).lower():
            return False
        expected_subscription = str(selected.get("subscriptionId", "")).lower()
        if expected_subscription and (not actual_group or actual_group.split("/")[2] != expected_subscription):
            return False
        expected_name = str(selected.get("resourceGroup", "")).lower()
        actual_name = actual_group.split("/")[-1] if actual_group else str(
            _get(record, "resourceGroup", "resource_group", default="")
        ).lower()
        return not expected_name or actual_name == expected_name

    def add_workspace_group(record: dict[str, Any]) -> None:
        group_id = _record_group_id(record)
        if group_id:
            allowed_group_ids.add(group_id)
        elif not qualified_scope and not subscriptions:
            group = _get(record, "resourceGroup", "resource_group")
            if group:
                allowed_legacy_groups.add(str(group).lower())

    for workspace in selected_workspaces:
        if in_declared_scope(workspace):
            add_workspace_group(workspace)
    original_workspaces = datasets.get("workspace", [])
    included_workspaces = []
    for workspace in original_workspaces:
        record = workspace.get("normalized", {})
        matches = [selected for selected in selected_workspaces if matches_workspace(record, selected)]
        if "workspaces" in databricks_config and not matches:
            continue
        # API workspace records may omit ARM identity; only an unambiguous configured match can supply it.
        scoped_record = {**matches[0], **record} if len(matches) == 1 else record
        if not in_declared_scope(scoped_record):
            continue
        included_workspaces.append(workspace)
        add_workspace_group(scoped_record)
        properties = _get(record, "properties", default={})
        if isinstance(properties, dict):
            managed_id = _resource_group_id(_get(properties, "managedResourceGroupId", "managed_resource_group_id"))
            if managed_id and (not subscriptions or managed_id.split("/")[2] in subscriptions):
                allowed_group_ids.add(managed_id)
    datasets["workspace"] = included_workspaces

    def in_allowed_group(item: dict[str, Any]) -> bool:
        normalized = item.get("normalized", {})
        group_id = _record_group_id(normalized)
        if group_id:
            if subscriptions and group_id.split("/")[2] not in subscriptions:
                return False
            return group_id in allowed_group_ids or group_id.split("/")[-1] in allowed_legacy_groups
        group = str(_get(normalized, "resourceGroup", "resource_group", default="")).lower()
        return group in allowed_legacy_groups

    result = {
        "schemaVersion": MODEL_VERSION,
        "allowedResourceGroupIds": sorted(allowed_group_ids),
        "allowedResourceGroups": sorted(allowed_legacy_groups | {value.split("/")[-1] for value in allowed_group_ids}),
        "limitations": [] if allowed_group_ids or allowed_legacy_groups else [
            "No selected resource groups or in-scope Databricks workspace inventory were available; Azure resources and costs were excluded."
        ],
        "entities": {
            "workspace": {
                "inputRecords": len(original_workspaces),
                "includedRecords": len(included_workspaces),
                "excludedRecords": len(original_workspaces) - len(included_workspaces),
            },
        },
    }
    for entity in ("azure_resource", "azure_cost", "owner"):
        original = datasets.get(entity, [])
        included = [item for item in original if in_allowed_group(item)]
        if entity in ("azure_resource", "owner"):
            deduplicated: dict[str, dict[str, Any]] = {}
            anonymous: list[dict[str, Any]] = []
            for item in included:
                resource_id = _norm_value(item, "canonicalResourceId")
                if resource_id:
                    deduplicated.setdefault(resource_id, item)
                else:
                    anonymous.append(item)
            included = list(deduplicated.values()) + anonymous
        datasets[entity] = included
        result["entities"][entity] = {
            "inputRecords": len(original),
            "includedRecords": len(included),
            "excludedRecords": len(original) - len(included),
        }
    return result


def correlate_model(datasets: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    resources = datasets.get("azure_resource", [])
    resource_ids = {
        _norm_value(item, "canonicalResourceId"): item
        for item in resources if _norm_value(item, "canonicalResourceId")
    }
    azure_workspaces = [
        item for item in resources
        if str(_norm_value(item, "type", default="")).lower() == "microsoft.databricks/workspaces"
    ]
    workspace_matches: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []
    for workspace in datasets.get("workspace", []):
        value = workspace["normalized"]
        workspace_id = str(_get(value, "workspace_id", "workspaceId", default="")).lower()
        workspace_name = str(_get(value, "workspace_name", "workspaceName", "name", default="")).lower()
        resource_group = str(_get(value, "resource_group", "resourceGroup", default="")).lower()
        matches = []
        for azure_workspace in azure_workspaces:
            az = azure_workspace["normalized"]
            if workspace_name and workspace_name == str(_get(az, "name", default="")).lower():
                if not resource_group or resource_group == str(_get(az, "resourceGroup", default="")).lower():
                    matches.append(azure_workspace)
        if len(matches) == 1:
            workspace["correlation"] = {
                "status": "matched", "rule": "workspace-name-resource-group",
                "azureResourceId": _norm_value(matches[0], "canonicalResourceId"),
            }
            workspace_matches.append({
                "workspaceId": workspace_id or workspace["sourceIdentifier"],
                "azureResourceId": _norm_value(matches[0], "canonicalResourceId"),
                "rule": "workspace-name-resource-group",
            })
        else:
            status = "ambiguous" if len(matches) > 1 else "unmatched"
            workspace["correlation"] = {"status": status, "rule": "workspace-name-resource-group"}
            unmatched.append({"entity": "workspace", "sourceIdentifier": workspace["sourceIdentifier"], "status": status})
    cost_matches = 0
    for cost in datasets.get("azure_cost", []):
        resource_id = _norm_value(cost, "canonicalResourceId")
        if resource_id and resource_id in resource_ids:
            cost["correlation"] = {"status": "matched", "rule": "canonical-resource-id", "resourceId": resource_id}
            cost_matches += 1
        else:
            cost["correlation"] = {"status": "unmatched", "rule": "canonical-resource-id"}
    return {
        "schemaVersion": MODEL_VERSION,
        "rulesVersion": "1.0",
        "workspaceMatches": workspace_matches,
        "matchedAzureCostRecords": cost_matches,
        "unmatched": unmatched,
    }


def confidence_from_metrics(metrics: dict[str, float], required: Iterable[str] = ()) -> dict[str, Any]:
    missing = [name for name in required if metrics.get(name, 0.0) <= 0.0]
    bounded = {name: max(0.0, min(1.0, float(value))) for name, value in metrics.items()}
    score = sum(bounded.values()) / len(bounded) if bounded else 0.0
    if missing:
        level = "insufficient"
    elif score >= 0.85:
        level = "high"
    elif score >= 0.65:
        level = "medium"
    elif score >= 0.40:
        level = "low"
    else:
        level = "insufficient"
    return {"score": round(score, 4), "level": level, "missingRequiredMetrics": missing, "metrics": bounded}


def telemetry_quality(
    inventory: dict[str, dict[str, Any]], datasets: dict[str, list[dict[str, Any]]]
) -> dict[str, Any]:
    sources = []
    for source, details in inventory.items():
        count = details["recordCount"]
        parse_errors = details["parseErrorCount"]
        reported_statuses = details.get("reportedStatuses", [])
        failed_count = sum(status in ("failed", "pending telemetry") for status in reported_statuses)
        partial_count = sum(status == "partial" for status in reported_statuses)
        assessed_count = sum(status != "skipped" for status in reported_statuses)
        collection_success = (
            max(0.0, 1.0 - (failed_count + partial_count * 0.5) / max(1, assessed_count))
            if reported_statuses else 1.0
        )
        completeness = 1.0 if count and not parse_errors else (0.5 if count else 0.0)
        consistency = 1.0 if not parse_errors else max(0.0, 1.0 - parse_errors / max(1, count + parse_errors))
        metrics = {
            "coverage": 1.0 if count else 0.0,
            "freshness": 1.0,
            "completeness": completeness,
            "consistency": consistency,
            "attributionQuality": 0.7 if count else 0.0,
            "sampleAdequacy": 1.0 if count >= 3 else (0.5 if count else 0.0),
            "sourceAuthority": 1.0,
            "collectionSuccess": collection_success,
        }
        sources.append({"source": source, **confidence_from_metrics(metrics, ("coverage", "completeness"))})
    reported_statuses = [
        status
        for details in inventory.values()
        for status in details.get("reportedStatuses", [])
        if status != "skipped"
    ]
    failed_count = sum(status in ("failed", "pending telemetry") for status in reported_statuses)
    partial_count = sum(status == "partial" for status in reported_statuses)
    collection_success = (
        max(0.0, 1.0 - (failed_count + partial_count * 0.5) / len(reported_statuses))
        if reported_statuses else 1.0
    )
    entity_coverage = min(1.0, len(datasets) / max(1, len(set(DATASET_MAP.values()))))
    overall_metrics = {
        "coverage": entity_coverage,
        "freshness": 1.0 if inventory else 0.0,
        "completeness": entity_coverage,
        "consistency": 1.0 if not any(value["parseErrorCount"] for value in inventory.values()) else 0.7,
        "attributionQuality": 1.0 if datasets.get("owner") else 0.3,
        "sampleAdequacy": 1.0 if sum(len(value) for value in datasets.values()) >= 10 else 0.5,
        "sourceAuthority": 1.0 if inventory else 0.0,
        "collectionSuccess": collection_success,
    }
    return {
        "schemaVersion": MODEL_VERSION,
        "generatedAtUtc": _utc_now(),
        "overall": confidence_from_metrics(overall_metrics),
        "sources": sources,
    }


def _is_serverless(record: dict[str, Any]) -> bool:
    searchable = json.dumps(record, sort_keys=True, default=str).lower()
    explicit = _get(record, "isServerless", "is_serverless", "serverless")
    explicitly_true = explicit is True or str(explicit).strip().lower() in ("true", "1", "yes")
    return explicitly_true or "serverless" in searchable


def _is_infrastructure_cost(record: dict[str, Any]) -> bool:
    text = " ".join(str(_get(record, name, default="")) for name in ("ServiceName", "Meter", "Product", "ResourceType")).lower()
    return any(token in text for token in ("virtual machine", "compute", "disk", "network", "bandwidth"))


def _is_databricks_service_cost(record: dict[str, Any]) -> bool:
    text = " ".join(str(_get(record, name, default="")) for name in ("ServiceName", "Meter", "Product")).lower()
    return "databricks" in text or "dbu" in text


def _list_price_amount(price: dict[str, Any]) -> float | None:
    value = _get(price, "pricing", "price", "list_price", "listPrice")
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return _number(value)
    if isinstance(value, dict):
        value = _get(value, "effective_list", "default", "value")
        if isinstance(value, dict):
            value = _get(value, "default", "value")
    return _number(value)


def _timestamp(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _effective_price(prices: list[dict[str, Any]], usage: dict[str, Any]) -> dict[str, Any] | None:
    usage_time = _timestamp(_get(usage, "usage_start_time", "usageStartTime"))
    if usage_time is None:
        return prices[0] if len(prices) == 1 else None
    applicable = []
    for price in prices:
        start = _timestamp(_get(price, "price_start_time", "priceStartTime"))
        end = _timestamp(_get(price, "price_end_time", "priceEndTime"))
        if (start is None or start <= usage_time) and (end is None or usage_time < end):
            applicable.append(price)
    if len(applicable) != 1:
        return None
    return applicable[0]


def reconcile_costs(
    datasets: dict[str, list[dict[str, Any]]], config: dict[str, Any]
) -> dict[str, Any]:
    totals: dict[str, float] = defaultdict(float)
    currencies: set[str] = set()
    unmatched_cost_by_basis: dict[str, float] = defaultdict(float)
    serverless_vm_excluded_by_basis: dict[str, float] = defaultdict(float)
    has_azure_dbu = False
    for item in datasets.get("azure_cost", []):
        row = item["normalized"]
        amount = _number(_get(row, "PreTaxCost", "Cost", "cost")) or 0.0
        basis = str(_get(row, "costBasis", default="ActualCost"))
        totals[basis] += amount
        currency = _get(row, "Currency", "currency")
        if currency:
            currencies.add(str(currency))
        if item.get("correlation", {}).get("status") != "matched":
            unmatched_cost_by_basis[basis] += amount
        has_azure_dbu = has_azure_dbu or _is_databricks_service_cost(row)
        if _is_serverless(row) and _is_infrastructure_cost(row) and not _is_databricks_service_cost(row):
            serverless_vm_excluded_by_basis[basis] += amount

    prices_by_sku: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in datasets.get("list_price", []):
        sku = str(_norm_value(item, "sku_name", "skuName", default="")).lower()
        if sku:
            prices_by_sku[sku].append(item["normalized"])
    dbu_total = 0.0
    unmatched_usage = 0
    serverless_dbu_total = 0.0
    for item in datasets.get("databricks_usage", []):
        usage = item["normalized"]
        quantity = _number(_get(usage, "usage_quantity", "usageQuantity"))
        sku = str(_get(usage, "sku_name", "skuName", default="")).lower()
        prices = prices_by_sku.get(sku, [])
        amount = None
        effective_price = _effective_price(prices, usage)
        if quantity is not None and effective_price:
            price = _list_price_amount(effective_price)
            if price is not None:
                amount = quantity * price
        if amount is None:
            unmatched_usage += 1
            continue
        dbu_total += amount
        if _is_serverless(usage):
            serverless_dbu_total += amount

    selected_basis = str(config.get("azure", {}).get("reportingCostBasis", "ActualCost"))
    if selected_basis not in totals and totals:
        selected_basis = "ActualCost" if "ActualCost" in totals else sorted(totals)[0]
    selected_total = totals.get(selected_basis, 0.0)
    unmatched_cost = unmatched_cost_by_basis.get(selected_basis, 0.0)
    serverless_vm_excluded = serverless_vm_excluded_by_basis.get(selected_basis, 0.0)
    additive_dbu = 0.0 if has_azure_dbu else dbu_total
    combined = selected_total - serverless_vm_excluded + additive_dbu
    tolerance = config.get("reconciliation", {}).get("tolerance", config.get("tolerance", {}))
    absolute_tolerance = _number(tolerance.get("absoluteCurrency")) or 10.0
    percent_tolerance = _number(tolerance.get("percent")) or 2.0
    variance = selected_total - combined
    variance_percent = abs(variance) / abs(selected_total) * 100 if selected_total else None
    within_tolerance = abs(variance) <= absolute_tolerance or (
        variance_percent is not None and variance_percent <= percent_tolerance
    )
    return {
        "schemaVersion": MODEL_VERSION,
        "reportingBasis": selected_basis,
        "currency": next(iter(currencies), config.get("azure", {}).get("currency")),
        "currencyAggregationAllowed": len(currencies) <= 1,
        "taxIncluded": None,
        "authoritativeTotals": {key: round(value, 6) for key, value in sorted(totals.items())},
        "authoritativeTotal": round(selected_total, 6),
        "collectedTotal": round(combined, 6),
        "databricksListPriceEstimate": round(dbu_total, 6),
        "databricksListPriceAddedToAzure": round(additive_dbu, 6),
        "matchedCost": round(selected_total - unmatched_cost - serverless_vm_excluded, 6),
        "unmatchedCost": round(unmatched_cost, 6),
        "allocatedSharedCost": 0.0,
        "excludedCost": round(serverless_vm_excluded, 6),
        "varianceAmount": round(variance, 6),
        "variancePercent": round(variance_percent, 6) if variance_percent is not None else None,
        "withinTolerance": within_tolerance,
        "duplicatePrevention": {
            "azureContainsDatabricksServiceCost": has_azure_dbu,
            "serverlessDbuCost": round(serverless_dbu_total, 6),
            "serverlessVmCostNotAdded": round(serverless_vm_excluded, 6),
            "rule": "Serverless DBU includes infrastructure; explicit serverless VM estimates are never additive.",
        },
        "unmatchedDatabricksUsageRecords": unmatched_usage,
        "limitations": (
            ["Multiple currencies detected; totals must not be aggregated without conversion."]
            if len(currencies) > 1 else []
        ) + ([f"{unmatched_usage} Databricks usage records could not be priced; the list-price estimate excludes them."] if unmatched_usage else []),
    }


def attribution_coverage(datasets: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    costs = datasets.get("azure_cost", [])
    total = sum((_number(_norm_value(item, "PreTaxCost", "Cost", "cost")) or 0.0) for item in costs)
    attributed_count = 0
    attributed_spend = 0.0
    keys = ("Owner", "Team", "BusinessUnit", "Project", "Environment", "CostCenter")
    for item in costs:
        row = item["normalized"]
        tags = _get(row, "tags", "Tags", default={})
        searchable = tags if isinstance(tags, dict) else {}
        attributed = any(_get(searchable, key) not in (None, "") for key in keys)
        if attributed:
            attributed_count += 1
            attributed_spend += _number(_get(row, "PreTaxCost", "Cost", "cost")) or 0.0
    return {
        "schemaVersion": MODEL_VERSION,
        "resourceCount": len(costs),
        "attributedResourceCount": attributed_count,
        "resourceCoveragePercent": round(attributed_count / len(costs) * 100, 4) if costs else 0.0,
        "totalSpend": round(total, 6),
        "attributedSpend": round(attributed_spend, 6),
        "spendCoveragePercent": round(attributed_spend / total * 100, 4) if total else 0.0,
    }
