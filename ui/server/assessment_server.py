from __future__ import annotations

import argparse
import csv
import json
import logging
import mimetypes
import os
import re
import shutil
import socket
import stat
import subprocess
import threading
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import quote, unquote, urlsplit

from permission_setup import DatabricksSetupClient, PermissionSetupService, SetupError, workspace_host


RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
TENANT_ID_PATTERN = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
COMPLETED_STATUSES = {"completed", "passed", "partial", "failed"}
TERMINAL_EVENT_TYPES = {"completed", "failed", "canceled"}
MAX_BODY_BYTES = 10 * 1024 * 1024
PROGRESS_PREFIX = "AssessmentProgress:"
ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


class ApiError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def read_json(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        if default is not None:
            return default
        raise ApiError(HTTPStatus.NOT_FOUND, f"Required artifact is missing: {path.name}")
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ApiError(HTTPStatus.INTERNAL_SERVER_ERROR, f"Cannot read {path.name}: {exc}") from exc


def read_ndjson(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    records: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8-sig") as stream:
            for line_number, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                try:
                    value = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ApiError(
                        HTTPStatus.INTERNAL_SERVER_ERROR,
                        f"Cannot read {path.name} line {line_number}: {exc}",
                    ) from exc
                if isinstance(value, dict):
                    records.append(value)
    except OSError as exc:
        raise ApiError(HTTPStatus.INTERNAL_SERVER_ERROR, f"Cannot read {path.name}: {exc}") from exc
    return records


def contained_path(root: Path, candidate: Path) -> Path:
    resolved_root = root.resolve()
    resolved_candidate = candidate.resolve()
    try:
        resolved_candidate.relative_to(resolved_root)
    except ValueError as exc:
        raise ApiError(HTTPStatus.BAD_REQUEST, "Path is outside the permitted root.") from exc
    return resolved_candidate


def resolve_run_root(output_root: Path, run_id: str, require_exists: bool = True) -> Path:
    if not RUN_ID_PATTERN.fullmatch(run_id):
        raise ApiError(HTTPStatus.BAD_REQUEST, "Invalid run id.")
    run_root = contained_path(output_root, output_root / run_id)
    if require_exists and not run_root.is_dir():
        raise ApiError(HTTPStatus.NOT_FOUND, f"Run not found: {run_id}")
    return run_root


def resolve_artifact(run_root: Path, relative_path: str) -> Path:
    decoded = unquote(relative_path)
    pure_path = PurePosixPath(decoded.replace("\\", "/"))
    if pure_path.is_absolute() or not pure_path.parts or any(part in {"", ".", ".."} for part in pure_path.parts):
        raise ApiError(HTTPStatus.BAD_REQUEST, "Invalid artifact path.")
    artifact = contained_path(run_root, run_root.joinpath(*pure_path.parts))
    if not artifact.is_file():
        raise ApiError(HTTPStatus.NOT_FOUND, "Artifact not found.")
    return artifact


def resolve_default_config(assessment_root: Path) -> Path:
    config_root = assessment_root / "config"
    for name in ("assessment-scope.local.json", "workshop-scope.json", "assessment-scope.example.json"):
        candidate = config_root / name
        if candidate.is_file():
            return candidate
    raise ApiError(HTTPStatus.NOT_FOUND, "No assessment scope configuration was found.")


def write_config(output_root: Path, config: dict[str, Any], purpose: str) -> Path:
    if not isinstance(config, dict):
        raise ApiError(HTTPStatus.BAD_REQUEST, "config must be a JSON object.")
    state_root = contained_path(output_root, output_root / ".ui-server" / "configs")
    state_root.mkdir(parents=True, exist_ok=True)
    path = contained_path(state_root, state_root / f"{purpose}-{uuid.uuid4().hex}.json")
    try:
        path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    except OSError as exc:
        raise ApiError(HTTPStatus.INTERNAL_SERVER_ERROR, f"Cannot write temporary config: {exc}") from exc
    return path


def build_assessment_arguments(
    powershell: str,
    script_path: Path,
    action: str,
    config_path: Path,
    output_root: Path,
    approvals: dict[str, Any],
) -> list[str]:
    if action not in {"Readiness", "Run"}:
        raise ValueError(f"Unsupported assessment action: {action}")
    arguments = [
        powershell,
        "-NoLogo",
        "-NoProfile",
        "-NonInteractive",
        "-File",
        str(script_path),
        "-Action",
        action,
        "-ConfigPath",
        str(config_path),
        "-OutputRoot",
        str(output_root),
    ]
    if bool(approvals.get("approveSqlWarehouseAutoStart")):
        arguments.append("-ApproveSqlWarehouseAutoStart")
    if action == "Run":
        if bool(approvals.get("continueOnCollectorError", True)):
            arguments.append("-ContinueOnCollectorError")
        else:
            arguments.append("-FailOnCollectorError")
        arguments.append("-NoOpenReport")
    return arguments


def run_command(
    arguments: list[str],
    cwd: Path,
    environment: dict[str, str] | None = None,
    timeout_seconds: int | None = None,
) -> subprocess.CompletedProcess[str]:
    executable = shutil.which(arguments[0]) or arguments[0]
    command: list[str]
    if os.name == "nt" and Path(executable).suffix.lower() in {".cmd", ".bat"}:
        command = [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", executable, *arguments[1:]]
    else:
        command = [executable, *arguments[1:]]
    try:
        return subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            env=environment,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise ApiError(HTTPStatus.GATEWAY_TIMEOUT, f"{arguments[0]} exceeded its {timeout_seconds}-second timeout. Check authentication and retry explicitly.") from exc
    except OSError as exc:
        raise ApiError(HTTPStatus.SERVICE_UNAVAILABLE, f"Cannot start {arguments[0]}: {exc}") from exc


def run_az(arguments: list[str], cwd: Path, *, timeout_seconds: int | None = None) -> Any:
    options = {"timeout_seconds": timeout_seconds} if timeout_seconds is not None else {}
    completed = run_command(["az", *arguments, "--only-show-errors", "--output", "json"], cwd, **options)
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "Azure CLI command failed."
        if "interactionrequired" in detail.lower() or "invalid_grant" in detail.lower():
            command = " ".join(arguments[:4])
            detail = (
                f"Azure CLI could not authenticate while running 'az {command}'. "
                "Run 'az login' in PowerShell, then retry discovery."
            )
        raise ApiError(HTTPStatus.BAD_GATEWAY, detail)
    try:
        return json.loads(completed.stdout or "null")
    except json.JSONDecodeError as exc:
        raise ApiError(HTTPStatus.BAD_GATEWAY, "Azure CLI returned invalid JSON.") from exc


def discover_estate(repository_root: Path) -> list[dict[str, Any]]:
    current_account = run_az(["account", "show"], repository_root) or {}
    current_tenant_id = str(current_account.get("tenantId", "")).lower()
    subscriptions = [
        subscription
        for subscription in run_az(["account", "list"], repository_root) or []
        if str(subscription.get("tenantId", "")).lower() == current_tenant_id
        and str(subscription.get("state", "")).lower() == "enabled"
    ]
    if not subscriptions:
        raise ApiError(
            HTTPStatus.NOT_FOUND,
            "No enabled subscriptions were found in the currently selected Azure tenant.",
        )
    result: list[dict[str, Any]] = []
    for subscription in subscriptions or []:
        subscription_id = str(subscription.get("id", ""))
        groups = run_az(["group", "list", "--subscription", subscription_id], repository_root)
        workspaces = run_az(
            ["databricks", "workspace", "list", "--subscription", subscription_id],
            repository_root,
        )
        workspaces_by_group: dict[str, list[dict[str, Any]]] = defaultdict(list)
        managed_group_ids: set[str] = set()
        for workspace in workspaces or []:
            resource_group = str(workspace.get("resourceGroup", ""))
            properties = workspace.get("workspaceProperties") or workspace.get("properties") or {}
            managed_group_id = str(
                workspace.get("managedResourceGroupId")
                or properties.get("managedResourceGroupId")
                or ""
            )
            if managed_group_id:
                managed_group_ids.add(managed_group_id.lower())
            parameters = properties.get("parameters") or {}
            workspace_id = (
                workspace.get("workspaceId")
                or properties.get("workspaceId")
                or workspace.get("id", "")
            )
            workspace_url = (
                workspace.get("workspaceUrl")
                or properties.get("workspaceUrl")
                or properties.get("workspace_url")
                or ""
            )
            sku = workspace.get("sku") or {}
            warehouse_error = None
            try:
                warehouses = discover_warehouses(str(workspace_url), repository_root)
            except (ApiError, SetupError) as exc:
                warehouse_error = f"SQL Warehouse discovery failed: {exc}"
                logging.warning("Warehouse discovery failed for workspace %s: %s", workspace_id, exc)
                warehouses = []
            workspaces_by_group[resource_group.lower()].append(
                {
                    "name": str(workspace.get("name", "")),
                    "workspaceId": str(workspace_id),
                    "workspaceUrl": str(workspace_url),
                    "resourceGroup": resource_group,
                    "subscriptionId": subscription_id,
                    "managedResourceGroup": managed_group_id.rsplit("/", 1)[-1] if managed_group_id else "",
                    "sku": str(sku.get("name", "") if isinstance(sku, dict) else sku),
                    "location": str(workspace.get("location", "")),
                    "sqlWarehouses": warehouses,
                    "warehouseDiscoveryError": warehouse_error,
                }
            )
        result.append(
            {
                "subscriptionId": subscription_id,
                "displayName": str(subscription.get("name", "")),
                "tenantId": str(subscription.get("tenantId", "")),
                "state": str(subscription.get("state", "")),
                "resourceGroups": [
                    {
                        "name": str(group.get("name", "")),
                        "resourceGroupId": str(group.get("id", "")),
                        "location": str(group.get("location", "")),
                        "subscriptionId": subscription_id,
                        "workspaces": workspaces_by_group.get(str(group.get("name", "")).lower(), []),
                        "isManagedResourceGroup": str(group.get("id", "")).lower() in managed_group_ids,
                    }
                    for group in groups or []
                ],
            }
        )
    return result


def discover_warehouses(host: str, repository_root: Path) -> list[dict[str, Any]]:
    host = workspace_host(host)
    warehouses: list[dict[str, Any]] = []
    token = ""
    seen: set[str] = set()
    for _ in range(100):
        url = f"https://{host}/api/2.0/sql/warehouses"
        if token:
            url += "?page_token=" + quote(token, safe="")
        response = run_az(["rest", "--method", "GET", "--url", url,
                           "--resource", "2ff814a6-3304-4ab8-85cb-cd0e6f879c1d"], repository_root)
        if not isinstance(response, dict) or not isinstance(response.get("warehouses", []), list):
            raise ApiError(HTTPStatus.BAD_GATEWAY, "Databricks returned an invalid warehouse inventory.")
        for warehouse in response.get("warehouses", []):
            if not isinstance(warehouse, dict) or not warehouse.get("id"):
                raise ApiError(HTTPStatus.BAD_GATEWAY, "Databricks returned an invalid warehouse entry.")
            warehouses.append({
                "id": str(warehouse["id"]), "name": str(warehouse.get("name", warehouse["id"])),
                "size": str(warehouse.get("cluster_size", "")), "state": str(warehouse.get("state", "")),
                "serverless": warehouse.get("enable_serverless_compute") is True,
            })
        token = response.get("next_page_token") or ""
        if not token:
            return warehouses
        if not isinstance(token, str) or token in seen:
            raise ApiError(HTTPStatus.BAD_GATEWAY, "Warehouse inventory pagination did not advance.")
        seen.add(token)
    raise ApiError(HTTPStatus.BAD_GATEWAY, "Warehouse inventory exceeded the page limit; default selection was not attempted.")


def readiness_warnings(output: str) -> list[str]:
    warnings: list[str] = []
    for line in output.splitlines():
        if not line.strip().lower().startswith("warning:"):
            continue
        text = line.split(":", 1)[1].strip()
        unsupported = re.search(
            r"resource type '([^']+)' does not support diagnostic settings",
            text,
            flags=re.IGNORECASE,
        )
        if unsupported:
            text = (
                f"Azure does not support diagnostic settings for resource type "
                f"'{unsupported.group(1)}'. The assessment skipped that diagnostic setting."
            )
        elif "sql statement post requires a statement" in text.lower():
            text = (
                "Databricks SQL evidence could not be collected because the request was incomplete. "
                "SQL-backed findings may be incomplete."
            )
        if text and text not in warnings:
            warnings.append(text)
    return warnings


def readiness_source_warnings(output: str) -> list[dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    for line in output.splitlines():
        if line.startswith(PROGRESS_PREFIX):
            for result in json.loads(line[len(PROGRESS_PREFIX):]).get("results", []):
                results[result["name"]] = result
    for line in output.splitlines():
        event = collector_event(line)
        if event:
            source = event["source"]
            results.setdefault(source["name"], source)
    return readiness_source_checks(list(results.values()))


def readiness_source_checks(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}

    def add(source: str, status: str, message: str) -> None:
        key = f"source:{source}"
        severity, check_status = "warning", "warn"
        title = f"{source} needs attention"
        detail = message or f"This source reported {status} without an explanation. Missing evidence is not zero usage."
        remediation = "Review the source response and correct the reported access, configuration, or API issue before relying on related findings."
        if message == "A SQL Warehouse ID is required to read this source.":
            key, title = "sql-warehouse", "SQL-backed evidence was not checked"
            detail = "No SQL Warehouse was available to these checks. Billing, compute timelines, query history, and other system-table evidence may be unavailable; this is not a finding of missing telemetry."
            remediation = "In Configure, select a SQL Warehouse for each affected workspace and explicitly approve auto-start in Validate (DBU charges may apply). The signed-in identity also needs warehouse access and system-table read permissions. Otherwise continue with API-only evidence."
        elif message in {
            "accountId and accountHost are required for Account API inventory.",
            "accountId and accountHost are required for account budget inventory.",
        }:
            key, title = "account-settings", "Account-level evidence is not configured"
            detail = "Workspace collection can continue, but account workspace inventory and account budgets cannot be checked without a Databricks Account ID and Account host."
            remediation = "Enter Account ID and Account host under Databricks account settings in Configure, using an identity authorized for those account APIs. Otherwise accept this coverage gap."
        elif source == "Azure Cost Management" and status == "partial" and message == (
            "Cost access probe succeeded. Readiness checks only a one-day aggregate per scope; full cost coverage is not validated until Run."
        ):
            key, title = "cost-probe", "Cost Management access probe passed"
            severity, check_status = "info", "pass"
            detail = "The one-day aggregate access probe succeeded. Full-window cost collection happens during Run; its coverage and throttling behavior have not yet been validated."
            remediation = ""
        elif re.search(r"resource type '[^']+' does not support diagnostic settings", message, re.IGNORECASE):
            key, title = "diagnostics-unsupported", "Some resource types do not support diagnostic settings"
            severity, check_status = "info", "skipped"
            detail = "Azure reports diagnostic settings as unsupported for these resource types. These checks are not applicable; enabling diagnostics on them is not a required fix."
            remediation = ""
        elif re.search(r"HTTP 403\b|AuthorizationFailed|PERMISSION_DENIED|INSUFFICIENT_PERMISSIONS", message, re.IGNORECASE):
            domain = "Databricks" if source.startswith("Databricks") else "Azure"
            key, title = f"permissions:{domain}", f"{domain} evidence access was denied"
            detail = "The signed-in identity could not read some selected evidence. Expand source details to see the exact denied operation; other readable evidence can still be collected."
            remediation = (
                "Ask the Databricks administrator for the specific read permissions named in the source response (for example SELECT or READ METADATA), then revalidate."
                if domain == "Databricks" else
                "Ask the Azure administrator for read access to the named resource or Cost Management scope, then revalidate."
            )
            if "system.lakeflow.pipeline_update_timeline" in message:
                key, title = "permissions:pipeline-timeline", "Pipeline timeline SELECT access is missing"
                remediation = "Use the separate Pipeline timeline permission setup in Validate to verify the signed-in identity and review the three grants before confirming. Existing grant authority is required; otherwise ask the system-table administrator for USE CATALOG on system, USE SCHEMA on system.lakeflow, and SELECT on system.lakeflow.pipeline_update_timeline. Validation itself never grants permissions."
            elif "workspace-bindings/" in message:
                key, title = "permissions:catalog-bindings", "Catalog binding metadata access is missing"
                remediation = "Ask the catalog owner or metastore administrator to provide catalog binding visibility, or have an authorized identity perform these checks. The binding API denied metadata access; table SELECT access alone may not satisfy it."
        elif re.search(r"HTTP 401\b|UNAUTHENTICATED|InvalidAuthenticationToken", message, re.IGNORECASE):
            key, title = "authentication", "Source authentication failed"
            remediation = "Sign in again with the intended tenant and identity, then revalidate the selected scope."
        elif re.search(r"\b429\b|Too Many Requests", message, re.IGNORECASE):
            key, title = "throttling", "An evidence API is throttling requests"
            detail = "A source returned a rate-limit response. Its evidence is incomplete; repeating validation immediately can extend throttling."
            remediation = "Wait for the service retry interval before retrying. Use a saved snapshot for review instead of collecting again."
        elif re.search(r"TABLE_OR_VIEW_NOT_FOUND|SCHEMA_NOT_FOUND", message):
            key, title = "table-unavailable", "A selected table or view is unavailable"
            detail = "A selected table could not be resolved by the SQL warehouse. The source response identifies the table and query failure."
            remediation = "Verify the named table exists, is visible to the signed-in identity, and is accessible from the selected warehouse. Correct the target or permissions before retrying."
        elif message == "The Jobs and cluster event APIs do not expose full Spark UI metrics. Supply an approved event-log export to satisfy detailed Spark evidence.":
            key, title = "spark-metrics", "Detailed Spark metrics require a separate review"
            detail = "This collector reads selected job-run metadata and cluster events, not Spark stage, task, executor, or SQL execution metrics. That detailed evidence has not been validated."
            remediation = "Review an approved Spark UI or event-log export separately. This toolkit has no event-log importer, so selecting a run ID alone cannot pass detailed Spark coverage."
        check = grouped.setdefault(key, {
            "source": source, "status": status, "title": title, "severity": severity,
            "checkStatus": check_status, "detail": detail, "remediation": remediation, "evidence": [],
        })
        evidence = {"source": source, "detail": message or detail}
        if evidence not in check["evidence"]:
            check["evidence"].append(evidence)

    for result in results:
        name, status = result["name"], result["status"]
        if status not in {"partial", "failed", "pending telemetry"}:
            continue
        sources = result.get("sources") or []
        if sources:
            for source in sources:
                if source["status"] not in {"passed", "skipped"}:
                    add(f"{name} / {source['source']}", source["status"], source.get("message") or "")
            if not any(source["status"] not in {"passed", "skipped"} for source in sources):
                add(name, status, result.get("error") or "; ".join(result.get("limitations") or []))
        else:
            messages = list(result.get("limitations") or [])
            if result.get("error") and result["error"] not in "; ".join(messages):
                messages.append(result["error"])
            for message in messages or [""]:
                add(name, status, message)
    return list(grouped.values())


def validation_report(
    config: dict[str, Any],
    approvals: dict[str, Any],
    completed: subprocess.CompletedProcess[str],
) -> dict[str, Any]:
    databricks = config.get("databricks") or {}
    workspaces = databricks.get("workspaces") or []
    has_warehouse = bool(databricks.get("sqlWarehouseId")) or any(
        bool(workspace.get("sqlWarehouseId")) for workspace in workspaces if isinstance(workspace, dict)
    )
    approved = bool(approvals.get("approveSqlWarehouseAutoStart"))
    readiness_passed = completed.returncode == 0
    detail = ANSI_ESCAPE.sub("", (completed.stdout + "\n" + completed.stderr)).strip()
    source_checks = readiness_source_warnings(detail)
    for check in source_checks:
        if check["title"] != "SQL-backed evidence was not checked":
            continue
        affected_ids = {
            match.group(1)
            for evidence in check["evidence"]
            if (match := re.search(r"\[([^\]]+)\]", evidence["source"]))
        }
        affected_names = [
            f"{workspace.get('name') or workspace.get('workspaceId')} ({workspace.get('workspaceId')})"
            for workspace in workspaces
            if isinstance(workspace, dict) and workspace.get("include")
            and str(workspace.get("workspaceId")) in affected_ids
        ]
        if affected_names:
            check["detail"] += " Affected workspaces: " + ", ".join(affected_names) + "."
        check["remediation"] = (
            "In Step 1: Configure > Azure Databricks workspaces, use each affected workspace's "
            "'SQL Warehouse for system-table queries' dropdown, then explicitly approve warehouse use "
            "in Validate (DBU charges may apply). The identity needs CAN USE on the warehouse and "
            "the required system-table read privileges. If no warehouse is listed, ask the workspace "
            "administrator for access. Leave None selected only if API-only evidence is sufficient."
        )
    detail = "\n".join(line for line in detail.splitlines() if not line.startswith(PROGRESS_PREFIX))
    checks: list[dict[str, Any]] = [
        {
            "id": "subscription-selected",
            "title": "At least one subscription is selected",
            "severity": "blocker",
            "status": "pass" if (config.get("azure") or {}).get("subscriptions") else "fail",
            "detail": "Subscription scope is configured." if (config.get("azure") or {}).get("subscriptions") else "Select at least one subscription.",
            "group": "scope",
        },
        {
            "id": "resource-group-selected",
            "title": "At least one resource group is selected",
            "severity": "blocker",
            "status": "pass" if (config.get("azure") or {}).get("resourceGroups") else "fail",
            "detail": "Resource group scope is configured." if (config.get("azure") or {}).get("resourceGroups") else "Select at least one resource group.",
            "group": "scope",
        },
        {
            "id": "workspace-selected",
            "title": "At least one workspace is selected",
            "severity": "blocker",
            "status": "pass" if any(item.get("include") for item in workspaces if isinstance(item, dict)) else "fail",
            "detail": "Workspace scope is configured." if any(item.get("include") for item in workspaces if isinstance(item, dict)) else "Select at least one workspace.",
            "group": "scope",
        },
        {
            "id": "sql-warehouse-approval",
            "title": "SQL Warehouse auto-start is explicitly approved",
            "severity": "blocker",
            "status": "pass" if not has_warehouse or approved else "fail",
            "detail": (
                "SQL-backed readiness was approved."
                if has_warehouse and approved
                else "A SQL Warehouse is selected, but auto-start has not been approved."
                if has_warehouse and not approved
                else "No SQL Warehouse is configured."
            ),
            "remediation": "Approve SQL Warehouse auto-start or remove SQL Warehouse IDs."
            if has_warehouse and not approved
            else None,
            "resolvableInUi": has_warehouse and not approved,
            "group": "safety",
        },
        {
            "id": "read-only-scanner",
            "title": "Read-only readiness completed",
            "severity": "blocker",
            "status": "pass" if readiness_passed else "fail",
            "detail": (
                "Read-only source checks finished. Review the warnings below; finishing does not mean every source passed."
                if readiness_passed else detail[-4000:] or "Readiness failed."
            ),
            "remediation": "Review the readiness output and correct the reported environment, access, or scope issue."
            if not readiness_passed
            else None,
            "group": "safety",
        },
    ]
    for index, warning in enumerate(readiness_warnings(detail), 1):
        unsupported = warning.startswith("Azure does not support diagnostic settings for resource type ")
        if unsupported and any(check["title"] == "Some resource types do not support diagnostic settings" for check in source_checks):
            continue
        checks.append(
            {
                "id": f"readiness-warning-{index}",
                "title": "Diagnostic settings are not applicable" if unsupported else "Readiness reported a source issue",
                "severity": "info" if unsupported else "warning",
                "status": "skipped" if unsupported else "warn",
                "detail": warning,
                "remediation": None if unsupported else "Review this item before relying on findings that use this evidence.",
                "group": "permissions",
            }
        )
    for index, warning in enumerate(source_checks, 1):
        checks.append(
            {
                "id": f"readiness-source-{index}",
                "title": warning["title"],
                "severity": warning["severity"],
                "status": warning["checkStatus"],
                "detail": warning["detail"],
                "remediation": warning["remediation"],
                "evidence": warning["evidence"],
                "group": "permissions",
            }
        )
    blocker_count = sum(check["severity"] == "blocker" and check["status"] == "fail" for check in checks)
    warning_count = sum(check["status"] == "warn" for check in checks)
    return {
        "generatedAtUtc": utc_now(),
        "checks": checks,
        "blockerCount": blocker_count,
        "warningCount": warning_count,
        "canRun": blocker_count == 0,
        "requiresSqlWarehouseApproval": has_warehouse and not approved,
    }


def normalize_manifest(manifest: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    scope = manifest.get("scope") or {}
    config_workspaces = (config.get("databricks") or {}).get("workspaces") or []
    workspace_urls = set(scope.get("workspaces") or [])
    workspaces = [
        {
            "name": str(item.get("name", "")),
            "workspaceId": str(item.get("workspaceId", "")),
            "workspaceUrl": str(item.get("workspaceUrl", "")),
            "resourceGroup": str(item.get("resourceGroup", "")),
            "subscriptionId": str(item.get("subscriptionId", "")),
        }
        for item in config_workspaces
        if isinstance(item, dict)
        and item.get("include")
        and (not workspace_urls or item.get("workspaceUrl") in workspace_urls)
    ]
    normalized = dict(manifest)
    normalized["status"] = "passed" if manifest.get("status") == "completed" else manifest.get("status")
    normalized["scope"] = {
        "tenantId": str((config.get("azure") or {}).get("tenantId", "")),
        "subscriptionIds": list(scope.get("subscriptionIds") or scope.get("subscriptions") or []),
        "resourceGroups": list(scope.get("resourceGroups") or []),
        "resourceGroupIds": list(scope.get("resourceGroupIds") or []),
        "workspaces": workspaces,
    }
    normalized["outputRoot"] = str(manifest.get("outputRoot", ""))
    return normalized


def map_collection(run_root: Path) -> list[dict[str, Any]]:
    resolved_run_root = run_root.resolve()
    collection = read_json(run_root / "collection-status.json", [])
    mapped: list[dict[str, Any]] = []
    for item in collection if isinstance(collection, list) else []:
        value = dict(item)
        name = str(value.get("name", ""))
        value["domain"] = "databricks" if name.lower().startswith("databricks") else "azure"
        match = re.search(r"\[([^\]]+)\]", name)
        if match:
            value["workspaceKey"] = match.group(1)
        outputs = []
        for output in value.get("outputs") or []:
            try:
                outputs.append(
                    contained_path(resolved_run_root, Path(str(output)))
                    .relative_to(resolved_run_root)
                    .as_posix()
                )
            except ApiError:
                continue
        value["outputs"] = outputs
        mapped.append(value)
    return mapped


def normalized_values(run_root: Path, name: str) -> list[dict[str, Any]]:
    return [
        {**record, "_value": record.get("normalized") or {}, "_scope": record.get("customerScope") or {}}
        for record in read_ndjson(run_root / "normalized" / name)
    ]


def workspace_name_map(config: dict[str, Any]) -> dict[str, str]:
    return {
        str(item.get("workspaceId", "")): str(item.get("name", ""))
        for item in (config.get("databricks") or {}).get("workspaces") or []
        if isinstance(item, dict)
    }


def map_compute(run_root: Path, config: dict[str, Any]) -> list[dict[str, Any]]:
    names = workspace_name_map(config)
    rows = []
    for record in normalized_values(run_root, "compute.ndjson"):
        value = record["_value"]
        autoscale = value.get("autoscale") or {}
        azure = value.get("azure_attributes") or {}
        rows.append(
            {
                "clusterId": str(value.get("cluster_id", "")),
                "clusterName": str(value.get("cluster_name", "")),
                "workspaceName": names.get(str(value.get("workspaceKey") or record["_scope"].get("workspaceKey")), ""),
                "source": str(value.get("cluster_source", "API")).upper(),
                "state": str(value.get("state", "")),
                "nodeTypeId": str(value.get("node_type_id", "")),
                "driverNodeTypeId": str(value.get("driver_node_type_id", "")),
                "runtime": str(value.get("spark_version", "")),
                "photon": str(value.get("runtime_engine", "")).upper() == "PHOTON",
                "autoterminationMinutes": int(value.get("autotermination_minutes") or 0),
                "minWorkers": autoscale.get("min_workers"),
                "maxWorkers": autoscale.get("max_workers"),
                "spotDriver": str(azure.get("availability", "")).upper() == "SPOT_AZURE",
                "observedUptimeHours": round(
                    max(0, (float(value.get("terminated_time") or time.time() * 1000) - float(value.get("start_time") or 0)) / 3600000),
                    2,
                ),
                "idlePercent": None,
                "owner": value.get("creator_user_name"),
                "policyName": value.get("policy_id"),
            }
        )
    return rows


def map_warehouses(run_root: Path, config: dict[str, Any]) -> list[dict[str, Any]]:
    names = workspace_name_map(config)
    rows = []
    for record in normalized_values(run_root, "warehouse.ndjson"):
        value = record["_value"]
        rows.append(
            {
                "id": str(value.get("id", "")),
                "name": str(value.get("name", "")),
                "workspaceName": names.get(str(value.get("workspaceKey") or record["_scope"].get("workspaceKey")), ""),
                "size": str(value.get("cluster_size") or value.get("size") or ""),
                "state": str(value.get("state", "")),
                "serverless": bool(value.get("enable_serverless_compute")),
                "photon": bool(value.get("enable_photon")),
                "autoStopMinutes": int(value.get("auto_stop_mins") or 0),
                "minClusters": int(value.get("min_num_clusters") or 0),
                "maxClusters": int(value.get("max_num_clusters") or 0),
                "queryCount": None,
                "p95QueueSeconds": None,
                "p95DurationSeconds": None,
                "spillGb": None,
            }
        )
    return rows


def map_workloads(run_root: Path, config: dict[str, Any]) -> list[dict[str, Any]]:
    names = workspace_name_map(config)
    run_counts: dict[str, int] = defaultdict(int)
    failures: dict[str, int] = defaultdict(int)
    durations: dict[str, list[float]] = defaultdict(list)
    for record in normalized_values(run_root, "job_run.ndjson"):
        value = record["_value"]
        job_id = str(value.get("job_id", ""))
        run_counts[job_id] += 1
        result_state = str((value.get("state") or {}).get("result_state", "")).upper()
        if result_state and result_state != "SUCCESS":
            failures[job_id] += 1
        start = float(value.get("start_time") or 0)
        end = float(value.get("end_time") or 0)
        if end >= start and start:
            durations[job_id].append((end - start) / 1000)
    rows = []
    for record in normalized_values(run_root, "job.ndjson"):
        value = record["_value"]
        job_id = str(value.get("job_id", ""))
        settings = value.get("settings") or {}
        samples = sorted(durations[job_id])
        count = run_counts[job_id]
        p50 = samples[len(samples) // 2] if samples else None
        p95 = samples[min(len(samples) - 1, int(len(samples) * 0.95))] if samples else None
        compute_type = "serverless" if settings.get("environments") else "job-cluster" if settings.get("job_clusters") else "all-purpose"
        rows.append(
            {
                "jobId": job_id,
                "jobName": str(settings.get("name", "")),
                "workspaceName": names.get(str(value.get("workspaceKey") or record["_scope"].get("workspaceKey")), ""),
                "computeType": compute_type,
                "runCount": count,
                "failureRatePercent": round(failures[job_id] * 100 / count, 1) if count else None,
                "p50DurationSeconds": p50,
                "p95DurationSeconds": p95,
                "owner": value.get("creator_user_name"),
                "observedCost": None,
                "currency": str((config.get("azure") or {}).get("currency", "")),
            }
        )
    return rows


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int((len(ordered) - 1) * fraction))]


def map_cost(run_root: Path, config: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    daily: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    groups: dict[str, float] = defaultdict(float)
    drivers: dict[str, dict[str, Any]] = {}
    currency = str((config.get("azure") or {}).get("currency", ""))
    for record in normalized_values(run_root, "azure_cost.ndjson"):
        value = record["_value"]
        cost = float(value.get("PreTaxCost") or 0)
        basis = str(value.get("costBasis", ""))
        raw_date = str(value.get("UsageDate", ""))
        date = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}" if len(raw_date) == 8 else raw_date
        if basis == "ActualCost":
            daily[date]["actualCost"] += cost
        elif basis == "AmortizedCost":
            daily[date]["amortizedCost"] += cost
        resource_id = str(value.get("ResourceId", ""))
        parts = resource_id.strip("/").split("/")
        lower_parts = [part.lower() for part in parts]
        resource_group = parts[lower_parts.index("resourcegroups") + 1] if "resourcegroups" in lower_parts else ""
        resource_type = ""
        if "providers" in lower_parts:
            index = lower_parts.index("providers")
            resource_type = "/".join(parts[index + 1:index + 3])
        name = parts[-1] if parts else resource_id
        if basis == "ActualCost":
            groups[resource_group or "Unattributed"] += cost
            item = drivers.setdefault(
                resource_id or name,
                {
                    "driver": resource_id or name,
                    "displayName": name,
                    "resourceType": resource_type,
                    "subscriptionId": str(record["_scope"].get("subscriptionId", "")),
                    "resourceGroup": resource_group,
                    "workspaceName": None,
                    "observedCost": 0.0,
                    "currency": str(value.get("Currency") or currency),
                },
            )
            item["observedCost"] += cost
    trend = [
        {
            "date": date,
            "actualCost": round(values["actualCost"], 2),
            "amortizedCost": round(values["amortizedCost"], 2),
            "dbuCost": 0.0,
            "infrastructureCost": round(values["actualCost"], 2),
        }
        for date, values in sorted(daily.items())
    ]
    breakdown = [
        {
            "key": f"resourceGroup:{name}",
            "label": name,
            "cost": round(cost, 2),
            "currency": currency,
            "dimension": "resourceGroup",
        }
        for name, cost in sorted(groups.items(), key=lambda item: item[1], reverse=True)
    ]
    cost_drivers = []
    for rank, item in enumerate(sorted(drivers.values(), key=lambda value: value["observedCost"], reverse=True)[:20], 1):
        item["rank"] = rank
        item["observedCost"] = round(item["observedCost"], 2)
        cost_drivers.append(item)
    return cost_drivers, trend, breakdown


def default_review(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "findingId": str(item.get("detectorId", "")),
            "finding": str(item.get("title", "")),
            "evidenceLinks": list(item.get("evidenceFiles") or []),
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
        for item in findings
    ]


def list_exports(run_root: Path) -> list[dict[str, Any]]:
    descriptions = {
        "reports/assessment-report.md": "Consolidated assessment report.",
        "reports/top-cost-drivers.csv": "Ranked observed cost drivers.",
        "reports/prioritized-backlog.csv": "Prioritized candidate findings.",
        "reports/human-validation-sign-off.csv": "Human validation sign-off register.",
    }
    candidates = [
        path
        for path in run_root.iterdir()
        if path.is_file() and path.suffix.lower() == ".json" and not path.name.startswith(".")
    ]
    reports = run_root / "reports"
    if reports.is_dir():
        candidates.extend(path for path in reports.iterdir() if path.is_file() and path.suffix.lower() in {".md", ".csv", ".json"})
    exports = []
    for path in sorted(candidates):
        relative = path.relative_to(run_root).as_posix()
        kind = path.suffix.lower().lstrip(".")
        exports.append(
            {
                "name": path.stem.replace("-", " ").title(),
                "relativePath": relative,
                "kind": kind,
                "description": descriptions.get(relative, "Persisted assessment artifact."),
                "sizeBytes": path.stat().st_size,
                "sensitivity": "sensitive",
            }
        )
    return exports


def map_results(run_root: Path) -> dict[str, Any]:
    manifest_raw = read_json(run_root / "assessment-manifest.json")
    config = read_json(run_root / "assessment-config.json")
    candidates = read_json(
        run_root / "optimization-candidates.json",
        {
            "schemaVersion": "1.0",
            "analysisWindow": manifest_raw.get("analysisWindow") or {},
            "candidateCount": 0,
            "insufficientEvidenceCount": 0,
            "findings": [],
        },
    )
    findings = candidates.get("findings") or []
    for finding in findings:
        finding.setdefault("scope", {"subscriptionId": None, "resourceGroup": None, "workspaceName": None, "workload": None})
        finding.setdefault("evidenceFiles", [])
    collection = map_collection(run_root)
    cost_drivers, cost_trend, cost_breakdown = map_cost(run_root, config)
    review_path = run_root / ".ui-review.json"
    review = read_json(review_path, default_review(findings))
    roadmap = [
        {
            "horizon": ("0-30", "31-60", "61-90")[index % 3],
            "title": str(finding.get("title", "")),
            "detail": str(finding.get("recommendedAction", "")),
            "owner": "Unassigned",
            "dependsOnFindingIds": [str(finding.get("detectorId", ""))],
        }
        for index, finding in enumerate(findings)
        if finding.get("status") == "candidate"
    ]
    evidence_gaps = [
        {
            "source": item.get("name", ""),
            "status": item.get("status", ""),
            "impact": "; ".join(item.get("limitations") or []) or item.get("error", ""),
            "requiredToUnlock": [],
        }
        for item in collection
        if item.get("status") in {"partial", "failed", "pending telemetry"}
    ]
    report_path = run_root / "reports" / "assessment-report.md"
    return {
        "manifest": normalize_manifest(manifest_raw, config),
        "scopeFilter": read_json(
            run_root / "scope-filter.json",
            {"schemaVersion": "1.0", "allowedResourceGroups": [], "allowedResourceGroupIds": [], "entities": {}, "limitations": []},
        ),
        "collection": collection,
        "reconciliation": read_json(run_root / "cost-reconciliation.json"),
        "attribution": read_json(run_root / "attribution-coverage.json"),
        "telemetry": read_json(run_root / "telemetry-quality.json"),
        "benefits": read_json(run_root / "benefits-baseline.json"),
        "candidates": candidates,
        "costDrivers": cost_drivers,
        "costTrend": cost_trend,
        "costBreakdown": cost_breakdown,
        "compute": map_compute(run_root, config),
        "warehouses": map_warehouses(run_root, config),
        "workloads": map_workloads(run_root, config),
        "roadmap": roadmap,
        "evidenceGaps": evidence_gaps,
        "review": review,
        "reportMarkdown": report_path.read_text(encoding="utf-8-sig") if report_path.is_file() else "",
        "exports": list_exports(run_root),
    }


def run_summary(run_root: Path) -> dict[str, Any] | None:
    manifest = read_json(run_root / "assessment-manifest.json")
    if manifest.get("status") not in COMPLETED_STATUSES:
        return None
    config = read_json(run_root / "assessment-config.json", {})
    candidates = read_json(run_root / "optimization-candidates.json", {"findings": []})
    benefits = read_json(run_root / "benefits-baseline.json", {})
    reconciliation = read_json(run_root / "cost-reconciliation.json", {})
    scope = manifest.get("scope") or {}
    config_workspaces = (config.get("databricks") or {}).get("workspaces") or []
    return {
        "runId": str(manifest.get("runId", run_root.name)),
        "customerId": str(manifest.get("customerId", "")),
        "status": "passed" if manifest.get("status") == "completed" else manifest.get("status"),
        "startedAtUtc": str(manifest.get("startedAtUtc", "")),
        "completedAtUtc": manifest.get("completedAtUtc"),
        "analysisWindow": manifest.get("analysisWindow") or {},
        "authoritativeCost": float(benefits.get("authoritativeCost") or reconciliation.get("authoritativeTotal") or 0),
        "currency": str(benefits.get("currency") or reconciliation.get("currency") or (config.get("azure") or {}).get("currency", "")),
        "findingCount": len(candidates.get("findings") or []),
        "subscriptionIds": list(scope.get("subscriptionIds") or scope.get("subscriptions") or []),
        "workspaceNames": [
            str(item.get("name", ""))
            for item in config_workspaces
            if isinstance(item, dict) and item.get("include")
        ],
        "scenarioId": "",
    }


def collector_event(line: str) -> dict[str, Any] | None:
    match = re.match(
        r"^\s{2}(.+?):\s*(passed|partial|failed|pending telemetry|skipped)\s*\((\d+) items\)\s*$",
        line,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    name, status, count = match.groups()
    workspace = re.search(r"\[([^\]]+)\]", name)
    source: dict[str, Any] = {
        "name": name,
        "status": status.lower(),
        "startedAtUtc": None,
        "completedAtUtc": utc_now(),
        "itemCount": int(count),
        "outputs": [],
        "limitations": [],
        "error": "",
        "domain": "databricks" if name.lower().startswith("databricks") else "azure",
    }
    if workspace:
        source["workspaceKey"] = workspace.group(1)
    return {"type": "source", "source": source, "atUtc": utc_now()}


class RunState:
    def __init__(self, run_id: str, config_path: Path) -> None:
        self.run_id = run_id
        self.config_path = config_path
        self.process: subprocess.Popen[str] | None = None
        self.events: list[dict[str, Any]] = []
        self.terminal = False
        self.cancel_requested = False
        self.lock = threading.Lock()

    def add_event(self, event: dict[str, Any]) -> None:
        with self.lock:
            self.events.append(event)
            if event.get("type") in TERMINAL_EVENT_TYPES:
                self.terminal = True

    def snapshot(self, after: int) -> dict[str, Any]:
        with self.lock:
            cursor = max(0, min(after, len(self.events)))
            return {"events": self.events[cursor:], "nextCursor": len(self.events), "terminal": self.terminal}


class ValidationState:
    def __init__(self, validation_id: str) -> None:
        self.lock = threading.Lock()
        self.data: dict[str, Any] = {
            "validationId": validation_id,
            "status": "running",
            "startedAtUtc": utc_now(),
            "finishedAtUtc": None,
            "lastActivityAtUtc": utc_now(),
            "message": "Starting PowerShell and reading the selected configuration.",
            "steps": [],
            "report": None,
            "error": None,
        }

    def consume(self, raw_line: str) -> None:
        line = ANSI_ESCAPE.sub("", raw_line).strip()
        if not line:
            return
        with self.lock:
            self.data["lastActivityAtUtc"] = utc_now()
            if not line.startswith(PROGRESS_PREFIX):
                if line.lower().startswith("warning:") or "retry" in line.lower():
                    self.data["message"] = line
                return
            event = json.loads(line[len(PROGRESS_PREFIX):])
            if "steps" in event:
                self.data["steps"] = [
                    {
                        "id": step["id"],
                        "title": step["title"],
                        "status": "pending",
                        "detail": "Waiting for earlier checks.",
                        "startedAtUtc": None,
                        "finishedAtUtc": None,
                        "estimatedSeconds": 90 if step["id"] in {"azure-cost", "azure-governance"}
                        else 5 if step["id"] in {"scope", "safety", "finish"} else 20,
                    }
                    for step in event["steps"]
                ]
                return
            step = next((item for item in self.data["steps"] if item["id"] == event.get("id")), None)
            if step is None or event.get("status") not in {"running", "pass", "warn", "fail", "skipped"}:
                raise ValueError("The assessment emitted an invalid validation progress event.")
            step["status"] = event["status"]
            step["detail"] = event.get("detail", "")
            if event.get("results"):
                checks = readiness_source_checks(event["results"])
                warnings = [check for check in checks if check["checkStatus"] == "warn"]
                step["issues"] = warnings
                if warnings:
                    step["status"] = "fail" if event["status"] == "fail" else "warn"
                    step["detail"] = "Some source checks need attention. Actions and source responses are listed below."
                elif checks:
                    applicable_passed = any(
                        result["status"] == "passed" or result.get("itemCount", 0) > 0
                        or any(source["status"] == "passed" for source in result.get("sources", []))
                        for result in event["results"]
                    ) or any(check["checkStatus"] == "pass" for check in checks)
                    step["status"] = "pass" if applicable_passed else "not-applicable"
                    step["detail"] = ("Applicable source checks passed. " if applicable_passed else "") + " ".join(check["detail"] for check in checks)
            step["startedAtUtc"] = step["startedAtUtc"] or utc_now()
            if event["status"] != "running":
                step["finishedAtUtc"] = utc_now()
            self.data["message"] = step["detail"]

    def finish(self, report: dict[str, Any] | None = None, error: str | None = None) -> None:
        with self.lock:
            blocked = report is not None and report.get("canRun") is False and any(
                check.get("severity") == "blocker" and check.get("status") == "fail"
                for check in report.get("checks", [])
            )
            if not error and not self.data["steps"] and not blocked:
                error = "Validation ended without reporting any checks. Review the local server output and retry."
            elif not error and not self.data["steps"]:
                self.data["message"] = "Readiness stopped before source checks. Review the reported blockers."
            self.data.update({
                "status": "failed" if error else "completed",
                "finishedAtUtc": utc_now(),
                "lastActivityAtUtc": utc_now(),
                "report": report,
                "error": error,
            })
            for step in self.data["steps"]:
                if step["status"] in {"pending", "running"}:
                    was_running = step["status"] == "running"
                    step.update({
                        "status": "fail" if was_running else "skipped",
                        "detail": error or "This check did not finish. Review the validation warnings.",
                        "finishedAtUtc": utc_now(),
                    })

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return json.loads(json.dumps(self.data))


class AssessmentService:
    def __init__(self, repository_root: Path, output_root: Path, dist_index: Path, powershell: str = "pwsh") -> None:
        self.repository_root = repository_root.resolve()
        self.assessment_root = (self.repository_root / "assessment").resolve()
        self.output_root = output_root.resolve()
        self.output_root.mkdir(parents=True, exist_ok=True)
        self.dist_index = dist_index.resolve()
        self.powershell = powershell
        self.script_path = self.assessment_root / "Invoke-Assessment.ps1"
        self.runs: dict[str, RunState] = {}
        self.runs_lock = threading.Lock()
        self.validations: dict[str, ValidationState] = {}
        self.validations_lock = threading.Lock()
        self.operation_lock = threading.RLock()
        self.permission_setup = PermissionSetupService(
            self._permission_client,
            contained_path(self.output_root, self.output_root / ".ui-server" / "permission-setup"),
        )

    def _permission_client(self, host: str, warehouse_id: str) -> DatabricksSetupClient:
        try:
            token = run_az(["account", "get-access-token", "--resource", "2ff814a6-3304-4ab8-85cb-cd0e6f879c1d"],
                           self.repository_root, timeout_seconds=60)
        except ApiError as exc:
            raise SetupError(str(exc), exc.status) from exc
        if not isinstance(token, dict) or not isinstance(token.get("accessToken"), str) or not token["accessToken"]:
            raise SetupError("Azure CLI did not return a usable Databricks access token.", 401)
        return DatabricksSetupClient(host, warehouse_id, token["accessToken"])

    def require_setup_idle(self) -> None:
        if self.permission_setup.busy():
            raise ApiError(HTTPStatus.CONFLICT, "Permission setup is running. Check its result before starting other live work.")

    def require_assessment_idle(self) -> None:
        with self.validations_lock:
            if any(state.snapshot()["status"] == "running" for state in self.validations.values()):
                raise ApiError(HTTPStatus.CONFLICT, "Wait for the active validation before changing permissions.")
        with self.runs_lock:
            if any(not state.terminal for state in self.runs.values()):
                raise ApiError(HTTPStatus.CONFLICT, "Wait for the active assessment before changing permissions.")

    def load_default_config(self) -> dict[str, Any]:
        return read_json(resolve_default_config(self.assessment_root))

    def sign_in(self, tenant_id: str) -> None:
        if not TENANT_ID_PATTERN.fullmatch(tenant_id):
            raise ApiError(HTTPStatus.BAD_REQUEST, "A valid Azure tenant ID is required.")
        current = run_command(
            ["az", "account", "show", "--only-show-errors", "--output", "json"],
            self.repository_root,
        )
        if current.returncode == 0:
            try:
                account = json.loads(current.stdout)
            except json.JSONDecodeError:
                account = {}
            if str(account.get("tenantId", "")).lower() == tenant_id.lower():
                return

        environment = os.environ.copy()
        environment["AZURE_CORE_LOGIN_EXPERIENCE_V2"] = "off"
        completed = run_command(
            [
                "az",
                "login",
                "--tenant",
                tenant_id,
                "--allow-no-subscriptions",
                "--only-show-errors",
                "--output",
                "json",
            ],
            self.repository_root,
            environment,
        )
        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip() or "Azure sign-in failed."
            raise ApiError(HTTPStatus.UNAUTHORIZED, detail)

    def validate(self, config: dict[str, Any], approvals: dict[str, Any]) -> dict[str, Any]:
        config_path = write_config(self.output_root, config, "readiness")
        readiness_root = contained_path(self.output_root, self.output_root / ".ui-server" / "readiness" / uuid.uuid4().hex)
        readiness_root.mkdir(parents=True)
        arguments = build_assessment_arguments(
            self.powershell, self.script_path, "Readiness", config_path, readiness_root, approvals
        )
        try:
            completed = run_command(
                arguments, self.repository_root, {**os.environ, "ASSESSMENT_UI_PROGRESS": "1", "NO_COLOR": "1"}
            )
            return validation_report(config, approvals, completed)
        finally:
            config_path.unlink(missing_ok=True)
            shutil.rmtree(readiness_root, ignore_errors=True)

    def start_validation(self, config: dict[str, Any], approvals: dict[str, Any]) -> dict[str, Any]:
        config_path = write_config(self.output_root, config, "readiness")
        state = ValidationState(uuid.uuid4().hex)
        with self.validations_lock:
            self.validations[state.data["validationId"]] = state
        threading.Thread(
            target=self._monitor_validation, args=(state, config_path, config, approvals), daemon=True
        ).start()
        return state.snapshot()

    def validation_status(self, validation_id: str) -> dict[str, Any]:
        with self.validations_lock:
            state = self.validations.get(validation_id)
        if state is None:
            raise ApiError(
                HTTPStatus.NOT_FOUND,
                "This validation is no longer available. The local server may have restarted. Run validation again.",
            )
        return state.snapshot()

    def _monitor_validation(
        self, state: ValidationState, config_path: Path, config: dict[str, Any], approvals: dict[str, Any]
    ) -> None:
        readiness_root = contained_path(
            self.output_root, self.output_root / ".ui-server" / "readiness" / state.data["validationId"]
        )
        process = None
        try:
            readiness_root.mkdir(parents=True)
            arguments = build_assessment_arguments(
                self.powershell, self.script_path, "Readiness", config_path, readiness_root, approvals
            )
            environment = {**os.environ, "ASSESSMENT_UI_PROGRESS": "1", "NO_COLOR": "1"}
            process = subprocess.Popen(
                arguments, cwd=self.repository_root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", bufsize=1, env=environment,
            )
            output: list[str] = []
            assert process.stdout is not None
            with process.stdout:
                for line in process.stdout:
                    output.append(line)
                    state.consume(line)
            completed = subprocess.CompletedProcess(arguments, process.wait(), "".join(output), "")
            report = validation_report(config, approvals, completed)
            for step in state.snapshot()["steps"]:
                if step["status"] in {"pending", "running"}:
                    report["checks"].append({
                        "id": f"readiness-incomplete-{step['id']}", "title": f"{step['title']} did not finish",
                        "severity": "warning", "status": "warn", "group": "permissions",
                        "detail": "This evidence check did not complete. Related findings may be unavailable.",
                    })
                    report["warningCount"] += 1
            state.finish(report)
        except (OSError, ValueError, ApiError) as exc:
            logging.exception("Validation failed")
            state.finish(error=f"Validation stopped: {exc}")
        finally:
            if process is not None and process.poll() is None:
                process.terminate()
                process.wait()
            config_path.unlink(missing_ok=True)
            if readiness_root.is_dir():
                shutil.rmtree(readiness_root)

    def start_run(self, config: dict[str, Any], approvals: dict[str, Any]) -> str:
        config_path = write_config(self.output_root, config, "run")
        arguments = build_assessment_arguments(
            self.powershell, self.script_path, "Run", config_path, self.output_root, approvals
        )
        creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        try:
            process = subprocess.Popen(
                arguments,
                cwd=self.repository_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=creation_flags,
            )
        except OSError as exc:
            config_path.unlink(missing_ok=True)
            raise ApiError(HTTPStatus.SERVICE_UNAVAILABLE, f"Cannot start {self.powershell}: {exc}") from exc

        run_id = ""
        buffered_lines: list[str] = []
        deadline = time.monotonic() + 30
        assert process.stdout is not None
        while time.monotonic() < deadline:
            line = process.stdout.readline()
            if not line:
                if process.poll() is not None:
                    break
                continue
            buffered_lines.append(ANSI_ESCAPE.sub("", line).rstrip())
            match = re.search(r"Assessment run:\s*([A-Za-z0-9][A-Za-z0-9._-]*)", line)
            if match:
                run_id = match.group(1)
                break
        if not run_id:
            process.terminate()
            config_path.unlink(missing_ok=True)
            message = "\n".join(buffered_lines[-20:]) or "Assessment did not emit a run id."
            raise ApiError(HTTPStatus.BAD_GATEWAY, message)

        state = RunState(run_id, config_path)
        state.process = process
        for line in buffered_lines:
            state.add_event({"type": "log", "level": "info", "message": line, "atUtc": utc_now()})
        state.add_event({"type": "phase", "phase": "collecting", "message": "Collecting assessment evidence.", "atUtc": utc_now()})
        with self.runs_lock:
            self.runs[run_id] = state
        threading.Thread(target=self._monitor_run, args=(state,), daemon=True).start()
        return run_id

    def _monitor_run(self, state: RunState) -> None:
        process = state.process
        assert process is not None and process.stdout is not None
        try:
            for raw_line in process.stdout:
                line = ANSI_ESCAPE.sub("", raw_line).rstrip()
                if not line:
                    continue
                lower = line.lower()
                source_event = collector_event(line)
                if source_event:
                    state.add_event(source_event)
                elif "normalizing, detecting" in lower:
                    state.add_event({"type": "phase", "phase": "normalizing", "message": "Normalizing collected evidence.", "atUtc": utc_now()})
                    state.add_event({"type": "phase", "phase": "analyzing", "message": "Analyzing normalized evidence.", "atUtc": utc_now()})
                    state.add_event({"type": "phase", "phase": "findings", "message": "Creating evidence-backed findings.", "atUtc": utc_now()})
                    state.add_event({"type": "phase", "phase": "reporting", "message": "Generating the consolidated report and exports.", "atUtc": utc_now()})
                else:
                    level = "error" if "error" in lower or "failed" in lower else "warn" if "warning" in lower else "info"
                    state.add_event({"type": "log", "level": level, "message": line, "atUtc": utc_now()})
            return_code = process.wait()
            if state.cancel_requested:
                self._mark_canceled(state.run_id)
                state.add_event({"type": "canceled", "atUtc": utc_now()})
            elif return_code == 0:
                state.add_event({"type": "completed", "runId": state.run_id, "atUtc": utc_now()})
            else:
                state.add_event(
                    {
                        "type": "failed",
                        "message": f"Assessment process exited with code {return_code}.",
                        "atUtc": utc_now(),
                    }
                )
        finally:
            state.config_path.unlink(missing_ok=True)

    def _mark_canceled(self, run_id: str) -> None:
        run_root = resolve_run_root(self.output_root, run_id, require_exists=False)
        manifest_path = run_root / "assessment-manifest.json"
        if not manifest_path.is_file():
            return
        manifest = read_json(manifest_path)
        manifest["status"] = "partial"
        manifest["completedAtUtc"] = utc_now()
        manifest["canceledByOperator"] = True
        temporary = manifest_path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        temporary.replace(manifest_path)

    def cancel(self, run_id: str) -> None:
        with self.runs_lock:
            state = self.runs.get(run_id)
        if state is None:
            resolve_run_root(self.output_root, run_id)
            raise ApiError(HTTPStatus.CONFLICT, "Run is not active.")
        process = state.process
        if state.terminal or process is None or process.poll() is not None:
            raise ApiError(HTTPStatus.CONFLICT, "Run is already terminal.")
        state.cancel_requested = True
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                capture_output=True,
                check=False,
            )
        else:
            process.terminate()

    def events(self, run_id: str, after: int) -> dict[str, Any]:
        with self.runs_lock:
            state = self.runs.get(run_id)
        if state is not None:
            return state.snapshot(after)
        run_root = resolve_run_root(self.output_root, run_id)
        manifest = read_json(run_root / "assessment-manifest.json")
        status = manifest.get("status")
        if status not in COMPLETED_STATUSES:
            return {"events": [], "nextCursor": 0, "terminal": False}
        event = (
            {"type": "completed", "runId": run_id, "atUtc": manifest.get("completedAtUtc") or utc_now()}
            if status in {"completed", "passed", "partial"}
            else {"type": "failed", "message": "Assessment failed.", "atUtc": manifest.get("completedAtUtc") or utc_now()}
        )
        events = [event] if after <= 0 else []
        return {"events": events, "nextCursor": 1, "terminal": True}

    def list_runs(self) -> list[dict[str, Any]]:
        summaries = []
        for child in self.output_root.iterdir():
            if not child.is_dir() or not RUN_ID_PATTERN.fullmatch(child.name):
                continue
            manifest_path = child / "assessment-manifest.json"
            if not manifest_path.is_file():
                continue
            summary = run_summary(child)
            if summary is not None:
                summaries.append(summary)
        return sorted(summaries, key=lambda item: item["startedAtUtc"], reverse=True)

    def delete_snapshots(self, run_ids: Any, confirmed: Any) -> dict[str, Any]:
        if confirmed is not True:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Permanent snapshot deletion requires explicit confirmation.")
        if not isinstance(run_ids, list) or not run_ids or not all(
            isinstance(run_id, str) and RUN_ID_PATTERN.fullmatch(run_id) for run_id in run_ids
        ):
            raise ApiError(HTTPStatus.BAD_REQUEST, "runIds must be a non-empty array of valid run IDs.")
        deleted: list[str] = []
        failures: list[dict[str, str]] = []

        def reject_link(path: Path) -> None:
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                raise ApiError(HTTPStatus.CONFLICT, "Snapshot contains a symbolic link or reparse point; deletion refused.")

        def walk_error(error: OSError) -> None:
            raise error

        with self.runs_lock:
            for run_id in dict.fromkeys(run_ids):
                removing = False
                try:
                    candidate = self.output_root / run_id
                    reject_link(candidate)
                    run_root = resolve_run_root(self.output_root, run_id)
                    if run_root.parent != self.output_root or run_root == self.output_root:
                        raise ApiError(HTTPStatus.BAD_REQUEST, "Only individual run folders directly under the output root can be deleted.")
                    manifest_path = run_root / "assessment-manifest.json"
                    reject_link(manifest_path)
                    manifest = read_json(manifest_path)
                    if not isinstance(manifest, dict) or manifest.get("runId") != run_id:
                        raise ApiError(HTTPStatus.CONFLICT, "The folder does not contain a matching assessment manifest.")
                    state = self.runs.get(run_id)
                    if manifest.get("status") not in COMPLETED_STATUSES or (
                        state is not None and (not state.terminal or (state.process is not None and state.process.poll() is None))
                    ):
                        raise ApiError(HTTPStatus.CONFLICT, "Active or unfinished assessments cannot be deleted.")
                    for parent, directories, files in os.walk(run_root, followlinks=False, onerror=walk_error):
                        for name in directories + files:
                            reject_link(Path(parent) / name)
                    removing = True
                    shutil.rmtree(run_root)
                    self.runs.pop(run_id, None)
                    deleted.append(run_id)
                except (ApiError, OSError) as exc:
                    message = str(exc)
                    if removing:
                        message += " Files may already be partly removed; inspect the folder before retrying."
                    logging.warning("Snapshot deletion refused or failed for %s: %s", run_id, exc)
                    failures.append({"runId": run_id, "message": message})
        return {"deletedRunIds": deleted, "failures": failures}

    def save_review(self, run_id: str, entries: Any) -> None:
        if not isinstance(entries, list) or not all(isinstance(entry, dict) for entry in entries):
            raise ApiError(HTTPStatus.BAD_REQUEST, "entries must be a JSON array of review records.")
        run_root = resolve_run_root(self.output_root, run_id)
        path = contained_path(run_root, run_root / ".ui-review.json")
        temporary = contained_path(run_root, run_root / ".ui-review.json.tmp")
        temporary.write_text(json.dumps(entries, indent=2), encoding="utf-8")
        temporary.replace(path)

        columns = [
            "findingId", "finding", "evidenceLinks", "reviewer", "role", "reviewedAtUtc",
            "decision", "businessSlaContext", "performanceReliabilityRisk",
            "securityGovernanceImpact", "validationExperiment", "ownerApprover", "rationale",
        ]
        reports = contained_path(run_root, run_root / "reports")
        reports.mkdir(exist_ok=True)
        csv_path = contained_path(run_root, reports / "human-validation-sign-off.csv")
        csv_temporary = contained_path(run_root, reports / "human-validation-sign-off.csv.tmp")
        with csv_temporary.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
            writer.writeheader()
            for entry in entries:
                row = dict(entry)
                row["evidenceLinks"] = "; ".join(str(item) for item in entry.get("evidenceLinks") or [])
                writer.writerow(row)
        csv_temporary.replace(csv_path)


class AssessmentRequestHandler(BaseHTTPRequestHandler):
    server: "AssessmentHttpServer"

    def log_message(self, format: str, *args: Any) -> None:
        print(f"{self.address_string()} - {format % args}")

    def _json(self, status: int, payload: Any) -> None:
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)

    def _body(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Invalid Content-Length.") from exc
        if length <= 0 or length > MAX_BODY_BYTES:
            raise ApiError(HTTPStatus.BAD_REQUEST, "A JSON request body is required.")
        try:
            value = json.loads(self.rfile.read(length))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Request body must be valid JSON.") from exc
        if not isinstance(value, dict):
            raise ApiError(HTTPStatus.BAD_REQUEST, "Request body must be a JSON object.")
        return value

    def _dispatch(self, method: str) -> None:
        parsed = urlsplit(self.path)
        path = parsed.path
        service = self.server.service

        if method == "GET" and path == "/api/health":
            self._json(HTTPStatus.OK, {"status": "ok", "serverVersion": "2026.09.28.9"})
            return
        if method == "GET" and path == "/favicon.ico":
            self.send_response(HTTPStatus.NO_CONTENT)
            self.send_header("Cache-Control", "public, max-age=86400")
            self.end_headers()
            return
        if method == "GET" and path == "/api/config/default":
            self._json(HTTPStatus.OK, service.load_default_config())
            return
        if method == "POST" and path == "/api/auth/login":
            body = self._body()
            with service.operation_lock:
                service.require_setup_idle()
                service.sign_in(str(body.get("tenantId", "")))
            self._json(HTTPStatus.OK, {"status": "signed-in"})
            return
        if method == "GET" and path == "/api/estate":
            self._json(HTTPStatus.OK, discover_estate(service.repository_root))
            return
        if method == "POST" and path == "/api/validate":
            body = self._body()
            with service.operation_lock:
                service.require_setup_idle()
                self._json(HTTPStatus.OK, service.validate(body.get("config"), body.get("approvals") or {}))
            return
        if method == "POST" and path == "/api/validations":
            body = self._body()
            with service.operation_lock:
                service.require_setup_idle()
                self._json(HTTPStatus.ACCEPTED, service.start_validation(body.get("config"), body.get("approvals") or {}))
            return
        match = re.fullmatch(r"/api/validations/([a-f0-9]{32})", path)
        if method == "GET" and match:
            self._json(HTTPStatus.OK, service.validation_status(match.group(1)))
            return
        if method == "POST" and path == "/api/runs":
            body = self._body()
            with service.operation_lock:
                service.require_setup_idle()
                run_id = service.start_run(body.get("config"), body.get("approvals") or {})
            self._json(HTTPStatus.ACCEPTED, {"runId": run_id})
            return
        if method == "GET" and path == "/api/runs":
            self._json(HTTPStatus.OK, service.list_runs())
            return
        if path == "/api/permission-setups" and method == "POST":
            self._permission_request_guard()
            body = self._body()
            with service.operation_lock:
                service.require_assessment_idle()
                result = service.permission_setup.preview(body.get("workspace"), body.get("approveSqlWarehouseAutoStart"))
            self._json(HTTPStatus.ACCEPTED, result)
            return
        setup_match = re.fullmatch(r"/api/permission-setups/([a-f0-9]{32})(/apply)?", path)
        if setup_match and method in {"GET", "POST"}:
            self._permission_request_guard(write=method == "POST")
            if method == "GET" and not setup_match.group(2):
                self._json(HTTPStatus.OK, service.permission_setup.snapshot(setup_match.group(1)))
                return
            if method == "POST" and setup_match.group(2):
                body = self._body()
                with service.operation_lock:
                    service.require_assessment_idle()
                    result = service.permission_setup.apply(setup_match.group(1), body.get("confirmed"),
                                                            body.get("principal"), body.get("approveSqlWarehouseAutoStart"))
                self._json(HTTPStatus.ACCEPTED, result)
                return
        if method == "POST" and path == "/api/snapshots/delete":
            if self.headers.get_content_type() != "application/json":
                raise ApiError(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "Snapshot deletion requires application/json.")
            origin = self.headers.get("Origin")
            if origin is not None and origin != f"http://{self.headers.get('Host')}":
                raise ApiError(HTTPStatus.FORBIDDEN, "Cross-origin snapshot deletion is not permitted.")
            body = self._body()
            self._json(HTTPStatus.OK, service.delete_snapshots(body.get("runIds"), body.get("confirmed")))
            return

        match = re.fullmatch(r"/api/runs/([^/]+)/events", path)
        if method == "GET" and match:
            query = urlsplit(self.path).query
            after = 0
            for item in query.split("&"):
                if item.startswith("after="):
                    try:
                        after = max(0, int(item.split("=", 1)[1]))
                    except ValueError as exc:
                        raise ApiError(HTTPStatus.BAD_REQUEST, "after must be a non-negative integer.") from exc
            self._json(HTTPStatus.OK, service.events(unquote(match.group(1)), after))
            return
        match = re.fullmatch(r"/api/runs/([^/]+)/results", path)
        if method == "GET" and match:
            run_root = resolve_run_root(service.output_root, unquote(match.group(1)))
            self._json(HTTPStatus.OK, map_results(run_root))
            return
        match = re.fullmatch(r"/api/runs/([^/]+)/review", path)
        if method == "PUT" and match:
            body = self._body()
            service.save_review(unquote(match.group(1)), body.get("entries"))
            self._json(HTTPStatus.OK, {})
            return
        match = re.fullmatch(r"/api/runs/([^/]+)/artifacts/(.+)", path)
        if method == "GET" and match:
            run_root = resolve_run_root(service.output_root, unquote(match.group(1)))
            relative = unquote(match.group(2))
            artifact = resolve_artifact(run_root, relative)
            try:
                content = artifact.read_text(encoding="utf-8-sig")
            except (OSError, UnicodeDecodeError) as exc:
                raise ApiError(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, f"Artifact is not UTF-8 text: {exc}") from exc
            mime_type = mimetypes.guess_type(artifact.name)[0] or "text/plain"
            self._json(
                HTTPStatus.OK,
                {
                    "relativePath": artifact.relative_to(run_root).as_posix(),
                    "mimeType": mime_type,
                    "content": content,
                },
            )
            return
        match = re.fullmatch(r"/api/runs/([^/]+)", path)
        if method == "DELETE" and match:
            service.cancel(unquote(match.group(1)))
            self._json(HTTPStatus.ACCEPTED, {})
            return
        if path.startswith("/api/"):
            raise ApiError(HTTPStatus.NOT_FOUND, "API route not found.")
        if method != "GET":
            raise ApiError(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
        if path not in {"/", "/index.html"}:
            raise ApiError(HTTPStatus.NOT_FOUND, "Resource not found.")
        if not service.dist_index.is_file():
            raise ApiError(HTTPStatus.NOT_FOUND, "UI bundle not found. Build ui\\dist\\index.html first.")
        content = service.dist_index.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def _permission_request_guard(self, write: bool = True) -> None:
        host = self.headers.get("Host")
        allowed = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
        if self.client_address[0] not in {"127.0.0.1", "::1"} or host not in allowed:
            raise ApiError(HTTPStatus.FORBIDDEN, "Permission setup is restricted to the loopback application origin.")
        origin = self.headers.get("Origin")
        if origin is not None and origin != f"http://{host}":
            raise ApiError(HTTPStatus.FORBIDDEN, "Cross-origin permission setup is not permitted.")
        if write and self.headers.get_content_type() != "application/json":
            raise ApiError(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "Permission setup requires application/json.")

    def _handle(self, method: str) -> None:
        try:
            self._dispatch(method)
        except (ApiError, SetupError) as exc:
            self._json(exc.status, {"error": str(exc)})
        except Exception as exc:
            self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})

    def do_GET(self) -> None:
        self._handle("GET")

    def do_POST(self) -> None:
        self._handle("POST")

    def do_PUT(self) -> None:
        self._handle("PUT")

    def do_DELETE(self) -> None:
        self._handle("DELETE")


class AssessmentHttpServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = os.name != "nt"

    def server_bind(self) -> None:
        if os.name == "nt":
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()

    def __init__(self, address: tuple[str, int], service: AssessmentService) -> None:
        super().__init__(address, AssessmentRequestHandler)
        self.service = service


def parse_args() -> argparse.Namespace:
    ui_root = Path(__file__).resolve().parents[1]
    repository_root = ui_root.parent
    parser = argparse.ArgumentParser(description="Serve the Azure Databricks assessment UI and local API.")
    parser.add_argument("--host", default="127.0.0.1", choices=("127.0.0.1", "::1", "localhost"))
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--output-root", type=Path, default=repository_root / "assessment" / "output")
    parser.add_argument("--dist-index", type=Path, default=ui_root / "dist" / "index.html")
    parser.add_argument("--powershell", default="pwsh")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ui_root = Path(__file__).resolve().parents[1]
    repository_root = ui_root.parent
    service = AssessmentService(repository_root, args.output_root, args.dist_index, args.powershell)
    server = AssessmentHttpServer((args.host, args.port), service)
    print(f"Assessment UI: http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
