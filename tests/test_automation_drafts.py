import copy
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.automation_drafts import get_draft, list_drafts, save_draft, validate_graph, VersionConflict


def graph():
    return dict(title="Bozza prova", description="", nodes=[
        dict(id="input", kind="trigger", label="Ingresso", x=30, y=50, config={}),
        dict(id="tool", kind="tool", label="Calcolatrice", x=300, y=50, config={"expression": "2+2"}, tool_id="calculator"),
        dict(id="output", kind="output", label="Risultato", x=600, y=50, config={}),
    ], edges=[dict(id="a", source="input", target="tool", label="successo"), dict(id="b", source="tool", target="output", label="successo")])


class DraftTests(unittest.TestCase):
    def test_persistent_create_reopen_and_optimistic_update(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            saved = save_draft(graph(), root=root, tool_ids={"calculator"})
            self.assertEqual(saved["status"], "draft")
            self.assertEqual(saved["version"], 1)
            self.assertEqual(saved["warnings"], [])
            self.assertEqual(get_draft(saved["id"], root)["nodes"], saved["nodes"])
            self.assertEqual(list_drafts(root)[0]["id"], saved["id"])
            saved["title"] = "Aggiornata"
            updated = save_draft(saved, saved["id"], 1, root, {"calculator"})
            self.assertEqual(updated["version"], 2)
            with self.assertRaises(VersionConflict):
                save_draft(saved, saved["id"], 1, root, {"calculator"})
            self.assertEqual(get_draft(saved["id"], root)["version"], 2)

    def test_incomplete_drafts_save_with_warnings(self):
        draft = graph()
        draft["edges"] = []
        draft["nodes"][1]["tool_id"] = None
        with tempfile.TemporaryDirectory() as tmp:
            saved = save_draft(draft, root=Path(tmp))
        self.assertGreater(len(saved["warnings"]), 0)
        self.assertEqual(saved["status"], "draft")

    def test_invalid_connections_and_unknown_tools_are_rejected(self):
        for change in ("self", "missing", "duplicate", "wrong_type", "output_source", "unknown_tool"):
            draft = graph()
            if change == "self": draft["edges"][0]["target"] = "input"
            if change == "missing": draft["edges"][0]["target"] = "missing"
            if change == "duplicate": draft["nodes"].append(copy.deepcopy(draft["nodes"][0]))
            if change == "wrong_type": draft["edges"][0]["source"] = []
            if change == "output_source": draft["edges"][0]["source"] = "output"
            if change == "unknown_tool": draft["nodes"][1]["tool_id"] = "absent"
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_graph(draft, {"calculator"})

    def test_cycles_and_invalid_coordinates_are_rejected(self):
        draft = graph()
        draft["nodes"][2]["kind"] = "tool"
        draft["edges"].append(dict(id="c", source="output", target="tool", label="successo"))
        with self.assertRaises(ValueError): validate_graph(draft)
        draft = graph()
        draft["nodes"][0]["x"] = float("nan")
        with self.assertRaises(ValueError): validate_graph(draft)

    def test_identifier_cannot_escape_draft_folder(self):
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(ValueError):
            get_draft("../../secret", Path(tmp))


if __name__ == "__main__":
    unittest.main()
