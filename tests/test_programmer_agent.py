import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from contextlib import ExitStack
from fastapi import FastAPI
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage
from programmer_agent import workspace as ws, knowledge
from programmer_agent.api import router
from programmer_agent.checks import run_check, docker_check


class ProgrammerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.env = patch.dict(os.environ, {"CORA_PROGRAMMER_WORKSPACE_ROOT": self.temp.name + "/work"})
        self.env.start(); self.addCleanup(self.env.stop)
        self.source = Path(self.temp.name) / "source"
        self.source.mkdir()
        (self.source / "sample.py").write_text('def add(a, b):\n    return a + b\n', encoding="utf-8")
        (self.source / ".env").write_text("PASSWORD=private")
        (self.source / "credentials.json").write_text('{"private":true}')
        (self.source / "data").mkdir()
        (self.source / "data" / "history.json").write_text('"private"')
        self.row = ws.create("Test tool", self.source)
        self.identifier = self.row["id"]
        app = FastAPI(); app.include_router(router)
        self.client = TestClient(app)

    def test_filtered_snapshot_and_optimistic_write_leave_live_source_untouched(self):
        self.assertEqual(ws.list_files(self.identifier), ["sample.py"])
        original = ws.read(self.identifier, "sample.py")
        ws.write(self.identifier, "sample.py", "value = 2\n", original["sha256"])
        with self.assertRaises(ws.WorkspaceConflict):
            ws.write(self.identifier, "sample.py", "value = 3\n", original["sha256"])
        self.assertIn("def add", (self.source / "sample.py").read_text())
        diff = ws.diff(self.identifier)
        self.assertEqual(diff["total_changes"], 1)
        self.assertIn("+value = 2", diff["changes"][0]["patch"])
        self.assertEqual(ws.list_workspaces()[0]["id"], self.identifier)

    def test_manual_editor_reads_full_file_and_rejects_stale_save(self):
        content = "value = 1\n" * 300 + "# no final newline"
        ws.write(self.identifier, "long.py", content)
        url = f"/api/v1/programmer/workspaces/{self.identifier}/file"
        partial = self.client.get(url, params={"path": "long.py"}).json()
        self.assertTrue(partial["truncated"])
        full = self.client.get(url, params={"path": "long.py", "full": "true"}).json()
        self.assertEqual(full["content"], content)
        self.assertFalse(full["truncated"])
        ws.write(self.identifier, "long.py", "newer", full["sha256"])
        result = self.client.put(url, json={"path": "long.py", "content": content, "expected_sha256": full["sha256"]})
        self.assertEqual(result.status_code, 409)
        self.assertEqual(ws.read_full(self.identifier, "long.py")["content"], "newer")
        self.assertEqual(self.client.get(url, params={"path": "../secret.py", "full": "true"}).status_code, 422)

    def test_path_traversal_secrets_symlinks_and_live_root_are_rejected(self):
        for path in ("../outside.py", "/tmp/a.py", "a\\b.py", ".env", "credentials.json", "data/chat.json", "test.exe", "C:/a.py"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                ws.write(self.identifier, path, "danger")
        external = Path(self.temp.name) / "outside.py"
        external.write_text("private")
        (ws.directory(self.identifier) / "files" / "link.py").symlink_to(external)
        with self.assertRaises(ValueError):
            ws.read(self.identifier, "link.py")
        with patch.dict(os.environ, {"CORA_PROGRAMMER_WORKSPACE_ROOT": str(ws.PROJECT / "core")}):
            with self.assertRaises(ValueError): ws.root()

    def test_static_checks_do_not_execute_generated_code_and_detect_invalid_json(self):
        marker = Path(self.temp.name) / "executed"
        ws.write(self.identifier, "generated.py", f'from pathlib import Path\nPath({str(marker)!r}).write_text("executed")\n')
        self.assertTrue(run_check(self.identifier)["passed"])
        self.assertFalse(marker.exists())
        ws.write(self.identifier, "broken.json", "{bad}")
        result = run_check(self.identifier)
        self.assertFalse(result["passed"])
        self.assertEqual(result["errors"][0]["path"], "broken.json")
        with self.assertRaises(ValueError): run_check(self.identifier, "shell")

    def test_graph_queries_preserve_provenance_and_signal_modified_snapshot(self):
        graph = {"nodes": [{"id": "a", "label": "add"}, {"id": "b", "label": "sample"}],
                 "links": [{"source": "a", "target": "b", "confidence": "EXTRACTED"}]}
        with self.assertRaises(ValueError): knowledge.import_graph(self.identifier, graph, "bad-digest")
        knowledge.import_graph(self.identifier, graph, self.row["source_digest"])
        result = knowledge.query_graph(self.identifier, "add")
        self.assertEqual(result["edges"][0]["confidence"], "EXTRACTED")
        self.assertFalse(result["status"]["stale"])
        ws.write(self.identifier, "new.py", "value = 1")
        self.assertTrue(knowledge.graph_status(self.identifier)["stale"])

    def test_graphify_unresolved_imports_are_explicit_and_edges_remain_queryable(self):
        graph = {"nodes": [{"id": "sample", "label": "sample"}],
                 "edges": [{"source": "sample", "target": "os", "confidence": "EXTRACTED"}]}
        knowledge.import_graph(self.identifier, graph, self.row["source_digest"])
        result = knowledge.query_graph(self.identifier, "", "os")
        self.assertTrue(result["nodes"][0]["unresolved"])
        self.assertEqual(result["nodes"][0]["provenance"], "adapter_placeholder")
        self.assertEqual(len(result["edges"]), 1)
        self.assertEqual(len(graph["nodes"]), 1)
        graph["edges"][0]["target"] = None
        with self.assertRaises(ValueError):
            knowledge.import_graph(self.identifier, graph, self.row["source_digest"])

    def test_api_file_conflict_and_explicit_draft_import_validate_existing_schema(self):
        url = "/api/v1/programmer/workspaces/" + self.identifier
        response = self.client.get(url + "/file", params={"path": "sample.py"})
        self.assertEqual(response.status_code, 200)
        response = self.client.put(url + "/file", json={"path": "sample.py", "content": "changed", "expected_sha256": "wrong"})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.client.get(url + "/file", params={"path": "../outside.py"}).status_code, 422)
        ws.write(self.identifier, "automation.json", knowledge.template("automation"))
        with patch.dict(os.environ, {"CORA_AUTOMATION_ROOT": self.temp.name + "/drafts"}):
            response = self.client.post(url + "/drafts", json={"path": "automation.json"})
            self.assertEqual(response.status_code, 201)
            self.assertEqual(response.json()["status"], "draft")
            self.assertTrue(response.json()["warnings"])
        self.assertEqual(self.client.post(url + "/checks", json={"profile": "shell"}).status_code, 422)
        self.assertEqual(self.client.post("/api/v1/programmer/runs", json={"workspace_id": self.identifier, "message": " ", "actor": "admin"}).status_code, 422)

    def test_agent_loop_writes_workspace_through_governed_tool(self):
        from programmer_agent.programmer_graph import graph
        from core.governance import executables
        identifier = self.identifier
        class Model:
            def bind_tools(self, tools): return self
            def invoke(self, messages):
                if any(getattr(m, "type", None) == "tool" for m in messages):
                    return AIMessage(content="Bozza creata: generated.py")
                return AIMessage(content="", tool_calls=[{"name": "programmer_write_file", "args": {"workspace_id": identifier, "path": "generated.py", "content": "value = 42\n"}, "id": "write", "type": "tool_call"}])
        with ExitStack() as stack:
            stack.enter_context(ws.bind_workspace(self.identifier))
            stack.enter_context(patch('programmer_agent.programmer_graph.get_chat_model', return_value=Model()))
            stack.enter_context(patch('programmer_agent.programmer_graph.with_permanent_context', side_effect=lambda p:p))
            stack.enter_context(patch('core.operation_journal.begin', return_value='op'))
            stack.enter_context(patch('core.operation_journal.finish'))
            stack.enter_context(patch('core.database.database_configured', return_value=True))
            stack.enter_context(patch('core.permissions.policy_overrides', return_value={}))
            result = graph.invoke({"messages": [HumanMessage(content="Crea un file") ]}, config={"recursion_limit": 12})
        self.assertIn("Bozza creata", result["messages"][-1].content)
        self.assertEqual(ws.read(self.identifier, "generated.py")["content"], "value = 42\n")
        self.assertFalse((self.source / "generated.py").exists())
        tools = [e for e in executables.values() if e["actor"] == "programmer_agent"]
        self.assertEqual(len(tools), 14)
        self.assertTrue(all(e["connected"] for e in tools))

    def test_docker_is_only_execution_path_and_cleanup_runs_on_cancellation(self):
        from core.runtime import RunStopped
        ws.write(self.identifier, "tests/test_sample.py", "import unittest\nclass Test(unittest.TestCase):\n def test_one(self): self.assertTrue(True)\n")
        calls = []
        def docker(*args, **kwargs):
            calls.append(args)
            if args[0] == "run": return "container"
            if args[0] == "inspect": return "false" if "Running" in args[1] else "0"
            if args[0] == "logs": return "Ran 1 test\nOK"
            return ""
        with patch('programmer_agent.checks.shutil.which', return_value=None), self.assertRaises(ValueError):
            docker_check(self.identifier)
        with patch('programmer_agent.checks.shutil.which', return_value='docker'), patch('programmer_agent.checks._docker', side_effect=docker):
            result = docker_check(self.identifier)
        self.assertTrue(result["passed"])
        command = calls[0]
        for flag in ("--network=none", "--read-only", "--cap-drop=ALL", "--security-opt=no-new-privileges", "--pull=never"):
            self.assertIn(flag, command)
        self.assertEqual(calls[-1][0], 'rm')
        calls.clear()
        with patch('programmer_agent.checks.shutil.which', return_value='docker'), patch('programmer_agent.checks._docker', side_effect=docker), patch('programmer_agent.checks.checkpoint', side_effect=[None, RunStopped()]):
            with self.assertRaises(RunStopped): docker_check(self.identifier)
        self.assertEqual(calls[-1][0], 'rm')

    def test_bundled_skills_are_discoverable_and_unsupported_names_rejected(self):
        for name in knowledge.SKILLS:
            text = knowledge.read_skill(name)
            self.assertIn("name: " + name, text)
            self.assertIn("description:", text)
        with self.assertRaises(ValueError): knowledge.read_skill("../private")


    def test_global_auth_protects_programmer_endpoints(self):
        from core.auth import AuthMiddleware
        app = FastAPI(); app.add_middleware(AuthMiddleware); app.include_router(router)
        client = TestClient(app)
        with patch('core.auth.session_user', return_value=None):
            self.assertEqual(client.get('/api/v1/programmer/status').status_code, 401)
            self.assertEqual(client.post('/api/v1/programmer/workspaces', headers={'X-Cora-Client':'ui'}, json={'title':'Test'}).status_code, 401)

    def test_optional_graphify_build_is_code_only_and_queries_real_graph(self):
        import shutil
        from programmer_agent.build_graph import build
        if not shutil.which('graphify'):
            self.skipTest('Optional Graphify CLI not installed')
        result = build(self.identifier)
        self.assertTrue(result['available'])
        self.assertGreater(result['nodes'], 0)
        self.assertTrue(knowledge.query_graph(self.identifier, 'add')['nodes'])


    def test_exact_workspace_payload_can_be_replayed_after_context_ends(self):
        from programmer_agent.programmer_tools import _workspace
        other = ws.create('Other', self.source)
        with ws.bind_workspace(self.identifier):
            self.assertEqual(_workspace(self.identifier), self.identifier)
            with self.assertRaises(ValueError): _workspace(other['id'])
        self.assertEqual(_workspace(self.identifier), self.identifier)

    def test_component_delivery_is_complete_immutable_and_lifecycle_requires_evidence(self):
        import io, zipfile
        from programmer_agent import components as cp
        ws.write(self.identifier, 'generated.py', 'value = 42')
        row = cp.register(self.identifier, 'Example', 'other', ['generated.py'], ['stdlib'], 'Review and integrate manually')
        with self.assertRaises(ValueError):
            cp.transition(self.identifier, row['id'], 'active', 'Declared', row['version'], row['workspace_digest'])
        run_check(self.identifier)
        self.assertEqual(cp.listing(self.identifier)[0]['status'], 'verified')
        row = cp.transition(self.identifier, row['id'], 'reviewed', 'Reviewed diff and evidence', row['version'], row['workspace_digest'])
        delivery = cp.deliver(self.identifier, row['id'])
        url = '/api/v1/programmer/workspaces/'+self.identifier+'/deliveries/'+delivery['id']
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            self.assertEqual(archive.read('files/generated.py'), b'value = 42')
            manifest = json.loads(archive.read('manifest.json'))
            self.assertFalse(manifest['activation_performed'])
            self.assertEqual(manifest['component']['status'], 'reviewed')
            self.assertEqual(len(manifest['checks']), 1)
            self.assertIn(b'No newline at end of file', archive.read('changes.patch'))
        ws.write(self.identifier, 'generated.py', 'value = 43', ws.read(self.identifier, 'generated.py')['sha256'])
        stale = cp.listing(self.identifier)[0]
        self.assertTrue(stale['stale']); self.assertEqual(stale['status'], 'draft')
        with self.assertRaises(ws.WorkspaceConflict): cp.deliver(self.identifier, row['id'])
        with self.assertRaises(ws.WorkspaceConflict): cp.transition(self.identifier, row['id'], 'integrated', 'Done', row['version'], row['workspace_digest'])
        self.assertEqual(self.client.get(url).content, response.content)
        updated = cp.register(self.identifier, row['title'], row['kind'], row['files'], [], row['integration'], row['id'])
        self.assertEqual(updated['version'], 2)
        self.assertEqual(updated['status'], 'draft')

    def test_failed_check_supersedes_prior_success_for_identical_source(self):
        from programmer_agent import components as cp
        row = cp.register(self.identifier, 'Example', 'other', ['sample.py'], [], 'Manual review')
        run_check(self.identifier)
        with patch('programmer_agent.checks.static_check', return_value={'profile': 'syntax', 'passed': False}):
            run_check(self.identifier)
        self.assertEqual(cp.listing(self.identifier)[0]['status'], 'draft')
        package = cp.deliver(self.identifier, row['id'])
        self.assertEqual(package['missing_checks'], ['syntax'])

    def test_contract_checks_do_not_import_adapters_and_reject_missing_types(self):
        from programmer_agent.contract_checks import contracts
        marker = Path(self.temp.name) / 'executed'
        content = knowledge.template('tool') + f'\nfrom pathlib import Path\nPath({str(marker)!r}).write_text("executed")\n'
        ws.write(self.identifier, 'generated_tools/example.py', content)
        result = contracts(self.identifier)
        self.assertTrue(result['passed'], result)
        self.assertFalse(marker.exists())
        ws.write(self.identifier, 'generated_tools/example.py', content.replace('value: str', 'value'), ws.read(self.identifier, 'generated_tools/example.py')['sha256'])
        self.assertFalse(contracts(self.identifier)['passed'])
        ws.write(self.identifier, 'generated_automations/draft.json', knowledge.template('automation'))
        self.assertTrue(any('Bozza incompleta' in e['error'] for e in contracts(self.identifier)['errors']))

    def test_frontend_profiles_use_fixed_isolated_commands_and_cleanup(self):
        ws.write(self.identifier, 'frontend/tsconfig.json', '{}')
        calls = []
        def docker(*args, **kwargs):
            calls.append(args)
            if args[0] == 'inspect': return 'false' if 'Running' in args[1] else '0'
            if args[0] == 'logs': return 'Build complete'
            return 'container'
        with patch('programmer_agent.checks.shutil.which', return_value='docker'), patch('programmer_agent.checks._docker', side_effect=docker):
            result = docker_check(self.identifier, 'frontend_build')
        self.assertTrue(result['passed'])
        command = calls[0]
        for flag in ('--entrypoint=node', '--network=none', '--pull=never', '--read-only'):
            self.assertIn(flag, command)
        self.assertIn("['build']", command[-1])
        self.assertIn('/opt/frontend/node_modules/.bin/tsc', command[-1])
        self.assertEqual(calls[-1][0], 'rm')
        with self.assertRaises(ValueError): docker_check(self.identifier, 'shell')

    def test_graph_view_is_bounded_and_contains_only_displayed_endpoints(self):
        graph = {'nodes': [{'id':str(i),'label':'symbol'} for i in range(100)],
                 'edges': [{'source':'0','target':str(i)} for i in range(1,100)]}
        knowledge.import_graph(self.identifier, graph, self.row['source_digest'])
        result = knowledge.graph_view(self.identifier, node_id='0')
        self.assertEqual(len(result['nodes']), 40)
        self.assertTrue(result['truncated'])
        ids = {str(n['id']) for n in result['nodes']}
        self.assertTrue(all(str(e['source']) in ids and str(e['target']) in ids for e in result['edges']))
        self.assertFalse(knowledge.graph_view(self.identifier, 'not present')['nodes'])

    def test_unavailable_checks_are_recorded_and_revoke_verified_state(self):
        from programmer_agent import components as cp
        row = cp.register(self.identifier, 'Example', 'other', ['sample.py'], [], 'Review')
        run_check(self.identifier)
        cp.transition(self.identifier, row['id'], 'reviewed', 'Reviewed', row['version'], row['workspace_digest'])
        with patch('programmer_agent.checks.static_check', side_effect=OSError('Parser unavailable')):
            with self.assertRaises(OSError): run_check(self.identifier)
        self.assertFalse(cp.check_history(self.identifier)[-1]['completed'])
        self.assertEqual(cp.listing(self.identifier)[0]['status'], 'draft')
        with self.assertRaises(ValueError):
            cp.transition(self.identifier, row['id'], 'integrated', 'Done', row['version'], row['workspace_digest'])

    def test_tool_registration_requires_tests_and_all_skipped_is_not_success(self):
        from programmer_agent import components as cp
        with self.assertRaises(ValueError):
            cp.register(self.identifier, 'Example', 'tool', ['sample.py'], [], 'Review')
        ws.write(self.identifier, 'tests/test_example.py', 'import unittest\n')
        def docker(*args, **kwargs):
            if args[0] == 'inspect': return 'false' if 'Running' in args[1] else '0'
            if args[0] == 'logs': return 'Ran 1 test\nOK (skipped=1)'
            return ''
        with patch('programmer_agent.checks.shutil.which', return_value='docker'), patch('programmer_agent.checks._docker', side_effect=docker):
            with self.assertRaises(ValueError): run_check(self.identifier, 'python_tests')
        self.assertFalse(cp.check_history(self.identifier)[-1]['passed'])
