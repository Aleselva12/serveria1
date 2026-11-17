"""Structure workspace: plans, evaluations and management records on disk."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.domain import plans
from core.orchestration import DEFAULT_PLAN_OWNER


class StructureWorkspaceTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name).resolve()
        roots = {"plan": self.root / "plans", "evaluation": self.root / "evaluations",
                 "management": self.root / "management"}
        self.granted = []
        for target in (patch.object(plans, "WORKSPACE_ROOT", self.root),
                       patch.object(plans, "PLANS_ROOT", roots["plan"]),
                       patch.object(plans, "EVALUATIONS_ROOT", roots["evaluation"]),
                       patch.object(plans, "MANAGEMENT_ROOT", roots["management"]),
                       patch.dict(plans.ALLOWED_ARTIFACT_TYPES, roots),
                       patch.object(plans, "require_permission",
                                    side_effect=lambda actor, action: self.granted.append((actor, action)))):
            target.start()
            self.addCleanup(target.stop)

    def plan(self, **overrides):
        values = {"objective": "  Riordino pagine  ", "tasks": [{"description": "Inventario"}]}
        return plans.create_plan_record(**{**values, **overrides})

    def test_plan_normalizes_tasks_and_forces_the_orchestrator_owner(self):
        record = self.plan(priority=" HIGH ", tasks=[
            {"description": " Inventario ", "owner": "someone_else", "status": " DONE "},
            {"id": "custom", "description": "Proposta", "dependencies": ("task_01",)},
        ])
        self.assertEqual(record["objective"], "Riordino pagine")
        self.assertEqual(record["priority"], "high")
        self.assertEqual(record["status"], "planned")
        first, second = record["tasks"]
        self.assertEqual((first["id"], first["owner"], first["status"]), ("task_01", DEFAULT_PLAN_OWNER, "done"))
        self.assertEqual(first["target_component"], "unassigned")
        self.assertEqual((second["id"], second["dependencies"]), ("custom", ["task_01"]))
        self.assertEqual(record["created_at"], record["updated_at"])
        self.assertIn(("structure_agent", "create_plan"), self.granted)

    def test_invalid_plans_are_rejected_before_anything_is_written(self):
        for overrides in ({"objective": "   "}, {"tasks": []}, {"tasks": [{"description": " "}]}):
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                self.plan(**overrides)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_saved_records_round_trip_and_list_newest_first(self):
        plan_path = plans.save_plan_record(self.plan(objective="Piano / con: simboli!"))
        self.assertEqual(plan_path.parent, self.root / "plans")
        self.assertTrue(plan_path.name.startswith("piano-con-simboli__"))
        self.assertEqual(list(plan_path.parent.glob("*.tmp")), [])
        evaluation = plans.create_evaluation_record(target="Pagina File", criteria=["chiara"], passed=["chiara"])
        plans.save_evaluation_record(evaluation)
        management = plans.create_management_record(title="Stato", summary="  ok  ")
        self.assertEqual(management["summary"], "ok")
        plans.save_management_record(management)

        listed = plans.list_artifacts()
        self.assertEqual({item["type"] for item in listed}, {"plan", "evaluation", "management"})
        self.assertEqual([item["type"] for item in plans.list_artifacts(" PLAN ")], ["plan"])
        self.assertEqual(plans.list_artifacts("unknown"), [])
        read = plans.read_artifact(f"plans/{plan_path.name}")
        self.assertEqual(read["objective"], "Piano / con: simboli!")

    def test_empty_slug_uses_the_record_type(self):
        record = self.plan(objective="àèì")
        self.assertTrue(plans.save_plan_record(record).name.startswith("plan__"))

    def test_listing_is_bounded(self):
        folder = self.root / "plans"
        folder.mkdir()
        for index in range(105):
            (folder / f"p{index}.json").write_text("{}", encoding="utf-8")
        self.assertEqual(len(plans.list_artifacts("plan")), 100)

    def test_read_is_confined_to_json_inside_the_workspace(self):
        outside = self.root.parent / (self.root.name + "-outside.json")
        outside.write_text(json.dumps({"secret": True}), encoding="utf-8")
        self.addCleanup(outside.unlink)
        (self.root / "note.txt").write_text("x", encoding="utf-8")
        with self.assertRaises(ValueError):
            plans.read_artifact("../" + outside.name)
        with self.assertRaises(ValueError):
            plans.read_artifact(str(outside))
        with self.assertRaises(ValueError):
            plans.read_artifact("note.txt")
        with self.assertRaises(FileNotFoundError):
            plans.read_artifact("plans/missing.json")

    def test_denied_permission_stops_the_save(self):
        with patch.object(plans, "require_permission", side_effect=PermissionError("negato")):
            with self.assertRaises(PermissionError):
                plans.save_plan_record({"plan_id": "x", "objective": "y"})
        self.assertFalse((self.root / "plans").exists())


class StructureToolTests(unittest.TestCase):
    def test_save_tools_write_through_the_workspace_with_relative_paths(self):
        from structure_agent import structure_tools as tools
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(plans, "WORKSPACE_ROOT", Path(folder)), \
                patch.object(plans, "PLANS_ROOT", Path(folder) / "plans"), \
                patch.object(plans, "require_permission"):
            native = tools.structure_save_plan.func.__wrapped__
            result = json.loads(native(objective="Obiettivo", tasks=[{"description": "Passo"}]))
            self.assertTrue(result["saved"])
            self.assertTrue(result["relative_path"].startswith("plans/obiettivo__"))
            self.assertTrue((Path(folder) / result["relative_path"]).is_file())

    def test_tool_list_has_unique_names_and_rejects_unknown_component_kinds(self):
        from structure_agent import structure_tools as tools
        names = [tool.name for tool in tools.STRUCTURE_TOOLS]
        self.assertEqual(len(names), len(set(names)))
        with patch.object(tools, "require_permission"):
            answer = json.loads(tools.structure_components.func.__wrapped__(kind="bogus"))
        self.assertEqual(answer["status"], "error")


if __name__ == "__main__":
    unittest.main()
