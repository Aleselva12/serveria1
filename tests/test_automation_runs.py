import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.domain import automation_drafts as drafts
from core.domain import automation_engine as engine
from core.domain import automation_runs as runs

BINDINGS = {
    "search.py:search": {"capability": "search:cap", "contract_id": "agent.search", "effect": "read", "actor": "agent",
                         "input_schema": {"type": "object", "required": ["query"], "properties": {"query": {"type": "string"}}}},
    "mail.py:send": {"capability": "send:cap", "contract_id": "agent.send", "effect": "write", "actor": "agent",
                     "input_schema": {"type": "object", "required": ["to", "body"], "properties": {"to": {}, "body": {}}}},
}


def ok(value):
    return SimpleNamespace(status="ok", value=value, operation_id="op", error=None, approval_id=None)


def graph(op="gt", right=0):
    """trigger -> search -> condition (count > 0) -> yes: send / no: output."""
    return {"title": "Avvisa", "description": "", "nodes": [
        dict(id="start", kind="trigger", label="Avvio", x=10, y=10, config={}),
        dict(id="find", kind="tool", label="Cerca", x=200, y=10, tool_id="search.py:search", config={"query": "{{input.topic}}"}),
        dict(id="check", kind="condition", label="Trovato?", x=400, y=10, config={"left": "{{find.count}}", "op": op, "right": right}),
        dict(id="send", kind="tool", label="Invia", x=600, y=10, tool_id="mail.py:send",
             config={"to": "me", "body": "Trovati {{find.count}}: {{find.items.0}}"}),
        dict(id="end", kind="output", label="Fine", x=800, y=10, config={}),
    ], "edges": [
        dict(id="a", source="start", target="find", label="successo"),
        dict(id="b", source="find", target="check", label="successo"),
        dict(id="c", source="check", target="send", label="sì"),
        dict(id="d", source="check", target="end", label="no"),
        dict(id="e", source="send", target="end", label="successo"),
    ]}


class Calls:
    def __init__(self, results):
        self.results, self.seen = results, []

    def __call__(self, capability, payload):
        self.seen.append((capability, payload))
        outcome = self.results[capability]
        return outcome(payload) if callable(outcome) else outcome


def new_run(g, mode="live", run_input=None):
    return {"id": "r", "mode": mode, "status": "queued", "input": run_input or {"topic": "fatture"}, "nodes": engine.new_run_nodes(g)}


