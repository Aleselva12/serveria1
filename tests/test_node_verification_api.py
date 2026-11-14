import os
import unittest
from copy import deepcopy
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.verify import node_verification as service


class NodeVerificationAPITests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"CORA_OWNER_TOKEN": "owner-test"})
        self.env.start()
        self.addCleanup(self.env.stop)
        app = FastAPI()
        app.include_router(service.router)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.auth = {"Authorization": "Bearer owner-test"}

    def test_routes_are_owner_only_and_get_never_launches(self):
        with patch.object(service, "_connection") as connection, patch.object(service, "Thread") as worker:
            self.assertEqual(self.client.get("/api/v1/system/node-verification").status_code, 401)
            self.assertEqual(self.client.post("/api/v1/system/node-verification", json={}).status_code, 401)
            connection.assert_not_called()
            worker.assert_not_called()
        with patch.object(service, "_connection"), patch.object(service, "_latest", return_value=None), patch.object(service, "Thread") as worker:
            response = self.client.get("/api/v1/system/node-verification", headers=self.auth)
            self.assertEqual(response.status_code, 200)
            self.assertIsNone(response.json()["run"])
            self.assertIn("memory_e2e", [r["id"] for r in response.json()["availableChecks"]])
            self.assertEqual(response.json()["unavailableChecks"], [])
            ids = [row["id"] for row in response.json()["availableChecks"]]
            self.assertEqual(len(ids), len(set(ids)))
            self.assertEqual(set(ids), set(service.CATALOG))
            self.assertTrue({"word_document_regression", "capability_permissions_regression", "file_preview_regression", "test_inventory_regression", "evidence_provenance_regression"} <= set(ids))
            inventory = response.json()["testInventory"]
            self.assertEqual(inventory["total"], inventory["runnerLinked"] + inventory["repositoryOnly"])
            self.assertGreater(inventory["total"], 90)
            self.assertTrue(any(row["module"] == "test_test_inventory" for row in inventory["tests"]))
            worker.assert_not_called()

    def test_duplicate_click_is_rejected_across_workers_and_cli(self):
        conn = MagicMock()
        with patch.object(service, "_connection", return_value=conn), patch.object(service, "_locked", return_value=False), patch.object(service, "Thread") as thread:
            response = self.client.post("/api/v1/system/node-verification", headers=self.auth, json={})
            self.assertEqual(response.status_code, 409)
            thread.assert_not_called()
            conn.close.assert_called_once()

    def test_start_returns_immediately_and_only_accepts_registered_machine_ids(self):
        identifier = str(uuid4())
        conn = MagicMock()
        with patch.object(service, "_connection", return_value=conn), patch.object(service, "_locked", return_value=True), patch.object(service, "Thread") as thread, patch("core.api.machines_api._find", return_value={}) as find:
            response = self.client.post("/api/v1/system/node-verification", headers=self.auth, json={"desktopMachineId": identifier})
            self.assertEqual(response.status_code, 202)
            job = response.json()
            self.assertEqual(job["status"], "running")
            self.assertEqual(job["completed"], 0)
            self.assertGreater(job["total"], 8)
            find.assert_called_once_with(identifier)
            thread.return_value.start.assert_called_once()
            self.assertEqual(thread.call_args.kwargs["args"][2], {"CORA_VERIFY_DESKTOP_ID": identifier})
            conn.close.assert_not_called()  # Owned by the background worker.
        for invalid in ({"command": "arbitrary"}, {"desktopMachineId": "https://host"}):
            with patch.object(service, "Thread") as thread:
                self.assertEqual(self.client.post("/api/v1/system/node-verification", headers=self.auth, json=invalid).status_code, 422)
                thread.assert_not_called()

    def test_reload_recovers_progress_without_starting_another_suite(self):
        job = {"id": str(uuid4()), "status": "running", "completed": 3, "results": []}
        for active, expected in ((True, "running"), (False, "interrupted")):
            with patch.object(service, "_connection"), patch.object(service, "_latest", return_value=dict(job)), patch.object(service, "_locked", return_value=not active), patch.object(service, "_save") as save, patch.object(service, "_release"), patch.object(service, "Thread") as thread:
                response = self.client.get("/api/v1/system/node-verification", headers=self.auth)
                self.assertEqual(response.json()["run"]["status"], expected)
                self.assertEqual(response.json()["run"]["completed"], 3)
                self.assertEqual(save.called, not active)
                thread.assert_not_called()

    def test_results_and_progress_are_recorded_after_every_check(self):
        conn = MagicMock()
        job = {"id": str(uuid4()), "status": "running", "checks": ["one", "two"], "results": [], "total": 2, "completed": 0}
        writes = []
        def execute(args, on_result):
            for key, status in (("one", "pass"), ("two", "fail")):
                on_result({"id": key, "status": status, "detail": "Test", "environment": "debian-verifier", "commit": "a"*40, "durationMs": 1, "at": "2026-11-05T12:00:00+00:00"})
        with patch.object(service.verify_nodes, "execute", side_effect=execute), patch.object(service, "_save", side_effect=lambda c,j:writes.append(deepcopy(j))), patch.object(service, "_release") as release:
            service._run(conn, job, {})
        self.assertEqual([j["completed"] for j in writes], [0, 0, 1, 2, 2])
        self.assertEqual(writes[2]["currentCheck"], "two")
        self.assertEqual(writes[-1]["status"], "failed")
        self.assertEqual(conn.execute.call_count, 2)
        release.assert_called_once_with(conn)
        conn.close.assert_called_once()

    def test_unavailable_storage_returns_actionable_error_without_private_details(self):
        with patch.object(service, "_connection", side_effect=OSError("private-token")):
            for method in ("get", "post"):
                response = getattr(self.client, method)("/api/v1/system/node-verification", headers=self.auth)
                self.assertEqual(response.status_code, 503)
                self.assertNotIn("private-token", response.text)


