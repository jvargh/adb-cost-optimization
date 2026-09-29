import io
import json
import subprocess
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from http.client import HTTPConnection, IncompleteRead
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import HTTPError

from assessment_server import AssessmentHttpServer, AssessmentService, ApiError, discover_warehouses, run_az, ValidationState
from permission_setup import DatabricksSetupClient, NoRedirect, PermissionSetupService, SetupError, StatementFailed, grant_statements

TARGET = {"include": True, "name": "fixture", "workspaceId": "123", "workspaceUrl": "adb-123.1.azuredatabricks.net", "sqlWarehouseId": "abc123"}


class PermissionSetupTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.client = Mock()
        self.client.identity.return_value = "assessment@example.test"
        self.factory = Mock(return_value=self.client)
        self.service = PermissionSetupService(self.factory, Path(self.temporary.name))
        self.thread = patch("permission_setup.threading.Thread").start()
        self.addCleanup(patch.stopall)

    def preview(self):
        self.client.query.side_effect = StatementFailed("INSUFFICIENT_PERMISSIONS: missing SELECT on pipeline_update_timeline")
        job = self.service.preview(TARGET, True)
        self.assertEqual(job["status"], "verifying")
        self.service._preview(job["setupId"])
        self.client.query.assert_called_once_with("SELECT 1 FROM system.lakeflow.pipeline_update_timeline LIMIT 1")
        self.client.query.reset_mock(side_effect=True)
        return self.service.snapshot(job["setupId"])

    def test_existing_read_access_completes_without_offering_or_submitting_grants(self):
        self.client.query.return_value = {"status": {"state": "SUCCEEDED"}, "result": {"data_array": []}}
        job = self.service.preview(TARGET, True)
        self.service._preview(job["setupId"])
        result = self.service.snapshot(job["setupId"])
        self.assertEqual(result["status"], "completed")
        self.assertTrue(result["accessVerified"])
        self.assertEqual(result["grants"], [])
        self.assertIsNone(result["expiresAtUtc"])
        self.client.query.assert_called_once_with("SELECT 1 FROM system.lakeflow.pipeline_update_timeline LIMIT 1")
        with self.assertRaises(SetupError):
            self.service.apply(job["setupId"], True, result["principal"], True)

    def test_only_a_permission_denial_offers_grants(self):
        for error in (StatementFailed("TABLE_OR_VIEW_NOT_FOUND"), SetupError("SQL statement timed out")):
            with self.subTest(error=str(error)):
                self.client.query.side_effect = error
                job = self.service.preview(TARGET, True)
                self.service._preview(job["setupId"])
                result = self.service.snapshot(job["setupId"])
                self.assertEqual(result["status"], "failed")
                self.assertFalse(result["accessVerified"])
                self.assertEqual(result["grants"], [])
                self.assertIn(str(error), result["error"])

    def test_preview_never_grants_and_requires_warehouse_consent(self):
        for consent in (False, None, "true", 1):
            with self.assertRaises(SetupError):
                self.service.preview(TARGET, consent)
        job = self.preview()
        self.assertEqual(job["status"], "awaiting_confirmation")
        self.assertEqual([grant["statement"] for grant in job["grants"]], grant_statements("assessment@example.test"))
        self.client.query.assert_not_called()

    def test_only_explicit_matching_identity_confirmation_can_apply(self):
        job = self.preview()
        for confirmed, principal, approved in ((False, job["principal"], True), ("true", job["principal"], True), (True, "other@example.test", True), (True, job["principal"], False)):
            with self.assertRaises(SetupError):
                self.service.apply(job["setupId"], confirmed, principal, approved)
        self.client.query.assert_not_called()

    def test_expired_preview_and_duplicate_application_are_rejected(self):
        job = self.preview()
        self.service.jobs[job["setupId"]]["expiresAtUtc"] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        with self.assertRaisesRegex(SetupError, "expired"):
            self.service.apply(job["setupId"], True, job["principal"], True)
        self.assertEqual(self.service.snapshot(job["setupId"])["status"], "failed")
        job = self.preview()
        self.service.apply(job["setupId"], True, job["principal"], True)
        with self.assertRaisesRegex(SetupError, "twice"):
            self.service.apply(job["setupId"], True, job["principal"], True)

    def test_identity_change_aborts_before_any_grant(self):
        job = self.preview()
        self.client.identity.return_value = "different@example.test"
        self.service.apply(job["setupId"], True, job["principal"], True)
        self.service._apply(job["setupId"])
        self.client.query.assert_not_called()
        self.assertIn("identity changed", self.service.snapshot(job["setupId"])["error"])

    def test_exact_grants_and_read_only_verification_are_persisted_without_credentials(self):
        job = self.preview()
        self.service.apply(job["setupId"], True, job["principal"], True)
        self.service._apply(job["setupId"])
        calls = [call.args[0] for call in self.client.query.call_args_list]
        self.assertEqual(calls, grant_statements(job["principal"]) + ["SELECT 1 FROM system.lakeflow.pipeline_update_timeline LIMIT 1"])
        result = self.service.snapshot(job["setupId"])
        self.assertEqual(result["status"], "completed")
        self.assertTrue(result["accessVerified"])
        audit = json.loads((Path(self.temporary.name) / f"{job['setupId']}.json").read_text())
        self.assertEqual(audit, result)
        self.assertNotIn("accessToken", json.dumps(audit))
        self.assertNotIn("Authorization", json.dumps(audit))

    def test_partial_failure_stops_without_rollback_retry_or_success(self):
        job = self.preview()
        self.client.query.side_effect = [{}, StatementFailed("PERMISSION_DENIED")]
        self.service.apply(job["setupId"], True, job["principal"], True)
        self.service._apply(job["setupId"])
        result = self.service.snapshot(job["setupId"])
        self.assertEqual(result["status"], "failed")
        self.assertFalse(result["accessVerified"])
        self.assertEqual([grant["status"] for grant in result["grants"]], ["applied", "failed", "not_attempted"])
        self.assertEqual(self.client.query.call_count, 2)
        self.assertIn("1 grant(s) were applied and remain", result["error"])
        self.assertNotIn("unknown outcome", result["error"])

    def test_audit_failure_prevents_grant_submission(self):
        job = self.preview()
        with patch.object(self.service, "_audit", side_effect=OSError("disk unavailable")):
            self.service.apply(job["setupId"], True, job["principal"], True)
            self.service._apply(job["setupId"])
        self.client.query.assert_not_called()
        self.assertEqual(self.service.snapshot(job["setupId"])["status"], "unknown")

    def test_denied_first_grant_stops_with_no_unknown_or_later_statements(self):
        job = self.preview()
        self.client.query.side_effect = StatementFailed("PERMISSION_DENIED: User does not have MANAGE on Catalog 'system'.")
        self.service.apply(job["setupId"], True, job["principal"], True)
        self.service._apply(job["setupId"])
        result = self.service.snapshot(job["setupId"])
        self.assertEqual(result["status"], "failed")
        self.assertEqual([grant["status"] for grant in result["grants"]], ["failed", "not_attempted", "not_attempted"])
        self.assertEqual(self.client.query.call_count, 1)
        self.assertIn("No grants were confirmed applied", result["error"])
        self.assertIn("authorized Unity Catalog administrator", result["error"])
        self.assertNotIn("unknown outcome", result["error"])

    def test_transport_loss_remains_unknown_and_is_never_retried(self):
        job = self.preview()
        self.client.query.side_effect = SetupError("Connection lost")
        self.service.apply(job["setupId"], True, job["principal"], True)
        self.service._apply(job["setupId"])
        result = self.service.snapshot(job["setupId"])
        self.assertEqual(result["status"], "unknown")
        self.assertEqual(result["grants"][0]["status"], "submitted")
        self.assertEqual(self.client.query.call_count, 1)
        with self.assertRaises(SetupError):
            self.service.apply(job["setupId"], True, job["principal"], True)

    def test_restart_invalidates_saved_preview_without_queries_or_grants(self):
        job = self.preview()
        restored = PermissionSetupService(self.factory, Path(self.temporary.name))
        self.factory.reset_mock()
        result = restored.snapshot(job["setupId"])
        self.assertEqual(result["status"], "failed")
        self.assertIn("preview cannot be reused", result["error"])
        with self.assertRaises(SetupError):
            restored.apply(job["setupId"], True, job["principal"], True)
        self.factory.assert_not_called()

    def test_restart_recovers_terminal_audit_without_reapplying(self):
        job = self.preview()
        self.service.apply(job["setupId"], True, job["principal"], True)
        self.service._apply(job["setupId"])
        self.factory.reset_mock()
        restored = PermissionSetupService(self.factory, Path(self.temporary.name))
        self.assertEqual(restored.snapshot(job["setupId"]), self.service.snapshot(job["setupId"]))
        with self.assertRaises(SetupError):
            restored.apply(job["setupId"], True, job["principal"], True)
        self.factory.assert_not_called()

    def test_restart_distinguishes_unsubmitted_from_unknown_grant(self):
        job = self.preview()
        self.service._update(job["setupId"], status="applying")
        self.service._audit(job["setupId"])
        restored = PermissionSetupService(self.factory, Path(self.temporary.name))
        self.assertEqual(restored.snapshot(job["setupId"])["status"], "failed")
        self.service.jobs[job["setupId"]]["grants"][0]["status"] = "submitted"
        self.service._audit(job["setupId"])
        restored = PermissionSetupService(self.factory, Path(self.temporary.name))
        result = restored.snapshot(job["setupId"])
        self.assertEqual(result["status"], "unknown")
        self.assertFalse(result["accessVerified"])
        self.assertIn("nothing was resubmitted", result["error"])
        self.client.query.assert_not_called()

    def test_missing_or_invalid_saved_audit_never_returns_success(self):
        with self.assertRaises(SetupError) as missing:
            self.service.snapshot("a" * 32)
        self.assertEqual(missing.exception.status, 404)
        path = Path(self.temporary.name) / f"{'a' * 32}.json"
        for content in ('not JSON', '[]', '{"setupId": "wrong"}'):
            path.write_text(content, encoding="utf-8")
            with self.assertRaises(SetupError) as invalid:
                self.service.snapshot("a" * 32)
            self.assertEqual(invalid.exception.status, 500)
        self.factory.assert_not_called()

    def test_rejects_external_hosts_and_unsafe_warehouse_paths(self):
        for host in ("example.com", "adb-123.1.azuredatabricks.net.evil.test", "adb-123.1.azuredatabricks.net/path", "adb-123.1.azuredatabricks.net@evil.test"):
            with self.assertRaises(SetupError):
                self.service.preview({**TARGET, "workspaceUrl": host}, True)
        with self.assertRaises(SetupError):
            self.service.preview({**TARGET, "sqlWarehouseId": "../other"}, True)
        self.factory.assert_not_called()

    def test_principal_is_quoted_as_one_identifier_not_executable_sql(self):
        statements = grant_statements("name`with;punctuation")
        self.assertEqual(len(statements), 3)
        self.assertTrue(all(statement.endswith("`name``with;punctuation`") for statement in statements))
        with self.assertRaises(SetupError):
            grant_statements("name\nsecond-line")


