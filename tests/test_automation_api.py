import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi import FastAPI
from fastapi.testclient import TestClient
from core.automation_api import router


class DraftApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"CORA_AUTOMATION_ROOT": self.tmp.name, "CORA_FILES_TOKEN": "owner-secret"})
        self.env.start()
        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)
        self.headers = {"Authorization": "Bearer owner-secret"}
        self.body = {"title": "Prova", "description": "", "nodes": [dict(id="start", kind="trigger", label="Ingresso", x=50, y=50, config={})], "edges": []}

    def tearDown(self):
        self.client.close()
        self.env.stop()
        self.tmp.cleanup()

    def test_owner_auth_protects_reads_and_writes(self):
        self.assertEqual(self.client.get("/tools/drafts").status_code, 401)
        self.assertEqual(self.client.post("/tools/drafts", json=self.body).status_code, 401)
        self.assertEqual(self.client.get("/tools/drafts", headers={"Authorization": "Bearer wrong"}).status_code, 401)

    def test_create_read_update_and_conflict_without_execution(self):
        created = self.client.post("/tools/drafts", json=self.body, headers=self.headers)
        self.assertEqual(created.status_code, 201)
        result = created.json()
        self.assertEqual(result["status"], "draft")
        self.assertEqual(self.client.get("/tools/drafts", headers=self.headers).json()[0]["id"], result["id"])
        url = "/tools/drafts/" + result["id"]
        self.assertEqual(self.client.get(url, headers=self.headers).json()["nodes"], result["nodes"])
        body = {**self.body, "version": 1, "title": "Aggiornata"}
        self.assertEqual(self.client.put(url, json=body, headers=self.headers).status_code, 200)
        self.assertEqual(self.client.put(url, json=body, headers=self.headers).status_code, 409)
        self.assertEqual(self.client.post(url + "/execute", headers=self.headers).status_code, 404)

    def test_invalid_graph_or_unknown_tool_returns_400(self):
        body = {**self.body, "edges": [dict(id="e", source=[], target="start", label="x")]}
        self.assertEqual(self.client.post("/tools/drafts", json=body, headers=self.headers).status_code, 400)
        body = {**self.body, "nodes": [dict(id="tool", kind="tool", label="Missing", x=50, y=50, config={}, tool_id="absent")]}
        self.assertEqual(self.client.post("/tools/drafts", json=body, headers=self.headers).status_code, 400)


if __name__ == "__main__":
    unittest.main()
