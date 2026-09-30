"""Local evidence operations and explicitly authorized, non-destructive publication."""
from __future__ import annotations

import csv
import io
import json
import re
import shutil
import stat
import sys
import uuid
from datetime import datetime, timezone
from collections import defaultdict
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from assessment.model.capabilities import ASSETS, MODULES, digest, number, timestamp, validate_options, commitment_scenario, percentile
from assessment.model.core import DATASET_MAP
from assessment.pipeline.run_assessment import run as run_pipeline

IMPORT_DATASETS = {"clusters", "node-timeline", "jobs", "job-runs", "query-history", "sql-warehouses",
                   "workspace-settings", "metastore-assignment", "commitment-demand", *ASSETS}


def load(path: Path, default=None):
    return json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else default


def save(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + "." + uuid.uuid4().hex + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False), encoding="utf-8")
    temporary.replace(path)


def summary(run_root: Path) -> dict | None:
    data = load(run_root / "capability-analysis.json")
    if data is None:
        return None
    return {key: value for key, value in data.items() if key not in ("datasets", "findings")}


def scoped_rows(rows: list[dict], request: dict) -> list[dict]:
    for field in ("workspaceId", "subscriptionId", "resourceGroup"):
        selection = request.get(field, [])
        if not isinstance(selection, list) or any(not isinstance(v, str) for v in selection):
            raise ValueError("Scope filters must be string arrays.")
        if selection:
            rows = [row for row in rows if row.get(field) in selection]
    return rows


def dataset_page(run_root: Path, module: str, request: dict) -> dict:
    if module not in MODULES:
        raise ValueError("Unknown capability dataset.")
    data = load(run_root / "capability-analysis.json")
    if data is None:
        raise ValueError("This snapshot predates capability analysis. Re-analyze saved evidence to create a child snapshot.")
    rows = scoped_rows(data["datasets"][module], request)
    search = str(request.get("search", "")).lower()[:200]
    if search:
        rows = [r for r in rows if search in json.dumps({k: v for k, v in r.items() if k != "detail"}).lower()]
    group_by = request.get("groupBy")
    if group_by:
        if module != "queries" or group_by not in ("warehouseId", "user"):
            raise ValueError("Only query warehouse/user grouping is supported.")
        groups = defaultdict(list)
        for row in rows:
            groups[row["workspaceId"], str(row.get(group_by) or "Unattributed")].append(row)
        grouped = []
        for (ws, identity), queries in groups.items():
            grouped.append({**queries[0], "key": digest([ws, group_by, identity]), "name": identity, "status": "Saved query summary",
                            "queryCount": len(queries), "failedQueries": sum(q["status"] == "FAILED" for q in queries),
                            "p95DurationSeconds": percentile([q["durationSeconds"] for q in queries if q["durationSeconds"] is not None]),
                            "p95QueueSeconds": percentile([q["queueSeconds"] for q in queries if q["queueSeconds"] is not None]),
                            "detail": {"scope": "Full matching saved dataset, not just this page", "queryIds": [q["resourceId"] for q in queries]}})
        rows = grouped
    sort = str(request.get("sort", "name"))
    rows = sorted(rows, key=lambda r: (r.get(sort) is None, number(r.get(sort)) if number(r.get(sort)) is not None else str(r.get(sort, "")).lower())
                  if all(r.get(sort) is None or number(r.get(sort)) is not None for r in rows)
                  else (r.get(sort) is None, str(r.get(sort, "")).lower()), reverse=request.get("descending") is True)
    offset, limit = request.get("offset", 0), request.get("limit", 50)
    if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 200:
        raise ValueError("Offset must be nonnegative and page size between 1 and 200.")
    return {"rows": rows[offset:offset + limit], "total": len(rows), "offset": offset, "limit": limit,
            "coverage": data["coverage"][module], "ruleVersion": data["ruleVersion"]}