class SetupTransportTests(unittest.TestCase):
    def test_failed_sql_statement_is_a_known_failure(self):
        client = DatabricksSetupClient(TARGET["workspaceUrl"], TARGET["sqlWarehouseId"], "not-a-real-token")
        client.request = Mock(return_value={
            "status": {"state": "FAILED", "error": {"message": "PERMISSION_DENIED: missing MANAGE"}},
        })
        with self.assertRaisesRegex(StatementFailed, "missing MANAGE"):
            client.query("GRANT USE CATALOG ON CATALOG system TO `fixture`")
        self.assertEqual(client.request.call_count, 1)

    def test_truncated_response_is_an_explicit_unknown_outcome(self):
        client = DatabricksSetupClient(TARGET["workspaceUrl"], TARGET["sqlWarehouseId"], "not-a-real-token")
        client.opener.open = Mock(side_effect=IncompleteRead(b"partial"))
        with self.assertRaisesRegex(SetupError, "outcome may be unknown"):
            client.query("SELECT 1")

    def test_cli_timeout_is_reported_without_retry(self):
        with patch("assessment_server.subprocess.run", side_effect=subprocess.TimeoutExpired("az", 60)) as command:
            with self.assertRaisesRegex(ApiError, "60-second timeout"):
                run_az(["account", "get-access-token"], Path.cwd(), timeout_seconds=60)
        self.assertEqual(command.call_count, 1)
        self.assertEqual(command.call_args.kwargs["timeout"], 60)

    def test_permission_identity_token_request_has_a_deadline(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            service = AssessmentService(root, root / "output", root / "index.html")
            with patch("assessment_server.run_az", side_effect=ApiError(504, "Token request timed out")) as command:
                with self.assertRaisesRegex(SetupError, "Token request timed out"):
                    service._permission_client(TARGET["workspaceUrl"], TARGET["sqlWarehouseId"])
            self.assertEqual(command.call_args.kwargs["timeout_seconds"], 60)

    def test_pending_statement_is_polled_without_resubmission(self):
        client = DatabricksSetupClient(TARGET["workspaceUrl"], TARGET["sqlWarehouseId"], "not-a-real-token")
        client.request = Mock(side_effect=[
            {"statement_id": "abc-123", "status": {"state": "PENDING"}},
            {"status": {"state": "SUCCEEDED"}, "result": {"data_array": [["verified@example.test"]]}},
        ])
        with patch("permission_setup.time.sleep"):
            self.assertEqual(client.identity(), "verified@example.test")
        self.assertEqual([call.args[0] for call in client.request.call_args_list], ["POST", "GET"])

    def test_timeout_is_explicit_and_never_retries_grants(self):
        client = DatabricksSetupClient(TARGET["workspaceUrl"], TARGET["sqlWarehouseId"], "not-a-real-token")
        client.request = Mock(return_value={"statement_id": "abc", "status": {"state": "RUNNING"}})
        with patch("permission_setup.time.monotonic", side_effect=[0, 181]):
            with self.assertRaisesRegex(SetupError, "may still execute"):
                client.query("SELECT 1")
        self.assertEqual(client.request.call_count, 1)

    def test_rejects_redirects_errors_and_malformed_identities(self):
        self.assertIsNone(NoRedirect().redirect_request(None, None, 302, "", {}, "https://external.test"))
        client = DatabricksSetupClient(TARGET["workspaceUrl"], TARGET["sqlWarehouseId"], "not-a-real-token")
        client.opener.open = Mock(side_effect=HTTPError("https://test", 403, "Forbidden", {}, io.BytesIO(b'{"message":"permission denied"}')))
        with self.assertRaisesRegex(SetupError, "HTTP 403"):
            client.query("SELECT 1")
        client.query = Mock(return_value={"status": {"state": "SUCCEEDED"}, "result": {"data_array": []}})
        with self.assertRaisesRegex(SetupError, "exactly one"):
            client.identity()


class WarehouseDiscoveryTests(unittest.TestCase):
    def test_discovery_uses_only_read_only_requests_and_maps_paginated_sizes(self):
        responses = [
            {"warehouses": [{"id": "one", "name": "Running", "cluster_size": "Small", "state": "RUNNING", "enable_serverless_compute": True}], "next_page_token": "a/b="},
            {"warehouses": [{"id": "two", "cluster_size": "2X-Small", "state": "STOPPED"}]},
        ]
        with patch("assessment_server.run_az", side_effect=responses) as request:
            rows = discover_warehouses(TARGET["workspaceUrl"], Path("."))
        self.assertEqual([row["size"] for row in rows], ["Small", "2X-Small"])
        self.assertTrue(rows[0]["serverless"])
        self.assertTrue(all("GET" in call.args[0] for call in request.call_args_list))
        self.assertIn("page_token=a%2Fb%3D", request.call_args_list[1].args[0][4])

    def test_repeating_page_tokens_are_reported(self):
        with patch("assessment_server.run_az", return_value={"warehouses": [], "next_page_token": "same"}):
            with self.assertRaisesRegex(ApiError, "did not advance"):
                discover_warehouses(TARGET["workspaceUrl"], Path("."))


class SetupEndpointTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.service = AssessmentService(root, root / "output", root / "index.html")
        self.server = AssessmentHttpServer(("127.0.0.1", 0), self.service)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def post(self, path, body, headers=None):
        connection = HTTPConnection("127.0.0.1", self.server.server_port)
        connection.request("POST", path, json.dumps(body), headers or {"Content-Type": "application/json"})
        response = connection.getresponse()
        result = response.status, json.loads(response.read())
        connection.close()
        return result

    def test_mutation_routes_reject_cross_origin_wrong_host_and_non_json(self):
        with patch.object(self.service.permission_setup, "preview") as preview:
            for headers, status in (
                ({"Content-Type": "text/plain"}, 415),
                ({"Content-Type": "application/json", "Origin": "https://other.test"}, 403),
                ({"Content-Type": "application/json", "Host": f"other.test:{self.server.server_port}"}, 403),
            ):
                self.assertEqual(self.post("/api/permission-setups", {}, headers)[0], status)
            preview.assert_not_called()

    def test_live_assessment_and_permission_setup_are_mutually_exclusive(self):
        state = ValidationState("running")
        self.service.validations["running"] = state
        with patch.object(self.service.permission_setup, "preview") as preview:
            self.assertEqual(self.post("/api/permission-setups", {"workspace": TARGET, "approveSqlWarehouseAutoStart": True})[0], 409)
            preview.assert_not_called()
        self.service.validations.clear()
        with patch.object(self.service.permission_setup, "busy", return_value=True), patch.object(self.service, "start_validation") as validate:
            self.assertEqual(self.post("/api/validations", {"config": {}, "approvals": {}})[0], 409)
            validate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
