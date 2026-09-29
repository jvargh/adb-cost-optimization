from __future__ import annotations

import json
import logging
import re
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from http.client import HTTPException
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

PIPELINE_ACCESS_QUERY = "SELECT 1 FROM system.lakeflow.pipeline_update_timeline LIMIT 1"


class SetupError(Exception):
    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.status = status


class StatementFailed(SetupError):
    """Databricks explicitly reported a failed statement, not a transport uncertainty."""


def workspace_host(value: Any) -> str:
    host = str(value or "").removeprefix("https://").rstrip("/").lower()
    if not re.fullmatch(r"adb-\d+\.\d+\.azuredatabricks\.(net|us)", host):
        raise SetupError("A per-workspace Azure Databricks adb-... hostname is required.")
    return host


def grant_statements(principal: str) -> list[str]:
    if not principal or len(principal) > 256 or any(ord(char) < 32 for char in principal):
        raise SetupError("Databricks returned an invalid assessment identity.")
    quoted = "`" + principal.replace("`", "``") + "`"
    return [
        f"GRANT USE CATALOG ON CATALOG system TO {quoted}",
        f"GRANT USE SCHEMA ON SCHEMA system.lakeflow TO {quoted}",
        f"GRANT SELECT ON TABLE system.lakeflow.pipeline_update_timeline TO {quoted}",
    ]


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class DatabricksSetupClient:
    """Separate from the assessment collectors: only confirmed setup calls can issue GRANT."""

    def __init__(self, host: str, warehouse_id: str, token: str) -> None:
        self.host = workspace_host(host)
        self.warehouse_id = warehouse_id
        self.token = token
        self.opener = build_opener(NoRedirect())

    def request(self, method: str, path: str, body: dict | None = None) -> dict:
        data = json.dumps(body).encode() if body is not None else None
        request = Request(f"https://{self.host}{path}", data=data, method=method, headers={
            "Authorization": f"Bearer {self.token}", "Content-Type": "application/json",
        })
        try:
            with self.opener.open(request, timeout=30) as response:
                payload = json.loads(response.read(1024 * 1024))
        except HTTPError as exc:
            try:
                detail = json.loads(exc.read(16384)).get("message", exc.reason)
            except (ValueError, AttributeError):
                detail = exc.reason
            raise SetupError(f"Databricks HTTP {exc.code}: {detail}. An authorized administrator may be required.", 502) from exc
        except (URLError, TimeoutError, ValueError, HTTPException) as exc:
            raise SetupError(f"Databricks setup request failed: {exc}. Query outcome may be unknown; inspect access before retrying.", 502) from exc
        if not isinstance(payload, dict):
            raise SetupError("Databricks returned an invalid statement response.", 502)
        return payload

    def query(self, statement: str) -> dict:
        deadline = time.monotonic() + 180
        response = self.request("POST", "/api/2.0/sql/statements", {
            "warehouse_id": self.warehouse_id, "statement": statement,
            "wait_timeout": "10s", "on_wait_timeout": "CONTINUE",
            "disposition": "INLINE", "format": "JSON_ARRAY",
        })
        while True:
            status = response.get("status") or {}
            if not isinstance(status, dict):
                raise SetupError("Databricks returned an invalid statement status.", 502)
            state = status.get("state")
            if state == "SUCCEEDED":
                return response
            if state not in {"PENDING", "RUNNING"}:
                error = status.get("error")
                detail = error.get("message") if isinstance(error, dict) else None
                detail = detail or f"Unexpected statement state: {state}"
                error_type = StatementFailed if state == "FAILED" else SetupError
                raise error_type(f"{detail} No administrator credentials or elevated roles are acquired by this tool.", 502)
            if time.monotonic() >= deadline:
                raise SetupError("SQL statement timed out. It may still execute; inspect its status and permissions before retrying.", 504)
            statement_id = response.get("statement_id", "")
            if not isinstance(statement_id, str) or not re.fullmatch(r"[a-zA-Z0-9_-]+", statement_id):
                raise SetupError("Databricks returned an invalid statement ID.", 502)
            time.sleep(1)
            response = self.request("GET", f"/api/2.0/sql/statements/{statement_id}")

    def identity(self) -> str:
        response = self.query("SELECT current_user() AS assessment_principal")
        result = response.get("result")
        rows = result.get("data_array") if isinstance(result, dict) else None
        if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], list) or len(rows[0]) != 1 or not isinstance(rows[0][0], str):
            raise SetupError("Could not verify exactly one Databricks assessment identity.", 502)
        grant_statements(rows[0][0])
        return rows[0][0]