def protect(value, salt: str, key: str = "", sensitive: bool = False):
    lowered = key.lower()
    if any(word in lowered for word in ("statement_text", "query_text", "querytext", "password", "access_token", "accesstoken", "secret", "credential", "private_key",
                                        "spark_env_vars", "base_parameters", "notebook_params", "python_params", "job_parameters")):
        return None
    sensitive = sensitive or any(word in lowered for word in ("user", "owner", "email", "identity", "path", "url", "executed_by"))
    if isinstance(value, dict):
        return {k: protect(v, salt, k, sensitive) for k, v in value.items()}
    if isinstance(value, list):
        return [protect(v, salt, key, sensitive) for v in value]
    if isinstance(value, str) and sensitive:
        return "protected:" + digest([salt, value])
    return value


def parse_import(request: dict) -> tuple[dict, dict, list]:
    ws = str(request.get("workspaceId", "")).strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", ws):
        raise ValueError("Provide a workspace ID (letters, digits, hyphens or underscores).")
    start, end = timestamp(request.get("startUtc")), timestamp(request.get("endUtc"))
    if start is None or end is None or not start < end:
        raise ValueError("A valid declared start/end window is required.")
    files = request.get("files")
    if not isinstance(files, list) or not files or len(files) > 30:
        raise ValueError("Select 1 to 30 CSV/JSON evidence files.")
    datasets: dict[str, list] = {}
    inventory = []
    for entry in files:
        if not isinstance(entry, dict):
            raise ValueError("Each file must be an object with name, dataset and content.")
        name, kind, content = entry.get("name"), entry.get("dataset"), entry.get("content")
        if kind not in IMPORT_DATASETS or not isinstance(content, str):
            raise ValueError("Each file requires a supported dataset and text content.")
        if kind in datasets:
            raise ValueError(f"Select only one file per dataset: {kind}.")
        if str(name).lower().endswith(".csv"):
            records = list(csv.DictReader(io.StringIO(content)))
            for record in records:
                for key, value in record.items():
                    if isinstance(value, str) and value.startswith(("{", "[")):
                        record[key] = json.loads(value)
        else:
            records = json.loads(content)
            if isinstance(records, dict):
                records = records.get("items", records.get("rows", records.get("data")))
        if not isinstance(records, list) or any(not isinstance(r, dict) for r in records) or len(records) > 100000:
            raise ValueError(f"{name}: expected an array of at most 100,000 records.")
        required = {"clusters": ("cluster_id",), "node-timeline": ("cluster_id", "start_time", "end_time"),
                    "jobs": ("job_id",), "job-runs": ("job_id", "start_time"), "query-history": ("start_time",),
                    "commitment-demand": ("hour", "region", "sku", "currency", "eligibleNodes", "coveredNodes", "onDemandHourlyRate", "commitmentHourlyRate")}
        for row in records:
            missing = [field for field in required.get(kind, ()) if row.get(field) in (None, "")]
            if missing:
                raise ValueError(f"{name}: unsupported record shape; missing {', '.join(missing)}. Aggregate scanner summaries are not raw timelines.")
            declared = str(row.get("workspace_id") or row.get("workspaceId") or ws)
            if declared != ws:
                raise ValueError(f"{name}: workspace mismatch. Import different workspaces as separate snapshots.")
            row["workspace_id"] = ws
        datasets[kind] = records
        inventory.append({"name": Path(str(name)).name, "dataset": kind, "rows": len(records), "sha256": digest(content),
                          "coverage": "Declared scope/window; completeness not established"})
    config = {"customerId": "imported-evidence", "assessmentId": "import", "evidenceOrigin": "imported",
              "azure": {"tenantId": "", "subscriptions": [], "resourceGroups": ["imported"], "costBasis": ["ActualCost"], "currency": "USD"},
              "databricks": {"workspaces": [{"workspaceId": ws, "name": str(request.get("workspaceName") or ws),
                                           "resourceGroup": "imported", "workspaceUrl": "", "include": True}]},
              "analysis": {"startUtc": request["startUtc"], "endUtc": request["endUtc"], "timeZone": "UTC"},
              "thresholds": {}, "redaction": {"hashIdentities": True, "omitQueryText": True},
              "capabilities": validate_options(request.get("capabilities"))}
    return config, datasets, inventory


