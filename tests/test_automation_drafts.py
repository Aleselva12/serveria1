import copy
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.domain.automation_drafts import (
    VersionConflict,
    delete_draft,
    duplicate_draft,
    get_draft,
    list_drafts,
    save_draft,
    validate_graph,
)


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

    def test_schema_warnings_flag_missing_unknown_and_uncontracted_tools(self):
        schema = {"calculator": {"type": "object", "properties": {"expression": {"type": "string"}, "precision": {"type": "integer"}}, "required": ["expression", "precision"]}}
        draft = graph()
        draft["nodes"][1]["config"] = {"expression": "2+2", "extra": 1}
        warnings = validate_graph(draft, {"calculator"}, schema)["warnings"]
        self.assertIn("Calcolatrice: manca il parametro obbligatorio «precision».", warnings)
        self.assertIn("Calcolatrice: il parametro «extra» non è previsto dal tool.", warnings)
        self.assertNotIn("expression", " ".join(w for w in warnings if "manca" in w))
        warnings = validate_graph(graph(), {"calculator"}, {})["warnings"]
        self.assertEqual(warnings, ["Calcolatrice: il tool non ha un contratto eseguibile; potrà restare solo nella bozza."])
        self.assertEqual(validate_graph(graph(), {"calculator"})["warnings"], [])

    def test_delete_requires_current_version_and_duplicate_creates_new_draft(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            saved = save_draft(graph(), root=root, tool_ids={"calculator"})
            clone = duplicate_draft(saved["id"], root, {"calculator"})
            self.assertNotEqual(clone["id"], saved["id"])
            self.assertEqual(clone["version"], 1)
            self.assertEqual(clone["title"], "Copia di Bozza prova")
            self.assertEqual(clone["nodes"], saved["nodes"])
            with self.assertRaises(VersionConflict):
                delete_draft(saved["id"], 2, root)
            delete_draft(saved["id"], 1, root)
            self.assertEqual([row["id"] for row in list_drafts(root)], [clone["id"]])
            with self.assertRaises(FileNotFoundError):
                delete_draft(saved["id"], 1, root)
            with self.assertRaises(ValueError):
                delete_draft("../x", 1, root)

    def test_identifier_cannot_escape_draft_folder(self):
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(ValueError):
            get_draft("../../secret", Path(tmp))


if __name__ == "__main__":
    unittest.main()