class EngineTests(unittest.TestCase):
    def test_live_run_passes_data_and_follows_yes_branch(self):
        g = graph()
        calls = Calls({"search:cap": ok({"count": 2, "items": ["A", "B"]}), "send:cap": ok({"sent": True})})
        run = engine.advance(new_run(g), g, BINDINGS, calls)
        self.assertEqual(run["status"], "succeeded")
        self.assertEqual(calls.seen[0], ("search:cap", {"query": "fatture"}))
        self.assertEqual(calls.seen[1], ("send:cap", {"to": "me", "body": "Trovati 2: A"}))
        self.assertEqual(run["nodes"]["check"]["outcome"], "sì")
        self.assertEqual(run["nodes"]["end"]["result"], {"Invia": {"sent": True}})

    def test_no_branch_skips_the_other_side(self):
        g = graph()
        calls = Calls({"search:cap": ok({"count": 0, "items": []})})
        run = engine.advance(new_run(g), g, BINDINGS, calls)
        self.assertEqual(run["status"], "succeeded")
        self.assertEqual(run["nodes"]["send"]["status"], "skipped")
        self.assertEqual(run["nodes"]["end"]["status"], "done")
        self.assertEqual(len(calls.seen), 1)

    def test_dry_run_never_calls_write_tools(self):
        g = graph()
        calls = Calls({"search:cap": ok({"count": 3, "items": ["X"]})})
        run = engine.advance(new_run(g, "dry_run"), g, BINDINGS, calls)
        self.assertEqual(run["status"], "succeeded")
        self.assertEqual([c[0] for c in calls.seen], ["search:cap"])
        self.assertEqual(run["nodes"]["send"]["status"], "simulated")
        self.assertEqual(run["nodes"]["send"]["input"], {"to": "me", "body": "Trovati 3: X"})

    def test_values_from_simulated_nodes_are_not_executed(self):
        g = graph()
        g["nodes"][1]["tool_id"] = "mail.py:send"  # first step writes, so its result is simulated
        g["nodes"][1]["config"] = {"to": "x", "body": "y"}
        calls = Calls({})
        run = engine.advance(new_run(g, "dry_run"), g, BINDINGS, calls)
        self.assertEqual(calls.seen, [])
        self.assertEqual(run["nodes"]["check"]["status"], "simulated")
        self.assertEqual(run["nodes"]["send"]["status"], "simulated")
        self.assertEqual(run["status"], "succeeded")

    def test_tool_error_stops_the_run_without_retry(self):
        g = graph()
        failed = SimpleNamespace(status="error", value=None, operation_id="op", approval_id=None,
                                 error=SimpleNamespace(code="Boom", message="Servizio non raggiungibile."))
        calls = Calls({"search:cap": failed})
        run = engine.advance(new_run(g), g, BINDINGS, calls)
        self.assertEqual(run["status"], "failed")
        self.assertIn("Servizio non raggiungibile", run["error"])
        self.assertEqual(len(calls.seen), 1)
        self.assertEqual(run["nodes"]["check"]["status"], "pending")

    def test_missing_reference_and_bad_comparison_fail_clearly(self):
        g = graph()
        run = engine.advance(new_run(g), g, BINDINGS, Calls({"search:cap": ok({"items": []})}))
        self.assertEqual(run["status"], "failed")
        self.assertIn("«count» non trovato", run["error"])
        run = engine.advance(new_run(g), g, BINDINGS, Calls({"search:cap": ok({"count": "molti"})}))
        self.assertIn("solo fra numeri", run["error"])

    def test_approval_pauses_and_resumes_or_rejects(self):
        g = graph()
        pending = SimpleNamespace(status="pending", value=None, operation_id="op", approval_id="appr-1", error=None)
        calls = Calls({"search:cap": ok({"count": 1, "items": ["A"]}), "send:cap": pending})
        run = engine.advance(new_run(g), g, BINDINGS, calls)
        self.assertEqual(run["status"], "waiting_approval")
        self.assertEqual(run["nodes"]["send"]["approval_id"], "appr-1")
        self.assertEqual(run["nodes"]["end"]["status"], "pending")
        resumed = {**run, "nodes": {k: dict(v) for k, v in run["nodes"].items()}}
        engine.apply_approval(resumed, "send", {"status": "approved", "result": {"sent": True}})
        engine.advance(resumed, g, BINDINGS, calls)
        self.assertEqual(resumed["status"], "succeeded")
        self.assertEqual(len(calls.seen), 2)  # the approved tool is not called again
        engine.apply_approval(run, "send", {"status": "rejected"})
        engine.advance(run, g, BINDINGS, calls)
        self.assertEqual(run["status"], "rejected")

    def test_conditions(self):
        cases = [("eq", "3", 3, True), ("ne", "a", "b", True), ("gte", 2, "2", True), ("lt", 1, 0, False),
                 ("contains", "Fattura urgente", "URGENTE", True), ("contains", ["a", "b"], "b", True),
                 ("not_contains", "ciao", "x", True), ("empty", [], None, True), ("not_empty", "", None, False),
                 ("eq", {"a": 1}, {"a": 1}, True)]
        for op, left, right, expected in cases:
            with self.subTest(op=op, left=left):
                self.assertEqual(engine.evaluate({"op": op}, left, right), expected)

    def test_preflight_lists_every_blocker(self):
        g = graph()
        g["nodes"][3]["config"] = {"body": "{{end.x}} {{ghost.y}}"}
        g["nodes"][2]["config"] = {"op": "gt"}
        g["nodes"][1]["tool_id"] = "unknown.py:tool"
        problems = engine.preflight(g, BINDINGS)
        text = "\n".join(problems)
        for expected in ("Cerca: il tool non ha un contratto eseguibile.", "Trovato?: regola incompleta",
                         "Invia: manca il parametro obbligatorio «to».", "«ghost.y» punta a un passaggio inesistente",
                         "usa «Fine», che non lo precede"):
            self.assertIn(expected, text)
        self.assertEqual(engine.input_names(graph()), ["topic"])


class RunStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.drafts = Path(self.tmp.name) / "drafts"
        self.root = Path(self.tmp.name) / "runs"
        self.saved = drafts.save_draft(graph(), root=self.drafts)

    def tearDown(self):
        self.tmp.cleanup()

    def create(self, mode="live", run_input=None):
        return runs.create_run(self.saved["id"], 1, mode, {"topic": "x"} if run_input is None else run_input,
                               BINDINGS, root=self.root, draft_root=self.drafts)

    def test_create_requires_current_version_inputs_and_runnable_graph(self):
        with self.assertRaises(drafts.VersionConflict):
            runs.create_run(self.saved["id"], 2, "live", {"topic": "x"}, BINDINGS, root=self.root, draft_root=self.drafts)
        with self.assertRaises(runs.RunRejected) as rejected:
            self.create(run_input={})
        self.assertIn("Manca il valore di avvio «topic».", rejected.exception.problems)
        with self.assertRaises(runs.RunRejected):
            runs.create_run(self.saved["id"], 1, "live", {"topic": "x"}, {}, root=self.root, draft_root=self.drafts)
        run = self.create()
        self.assertEqual(run["status"], "queued")
        self.assertEqual(set(run["bindings"]), set(BINDINGS))
        self.assertEqual(runs.list_runs(self.saved["id"], self.root)[0]["id"], run["id"])

    def test_process_pauses_for_approval_and_resumes_from_store(self):
        run = self.create()
        pending = SimpleNamespace(status="pending", value=None, operation_id="op", approval_id="appr", error=None)
        calls = Calls({"search:cap": ok({"count": 1, "items": ["A"]}), "send:cap": pending})
        run = runs.process(run, self.root, execute=calls, decide=lambda _id: {"status": "pending"})
        self.assertEqual(run["status"], "waiting_approval")
        self.assertIsNone(run["finished_at"])
        stored = runs.get_run(run["id"], self.root)
        unchanged = runs.process(stored, self.root, execute=calls, decide=lambda _id: {"status": "pending"})
        self.assertEqual(unchanged["status"], "waiting_approval")
        done = runs.process(stored, self.root, execute=calls, decide=lambda _id: {"status": "approved", "result": {"ok": 1}})
        self.assertEqual(done["status"], "succeeded")
        self.assertIsNotNone(done["finished_at"])
        self.assertEqual(len(calls.seen), 2)
        self.assertEqual(runs.get_run(run["id"], self.root)["nodes"]["send"]["result"], {"ok": 1})

    def test_cancel_queued_and_waiting_runs(self):
        run = self.create()
        cancelled = runs.cancel_run(run["id"], self.root)
        self.assertEqual(cancelled["status"], "cancelled")
        # A run cancelled while queued is not started by the runner.
        self.assertEqual(runs.process(run, self.root, execute=Calls({}))["status"], "cancelled")
        with self.assertRaises(drafts.VersionConflict):
            runs.cancel_run(run["id"], self.root)

    def test_running_cancel_stops_before_next_node(self):
        run = self.create()

        def search(_payload):
            runs._CANCEL.add(run["id"])
            return ok({"count": 1, "items": ["A"]})
        done = runs.process(run, self.root, execute=Calls({"search:cap": search}))
        self.assertEqual(done["status"], "cancelled")
        self.assertEqual(done["nodes"]["check"]["status"], "pending")

    def test_time_limit_fails_the_run(self):
        run = self.create()
        with patch.object(runs, "time_limit", return_value=-1):
            done = runs.process(run, self.root, execute=Calls({}))
        self.assertEqual(done["status"], "failed")
        self.assertIn("Tempo massimo", done["error"])

    def test_restart_marks_running_runs_interrupted_and_keeps_waiting_ones(self):
        running = self.create()
        running.update(status="running")
        running["nodes"]["find"]["started_at"] = engine.now()
        runs._write(running, self.root)
        waiting = self.create()
        waiting["status"] = "waiting_approval"
        runs._write(waiting, self.root)
        runs.recover_interrupted(self.root)
        interrupted = runs.get_run(running["id"], self.root)
        self.assertEqual(interrupted["status"], "interrupted")
        self.assertEqual(interrupted["nodes"]["find"]["status"], "failed")
        self.assertEqual(runs.get_run(waiting["id"], self.root)["status"], "waiting_approval")

    def test_identifiers_cannot_escape_folder(self):
        with self.assertRaises(ValueError):
            runs.get_run("../x", self.root)


class RunApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"CORA_AUTOMATION_ROOT": self.tmp.name + "/d", "CORA_AUTOMATION_RUNS_ROOT": self.tmp.name + "/r",
                                           "CORA_FILES_TOKEN": "owner-secret"})
        self.env.start()
        from core.api.automation_api import router, runs_router
        app = FastAPI()
        app.include_router(router)
        app.include_router(runs_router)
        self.client = TestClient(app)
        self.headers = {"Authorization": "Bearer owner-secret"}
        self.saved = drafts.save_draft(graph())
        entries = [{"id": key, "kind": "tool", "capabilities": [{"tool_id": b["capability"], "id": b["contract_id"], "effect": b["effect"],
                                                                 "actor": b["actor"], "input_schema": b["input_schema"]}]} for key, b in BINDINGS.items()]
        self.inventory = patch("core.api.automation_api.inventory", return_value={"entries": entries, "errors": []})
        self.inventory.start()

    def tearDown(self):
        self.inventory.stop()
        self.client.close()
        self.env.stop()
        self.tmp.cleanup()

    def test_start_list_get_and_cancel(self):
        url = f"/tools/drafts/{self.saved['id']}/runs"
        body = {"version": 1, "mode": "dry_run", "input": {"topic": "x"}}
        self.assertEqual(self.client.post(url, json=body).status_code, 401)
        with patch.object(runs, "runner_active", return_value=False):
            self.assertEqual(self.client.post(url, json=body, headers=self.headers).status_code, 503)
        with patch.object(runs, "runner_active", return_value=True):
            rejected = self.client.post(url, json={**body, "input": {}}, headers=self.headers)
            self.assertEqual(rejected.status_code, 422)
            self.assertIn("Manca il valore di avvio «topic».", rejected.json()["detail"]["problems"])
            self.assertEqual(self.client.post(url, json={**body, "version": 3}, headers=self.headers).status_code, 409)
            self.assertEqual(self.client.post(url, json={**body, "mode": "other"}, headers=self.headers).status_code, 422)
            created = self.client.post(url, json=body, headers=self.headers)
        self.assertEqual(created.status_code, 201)
        run_id = created.json()["id"]
        self.assertEqual(self.client.get(url, headers=self.headers).json()[0]["id"], run_id)
        self.assertEqual(self.client.get(f"/tools/runs/{run_id}", headers=self.headers).json()["status"], "queued")
        self.assertEqual(self.client.get(f"/tools/runs/{run_id}").status_code, 401)
        self.assertEqual(self.client.post(f"/tools/runs/{run_id}/cancel", headers=self.headers).json()["status"], "cancelled")
        self.assertEqual(self.client.post(f"/tools/runs/{run_id}/cancel", headers=self.headers).status_code, 409)
        self.assertEqual(self.client.get("/tools/runs/not-a-uuid", headers=self.headers).status_code, 400)


if __name__ == "__main__":
    unittest.main()
