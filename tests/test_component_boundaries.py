"""Integration boundaries: catching cross-program regressions without real accounts.

These tests fail with the broken hop instead of merely asserting HTTP 200.
They run in CI and complement the production 5-minute structural checks.
"""
import unittest
from unittest.mock import patch
from core import project_contracts, project_checks
from core.health_catalog import CATALOG, COMPONENTS


class CatalogTests(unittest.TestCase):
    def test_one_source_contains_every_automated_probe_and_no_dangling_dependencies(self):
        self.assertEqual(set(project_checks._PROBES),
                         {key for key, item in CATALOG.items() if item["automated"]})
        for key,item in CATALOG.items():
            with self.subTest(check=key):
                self.assertIn(item["component"],COMPONENTS)
                self.assertEqual(key,item["id"])
                self.assertTrue(set(item["dependsOn"]) <= set(CATALOG))
                if not item["automated"]:
                    self.assertNotIn(key,project_checks._PROBES)

    def test_diagnostic_route_failure_names_breaking_boundary(self):
        with patch.object(project_contracts,"_routes",return_value=set()):
            status,detail = project_contracts.chat_contract()
        self.assertEqual(status,"fail")
        self.assertIn("UI/Chat",detail)

    def test_chat_supervisor_delegates_to_specialists(self):
        status,detail = project_contracts.chat_contract()
        self.assertEqual(status,"pass",detail)

    def test_chat_wiring_fails_when_delegations_disappear(self):
        import graph
        with patch.object(graph,"supervisor_tools",[]):
            status,detail = project_contracts.chat_contract()
        self.assertEqual(status,"fail")
        self.assertIn("orchestratore",detail)

    def test_audio_to_word_route_and_approval_wiring(self):
        status,detail=project_contracts.audio_word_contract()
        self.assertEqual(status,"pass",detail)

    def test_calendar_approval_provider_route(self):
        status,detail=project_contracts.calendar_contract()
        self.assertEqual(status,"pass",detail)

    def test_worker_api_to_model_binding(self):
        status,detail=project_contracts.worker_contract()
        self.assertEqual(status,"pass",detail)

    def test_non_e2e_checks_never_create_external_side_effects(self):
        with patch.object(project_checks,"_persist",side_effect=AssertionError("no persistence without scheduler")):
            with patch.dict(project_checks._PROBES,{"word_sample":project_checks._word_sample},clear=True):
                result=project_checks.run_once()
        self.assertEqual(result["checks"][0]["status"],"pass")
        self.assertFalse(result["persisted"])

    def test_registry_is_not_silently_persisted_when_database_unreachable(self):
        with patch("core.database.db_connection",side_effect=OSError("private database error")):
            result=project_checks.health_dashboard()
        self.assertEqual(result["historyStore"],"unavailable")
        self.assertEqual(set(result["components"]),set(COMPONENTS))


if __name__=="__main__":
    unittest.main()