def import_evidence(output_root: Path, request: dict, preview: bool = False) -> dict:
    config, datasets, inventory = parse_import(request)
    if preview:
        return {"files": inventory, "origin": "imported", "redaction": "Identities/paths protected, query text omitted. No cloud access.",
                "datasets": list(datasets), "costAvailable": False}
    if request.get("confirmed") is not True:
        raise ValueError("Confirm the scope, declared time window and redaction before import.")
    run_id = "import-" + uuid.uuid4().hex
    root = output_root / run_id
    root.mkdir()
    config["assessmentId"] = run_id
    now = datetime.now(timezone.utc).isoformat()
    manifest = {"runId": run_id, "customerId": config["customerId"], "assessmentId": run_id, "schemaVersion": "1.0",
                "toolkitVersion": "capabilities-1.0", "status": "partial", "startedAtUtc": now, "completedAtUtc": now,
                "analysisWindow": config["analysis"], "scope": {"subscriptionIds": [], "resourceGroups": ["imported"]},
                "evidenceOrigin": "imported", "costAvailable": False}
    save(root / "assessment-manifest.json", manifest)
    save(root / "assessment-config.json", config)
    save(root / "import-provenance.json", inventory)
    salt = uuid.uuid4().hex
    for kind, records in datasets.items():
        save(root / "raw" / "databricks" / str(config["databricks"]["workspaces"][0]["workspaceId"]) / f"{kind}.json", protect(records, salt))
    save(root / "collection-status.json", [{"name": f"Imported {kind}", "status": "partial", "itemCount": len(records), "outputs": [],
         "limitations": ["Imported evidence; completeness and original extraction window are not established."], "error": ""} for kind, records in datasets.items()])
    try:
        run_pipeline(root / "assessment-config.json", root)
    except (ValueError, OSError, TypeError, KeyError) as exc:
        manifest.update(status="failed", error=str(exc))
        save(root / "assessment-manifest.json", manifest)
        raise
    return {"runId": run_id}


