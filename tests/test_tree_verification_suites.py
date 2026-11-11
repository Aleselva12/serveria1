import json
import re
import unittest
from pathlib import Path

from core.additional_verifications import REGRESSIONS
from core.health_catalog import CATALOG
from core.tree_verification_suites import SUITES


class TreeVerificationSuiteTests(unittest.TestCase):
    def test_catalog_runner_mapping_and_scope_agree(self):
        root = Path(__file__).resolve().parents[1]
        nodes = {n["id"]: n for n in json.loads((root/"frontend/src/tree/cora-plan.snapshot.json").read_text(encoding="utf-8"))["nodes"]}
        model = (root/"frontend/src/tree/model.ts").read_text(encoding="utf-8")
        pairs = re.findall(r'"([^"\n]+)":\s*\[([^\]]*)\]', model)
        self.assertEqual(len(pairs), len(dict(pairs)), "Duplicate node mappings")
        mapping = {key: json.loads("["+value+"]") for key,value in pairs}
        for key, suite in SUITES.items():
            self.assertEqual(REGRESSIONS[key], suite["tests"])
            self.assertEqual(CATALOG[key]["kind"], "synthetic")
            self.assertEqual(CATALOG[key]["description"], suite["scope"])
            self.assertTrue(suite["tests"])
            for node in suite["nodes"]:
                self.assertIn(node, nodes)
                self.assertNotIn(nodes[node].get("status"), ("planned", "idea"))
                self.assertIn(key, mapping[node])