class PermissionSetupService:
    def __init__(self, client_factory: Callable[[str, str], DatabricksSetupClient], audit_root: Path) -> None:
        self.client_factory = client_factory
        self.audit_root = audit_root
        self.lock = threading.RLock()
        self.jobs: dict[str, dict] = {}

    def busy(self) -> bool:
        with self.lock:
            return any(job["status"] in {"verifying", "applying"} for job in self.jobs.values())

    def snapshot(self, setup_id: str) -> dict:
        with self.lock:
            if setup_id not in self.jobs:
                self.jobs[setup_id] = self._restore(setup_id)
            return json.loads(json.dumps(self.jobs[setup_id]))

    def _restore(self, setup_id: str) -> dict:
        if not re.fullmatch(r"[a-f0-9]{32}", setup_id):
            raise SetupError("Invalid permission setup ID.")
        path = self.audit_root / f"{setup_id}.json"
        try:
            job = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise SetupError("Permission setup is unavailable; the host may have restarted before this preview was saved.", 404) from exc
        except (OSError, ValueError) as exc:
            logging.error("Could not restore permission setup %s: %s", setup_id, exc)
            raise SetupError("Could not read the saved setup audit. Inspect it and actual permissions before retrying.", 500) from exc
        states = {"verifying", "awaiting_confirmation", "applying", "completed", "failed", "unknown"}
        if (not isinstance(job, dict) or job.get("setupId") != setup_id
                or not isinstance(job.get("status"), str) or job["status"] not in states
                or not isinstance(job.get("grants"), list)
                or any(not isinstance(grant, dict) or not isinstance(grant.get("statement"), str)
                       or grant.get("status") not in ("not_attempted", "submitted", "applied", "failed")
                       for grant in job["grants"])
                or any(not isinstance(job.get(key), str) for key in
                       ("workspaceId", "workspaceName", "workspaceUrl", "warehouseId", "createdAtUtc"))):
            logging.error("Invalid saved permission setup audit: %s", setup_id)
            raise SetupError("The saved setup audit is invalid. Inspect actual permissions before retrying.", 500)
        if job["status"] in {"verifying", "awaiting_confirmation"}:
            job.update(status="failed", accessVerified=False,
                       error="The host restarted. This identity preview cannot be reused; it submitted no grants. Verify the identity again.")
        elif job["status"] == "applying":
            if any(grant["status"] in {"submitted", "applied"} for grant in job["grants"]):
                job.update(status="unknown", accessVerified=False,
                           error="The host restarted during permission setup. Saved grant steps are shown below, but the final outcome is unknown. Inspect actual permissions before retrying; nothing was resubmitted.")
            else:
                job.update(status="failed", accessVerified=False,
                           error="The host restarted before any grant was submitted. Verify a new identity preview before confirming again.")
        return job

    def preview(self, target: Any, approved: Any) -> dict:
        if approved is not True:
            raise SetupError("Explicit SQL Warehouse approval is required before identity verification; queries may incur DBU charges.")
        if not isinstance(target, dict) or target.get("include") is not True:
            raise SetupError("Select an included workspace for permission setup.")
        host = workspace_host(target.get("workspaceUrl"))
        warehouse_id = target.get("sqlWarehouseId")
        if not isinstance(warehouse_id, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,128}", warehouse_id):
            raise SetupError("A SQL Warehouse must be selected for permission setup.")
        with self.lock:
            if self.busy():
                raise SetupError("Another permission setup is running. Check its result before continuing.", 409)
            setup_id = uuid.uuid4().hex
            self.jobs[setup_id] = {
                "setupId": setup_id, "status": "verifying", "workspaceId": str(target.get("workspaceId", "")),
                "workspaceName": str(target.get("name") or host), "workspaceUrl": host, "warehouseId": warehouse_id,
                "principal": None, "grants": [], "error": None, "accessVerified": False,
                "accessCheckError": None,
                "expiresAtUtc": None, "createdAtUtc": datetime.now(timezone.utc).isoformat(),
            }
            try:
                self._audit(setup_id)
            except OSError as exc:
                self._update(setup_id, status="failed", error=f"Could not save the identity preview: {exc}. No queries were submitted.")
                raise SetupError(self.jobs[setup_id]["error"], 500) from exc
            threading.Thread(target=self._preview, args=(setup_id,), daemon=True).start()
            return self.snapshot(setup_id)

    def apply(self, setup_id: str, confirmed: Any, principal: Any, approved: Any) -> dict:
        with self.lock:
            job = self.snapshot(setup_id)
            if confirmed is not True or approved is not True or principal != job["principal"] or not principal:
                raise SetupError("Confirm the verified principal, the exact grants, and SQL Warehouse use before applying.")
            if self.busy() or job["status"] != "awaiting_confirmation":
                raise SetupError("This setup is not awaiting confirmation. An application cannot be submitted twice.", 409)
            if datetime.now(timezone.utc) >= datetime.fromisoformat(job["expiresAtUtc"]):
                self._update(setup_id, status="failed", error="The identity preview expired. No grants were submitted. Verify the identity again.")
                self._audit(setup_id)
                raise SetupError("The identity preview expired. Verify the identity again before confirming grants.", 409)
            self.jobs[setup_id]["status"] = "applying"
            threading.Thread(target=self._apply, args=(setup_id,), daemon=True).start()
            return self.snapshot(setup_id)

    def _update(self, setup_id: str, **values: Any) -> None:
        with self.lock:
            self.jobs[setup_id].update(json.loads(json.dumps(values)))

    def _audit(self, setup_id: str) -> None:
        self.audit_root.mkdir(parents=True, exist_ok=True)
        path = self.audit_root / f"{setup_id}.json"
        temporary = self.audit_root / f"{setup_id}.tmp"
        temporary.write_text(json.dumps(self.snapshot(setup_id), indent=2), encoding="utf-8")
        temporary.replace(path)

    def _preview(self, setup_id: str) -> None:
        try:
            job = self.snapshot(setup_id)
            client = self.client_factory(job["workspaceUrl"], job["warehouseId"])
            principal = client.identity()
            self._update(setup_id, principal=principal)
            access_error = None
            try:
                client.query(PIPELINE_ACCESS_QUERY)
            except StatementFailed as exc:
                if not re.search(r"\b(?:PERMISSION_DENIED|INSUFFICIENT_PERMISSIONS)\b", str(exc), re.IGNORECASE):
                    raise
                access_error = str(exc)
            accessible = access_error is None
            with self.lock:
                self._update(setup_id, status="completed" if accessible else "awaiting_confirmation",
                             accessVerified=accessible, accessCheckError=access_error,
                             grants=[] if accessible else [
                                 {"statement": sql, "status": "not_attempted"} for sql in grant_statements(principal)
                             ],
                             expiresAtUtc=None if accessible else (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat())
                try:
                    self._audit(setup_id)
                except OSError:
                    self._update(setup_id, status="failed")
                    raise
        except (SetupError, OSError, ValueError, TypeError) as exc:
            logging.warning("Permission setup access verification failed: %s", exc)
            self._update(setup_id, status="failed", accessVerified=False,
                         error=f"Read access could not be verified. No grants were submitted. {exc}")
            try:
                self._audit(setup_id)
            except OSError as audit_error:
                logging.error("Could not persist identity preview failure: %s", audit_error)

    def _apply(self, setup_id: str) -> None:
        job = self.snapshot(setup_id)
        grants = job["grants"]
        try:
            self._audit(setup_id)
            client = self.client_factory(job["workspaceUrl"], job["warehouseId"])
            if client.identity() != job["principal"]:
                raise SetupError("The signed-in Databricks identity changed. No grants were submitted. Verify a new preview.")
            for grant in grants:
                grant["status"] = "submitted"
                self._update(setup_id, grants=grants)
                try:
                    self._audit(setup_id)
                except OSError:
                    grant["status"] = "not_attempted"
                    self._update(setup_id, grants=grants)
                    raise
                try:
                    client.query(grant["statement"])
                except StatementFailed:
                    grant["status"] = "failed"
                    self._update(setup_id, grants=grants)
                    raise
                grant["status"] = "applied"
                self._update(setup_id, grants=grants)
                self._audit(setup_id)
            client.query(PIPELINE_ACCESS_QUERY)
            self._update(setup_id, status="completed", accessVerified=True)
        except (SetupError, OSError, ValueError, TypeError) as exc:
            logging.warning("Confirmed permission setup did not complete: %s", exc)
            applied = sum(grant["status"] == "applied" for grant in grants)
            unknown = any(grant["status"] == "submitted" for grant in grants)
            outcome = f"{applied} grant(s) were applied and remain in place." if applied else "No grants were confirmed applied."
            if unknown:
                outcome += " A submitted grant has an unknown outcome; inspect actual permissions before retrying."
            elif any(grant["status"] == "failed" for grant in grants):
                outcome += " Databricks rejected the failed grant. Later grants were not attempted. Ask an authorized Unity Catalog administrator to apply the required grants."
            self._update(setup_id, status="unknown" if unknown else "failed", error=f"{exc} {outcome} No automatic retry or rollback was attempted.")
        finally:
            try:
                self._audit(setup_id)
            except OSError as exc:
                logging.error("Could not persist permission setup audit: %s", exc)
                self._update(setup_id, status="unknown", error=f"Could not persist setup audit: {exc}. Inspect actual permissions before retrying.")
