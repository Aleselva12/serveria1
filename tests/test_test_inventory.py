import unittest
from pathlib import Path

from core.health_catalog import CATALOG
from core.verify.test_inventory import (
    PREEXISTING_LIVE_E2E_CHECKS,
    TARGETED_E2E_NODES,
    TARGETED_NEW_E2E,
    assert_live_e2e_scope,
    inventory,
)


class TestInventoryTests(unittest.TestCase):
    def test_every_repository_unittest_module_is_visible_once(self):
        rows = inventory()["tests"]
        files = sorted(path.stem for path in (Path(__file__).resolve().parent).glob("test_*.py"))
        self.assertEqual(sorted(row["module"] for row in rows), files)
        self.assertEqual(len(rows), len({row["module"] for row in rows}))

    def test_inventory_distinguishes_runner_checks_from_repository_only_tests(self):
        snapshot = inventory()
        self.assertEqual(snapshot["total"], snapshot["runnerLinked"] + snapshot["repositoryOnly"])
        self.assertGreater(snapshot["runnerLinked"], 0)
        self.assertGreater(snapshot["repositoryOnly"], 0)
        for row in snapshot["tests"]:
            self.assertEqual(row["runnerLinked"], bool(row["linkedChecks"]))

    def test_new_live_e2e_scope_is_limited_to_owner_selected_nodes(self):
        assert_live_e2e_scope(CATALOG)
        self.assertIn("memory_e2e", PREEXISTING_LIVE_E2E_CHECKS)
        self.assertTrue(TARGETED_NEW_E2E)
        for nodes in TARGETED_NEW_E2E.values():
            self.assertTrue(set(nodes) <= TARGETED_E2E_NODES)

    def test_inventory_does_not_relabel_repository_tests_as_runtime_evidence(self):
        snapshot = inventory()
        self.assertEqual(snapshot["scope"], "inventory_only")
        self.assertTrue(all(row["role"] in {"verification_runner", "repository_test"} for row in snapshot["tests"]))


if __name__ == "__main__":
    unittest.main()