def reanalyze(output_root: Path, parent: Path, options: dict) -> dict:
    if not (parent / "raw").is_dir():
        raise ValueError("Saved raw evidence is unavailable. Re-analysis cannot recreate missing inputs.")
    if any(p.is_symlink() or getattr(p.lstat(), "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
           for p in [parent / "raw", *(parent / "raw").rglob("*")]):
        raise ValueError("Linked raw evidence is not eligible for local re-analysis.")
    config = load(parent / "assessment-config.json")
    config["capabilities"] = validate_options(options)
    run_id = "analysis-" + uuid.uuid4().hex
    root = output_root / run_id
    root.mkdir()
    shutil.copytree(parent / "raw", root / "raw")
    config["assessmentId"] = run_id
    save(root / "assessment-config.json", config)
    manifest = load(parent / "assessment-manifest.json")
    manifest.update(runId=run_id, assessmentId=run_id, parentRunId=parent.name, analyzedAtUtc=datetime.now(timezone.utc).isoformat())
    save(root / "assessment-manifest.json", manifest)
    if (parent / "collection-status.json").exists():
        shutil.copyfile(parent / "collection-status.json", root / "collection-status.json")
    if (parent / "import-provenance.json").exists():
        shutil.copyfile(parent / "import-provenance.json", root / "import-provenance.json")
    try:
        run_pipeline(root / "assessment-config.json", root)
    except (ValueError, OSError, TypeError, KeyError) as exc:
        manifest.update(status="failed", error=str(exc))
        save(root / "assessment-manifest.json", manifest)
        raise
    return {"runId": run_id}


def workbook(run_root: Path, requested: list[str]) -> str:
    analysis = load(run_root / "capability-analysis.json")
    if not analysis:
        raise ValueError("Re-analyze saved evidence before generating a capability workbook.")
    sheets = {"Summary": [dict(runId=run_root.name, origin=analysis["origin"], ruleVersion=analysis["ruleVersion"],
                              source="capability-analysis.json", limitations="; ".join(analysis["limitations"]))],
              "Rules": [analysis["options"]["rules"]],
              "Quality": [{"dataset": k, **v} for k, v in analysis["coverage"].items()],
              "Review": load(run_root / ".ui-review.json", []),
              "Findings": load(run_root / "optimization-candidates.json", {}).get("findings", [])}
    for name in requested:
        if name not in MODULES:
            raise ValueError("Unknown workbook sheet.")
        sheets[name.title()] = analysis["datasets"][name]
    revision = digest(sheets)
    relative = f"reports/capability-workbook-{revision}.xlsx"
    path = run_root / relative
    path.parent.mkdir(exist_ok=True)
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    relationships = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    def cell(value, header=False) -> str:
        style = ' s="1"' if header else ""
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return f"<c{style}><v>{value}</v></c>"
        text = "Not available" if value is None else str(value)
        if len(text) > 32767:
            raise ValueError("A workbook cell exceeds Excel's limit. Export JSON evidence instead.")
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
        return f'<c{style} t="inlineStr"><is><t xml:space="preserve">{escape(text)}</t></is></c>'
    buffer = io.BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        overrides = []
        for i, (name, data) in enumerate(sheets.items(), 1):
            if len(data) >= 1048576:
                raise ValueError("Workbook exceeds Excel row limit; export JSON instead.")
            # Detailed arrays stay in the canonical JSON; flat rows retain evidence links.
            flat = [{k: v for k, v in r.items() if k != "detail"} for r in data] or [{"status": "No rows / evidence unavailable"}]
            keys = list(dict.fromkeys(k for row in flat for k in row))
            xml_rows = ["<row>" + "".join(cell(k, header=True) for k in keys) + "</row>"]
            xml_rows.extend("<row>" + "".join(cell(row.get(k)) for k in keys) + "</row>" for row in flat)
            archive.writestr(f"xl/worksheets/sheet{i}.xml", f'<worksheet xmlns="{ns}"><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" state="frozen"/></sheetView></sheetViews><sheetFormatPr defaultColWidth="24"/><sheetData>{"".join(xml_rows)}</sheetData></worksheet>')
            overrides.append(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>')
        archive.writestr("xl/workbook.xml", f'<workbook xmlns="{ns}" xmlns:r="{relationships}"><sheets>' + "".join(
            f'<sheet name="{escape(name)}" sheetId="{i}" r:id="rId{i}"/>' for i, name in enumerate(sheets, 1)) + "</sheets></workbook>")
        archive.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' + "".join(
            f'<Relationship Id="rId{i}" Type="{relationships}/worksheet" Target="worksheets/sheet{i}.xml"/>' for i in range(1, len(sheets) + 1)) + f'<Relationship Id="styles" Type="{relationships}/styles" Target="styles.xml"/></Relationships>')
        archive.writestr("xl/styles.xml", f'<styleSheet xmlns="{ns}"><fonts count="2"><font><sz val="11"/><name val="Arial"/></font><font><b/><sz val="11"/><name val="Arial"/></font></fonts><fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>')
        overrides.append('<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>')
        archive.writestr("_rels/.rels", f'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="{relationships}/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        archive.writestr("[Content_Types].xml", '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>' + "".join(overrides) + "</Types>")
    temporary = path.with_suffix("." + uuid.uuid4().hex + ".tmp")
    try:
        temporary.write_bytes(buffer.getvalue())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return relative


def dashboard_payload(run_root: Path) -> dict:
    analysis = load(run_root / "capability-analysis.json")
    if not analysis:
        raise ValueError("Capability evidence required before dashboard publication.")
    # Only summary counts are published: no identities, query text or raw artifacts.
    rows = [{"capability": k, "rows": v["rows"], "coverage": v["status"], "snapshot": run_root.name} for k, v in analysis["coverage"].items()]
    sql = " UNION ALL ".join("SELECT " + ", ".join("'" + str(v).replace("'", "''") + "' AS `" + k + "`" for k, v in row.items()) for row in rows)
    return {"datasets": [{"name": "coverage", "displayName": "Snapshot capability coverage", "query": sql}],
            "pages": [{"name": "overview", "displayName": "Assessment coverage", "layout": [{
                "widget": {"name": "coverage_table", "queries": [{"name": "main_query", "query": {"datasetName": "coverage", "fields": [{"name": k, "expression": f"`{k}`"} for k in rows[0]]}}],
                           "spec": {"version": 2, "widgetType": "table", "encodings": {"columns": [{"fieldName": k, "displayName": k, "type": "string"} for k in rows[0]]}}},
                "position": {"x": 0, "y": 0, "width": 6, "height": 6}}]}]}


def publish(run_root: Path, request: dict, client_factory) -> dict:
    from permission_setup import workspace_host
    host = workspace_host(request.get("workspaceUrl"))
    warehouse = str(request.get("warehouseId", ""))
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", warehouse):
        raise ValueError("A destination warehouse ID is required.")
    payload = dashboard_payload(run_root)
    plan = {"workspaceUrl": host, "warehouseId": warehouse, "snapshot": run_root.name,
            "dataset": "Coverage counts only; no raw evidence or customer identities",
            "operations": ["Create a new Lakeview dashboard", "Publish with viewer credentials (embed_credentials=false)"],
            "createsTables": False, "dropsObjects": False, "serializedDashboard": payload}
    confirmation = digest(plan)
    if request.get("preview") is True:
        return {"plan": plan, "confirmation": confirmation}
    if request.get("confirmed") is not True or request.get("approveCompute") is not True or request.get("confirmation") != confirmation:
        raise ValueError("Preview and explicitly approve this exact publication destination, snapshot and compute usage.")
    audit_path = run_root / "reports" / f"publication-{confirmation}.json"
    if audit_path.exists():
        raise ValueError("A publication for this plan was already attempted. Inspect its audit and remote outcome; automatic retries are forbidden.")
    audit = {"plan": plan, "status": "creating", "createdAtUtc": datetime.now(timezone.utc).isoformat(), "dashboardId": None}
    save(audit_path, audit)
    try:
        client = client_factory(host, warehouse)
        created = client.request("POST", "/api/2.0/lakeview/dashboards", {"display_name": f"Assessment {run_root.name}",
                                 "warehouse_id": warehouse, "serialized_dashboard": json.dumps(payload)})
        dashboard_id = created.get("dashboard_id")
        if not isinstance(dashboard_id, str) or not re.fullmatch(r"[a-zA-Z0-9_-]+", dashboard_id):
            raise ValueError("Creation response lacks a valid dashboard ID; inspect workspace before retrying.")
        audit.update(status="publishing", dashboardId=dashboard_id)
        save(audit_path, audit)
        client.request("POST", f"/api/2.0/lakeview/dashboards/{dashboard_id}/published", {"warehouse_id": warehouse, "embed_credentials": False})
        client.request("GET", f"/api/2.0/lakeview/dashboards/{dashboard_id}/published")
        audit.update(status="published", url=f"https://{host}/dashboardsv3/{dashboard_id}/published")
    except Exception as exc:
        audit.update(status="failed_or_unknown", error=str(exc))
        save(audit_path, audit)
        raise
    save(audit_path, audit)
    return audit
