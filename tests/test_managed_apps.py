import tempfile
import unittest
from pathlib import Path
from updater.managed_apps import AppManager

class ManagedAppsTests(unittest.TestCase):
    def test_disabled_by_default_and_allowlist(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager=AppManager({"managed_apps_root":tmp})
            state=manager.status()
            self.assertFalse(state["available"])
            self.assertEqual([x["id"] for x in state["apps"]],["magazzino-tele"])
            self.assertFalse(state["apps"][0]["installed"])
            with self.assertRaises(ValueError):
                manager.submit("magazzino-tele","install")
            with self.assertRaises(ValueError):
                manager.path("not-approved")

    def test_action_rejects_arbitrary_operations(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager=AppManager({"managed_apps_root":tmp,"managed_apps_enabled":True})
            with self.assertRaises(ValueError):
                manager.submit("magazzino-tele","shell")
            with self.assertRaises(ValueError):
                manager.submit("../etc","install")

if __name__=="__main__":unittest.main()