if __name__ == "__main__":
    unittest.main()


class AutoVerificationTests(unittest.TestCase):
    SHA = "c" * 40

    def _conn(self, existing=None, previous=None):
        conn = MagicMock()
        conn.__enter__.return_value = conn
        conn.execute.return_value.fetchone.return_value = existing
        return conn

    def _patches(self, conn, environment="debian-api", release=SHA, previous=None):
        return (patch.dict(os.environ, {"CORA_AUTO_VERIFY": "1"}),
                patch("core.verify.project_checks._environment", return_value=environment),
                patch.object(service, "_installed_release", return_value=release),
                patch.object(service, "_connection", return_value=conn),
                patch.object(service, "_latest", return_value=previous))

    def _run(self, conn, **kwargs):
        from contextlib import ExitStack
        with ExitStack() as stack:
            for item in self._patches(conn, **kwargs):
                stack.enter_context(item)
            launch = stack.enter_context(patch.object(service, "_launch"))
            return service.auto_verify_release(), launch

    def test_new_release_starts_once_with_previous_machines(self):
        identifier = str(uuid4())
        reason, launch = self._run(self._conn(), previous={"targets": {"desktopMachineId": identifier, "laptopMachineId": None}})
        self.assertEqual(reason, "started")
        body, trigger = launch.call_args.args
        self.assertEqual(trigger, "auto")
        self.assertEqual(str(body.desktopMachineId), identifier)
        self.assertIsNone(body.laptopMachineId)

    def test_release_already_verified_or_not_installed_never_starts(self):
        reason, launch = self._run(self._conn(existing={"?column?": 1}))
        self.assertEqual(reason, "already_verified")
        launch.assert_not_called()
        for kwargs in ({"environment": "ci-api"}, {"release": ""}):
            reason, launch = self._run(self._conn(), **kwargs)
            self.assertEqual(reason, "not_installed_release")
            launch.assert_not_called()
        with patch.dict(os.environ, {"CORA_AUTO_VERIFY": "0"}), patch.object(service, "_launch") as launch:
            self.assertEqual(service.auto_verify_release(), "disabled")
            launch.assert_not_called()

    def test_removed_machine_falls_back_and_running_suite_is_respected(self):
        from fastapi import HTTPException
        conn = self._conn()
        previous = {"targets": {"desktopMachineId": str(uuid4())}}
        from contextlib import ExitStack
        with ExitStack() as stack:
            for item in self._patches(conn, previous=previous):
                stack.enter_context(item)
            launch = stack.enter_context(patch.object(service, "_launch", side_effect=[HTTPException(404), None]))
            self.assertEqual(service.auto_verify_release(), "started")
            self.assertIsNone(launch.call_args.args[0].desktopMachineId)
        reason, _ = self._run(conn)
        with ExitStack() as stack:
            for item in self._patches(conn):
                stack.enter_context(item)
            stack.enter_context(patch.object(service, "_launch", side_effect=HTTPException(409)))
            self.assertEqual(service.auto_verify_release(), "busy")

    def test_api_lifespan_registers_and_stops_the_automatic_run(self):
        from pathlib import Path
        source = (Path(__file__).resolve().parents[1] / "api.py").read_text(encoding="utf-8")
        self.assertIn("node_verification.start_auto()", source)
        self.assertIn("cleanup.callback(node_verification.stop_auto)", source)
