import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.tool_definitions import definition
from core.tool_inventory import inventory


class DefinitionTests(unittest.TestCase):
    def test_calculator_signature_and_permission_stage(self):
        result = definition("tools.py:calculator_tool")
        self.assertEqual(result["parameters"], [dict(name="expression", type="str", required=True, default=None)])
        self.assertEqual(result["output_type"], "str")
        self.assertTrue(any(n["kind"] == "condition" for n in result["flow"]["nodes"]))
        self.assertIn("_calculator_tool.invoke", result["operations"])
        self.assertTrue(result["flow"]["edges"])

    def test_calendar_write_ends_at_a_proposal_not_a_completed_event(self):
        result = definition("core/calendar_tools.py:calendar_create_event")
        self.assertEqual(result["flow"]["nodes"][-1]["label"], "Proposta da approvare")
        parameter = next(p for p in result["parameters"] if p["name"] == "all_day")
        self.assertFalse(parameter["required"])
        self.assertEqual(parameter["default"], "False")

    def test_all_current_tools_have_readable_diagrams_with_valid_edges(self):
        for entry in inventory()["entries"]:
            with self.subTest(entry=entry["id"]):
                result = definition(entry["id"])
                ids = {n["id"] for n in result["flow"]["nodes"]}
                self.assertTrue(ids)
                self.assertTrue(all(e["source"] in ids and e["target"] in ids for e in result["flow"]["edges"]))

    def test_arbitrary_source_paths_cannot_be_requested(self):
        with self.assertRaises(KeyError):
            definition("../../.env:secret")


if __name__ == "__main__":
    unittest.main()
