import hashlib
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "database" / "schema.sql"
PROJECT_MIGRATION = ROOT / "database" / "migrations" / "0005_conversation_projects.sql"

# Git blob id of database/schema.sql in the installed baseline commit 5161d549e180...
# This is intentionally fixed: once 0001 is recorded in PostgreSQL, changing it
# would make existing databases impossible to migrate safely.
EXPECTED_BASELINE_BLOB = "74a65cf6be9dfc68dd3deee90b456ac54f6e523f"


def git_blob_sha1(data: bytes) -> str:
    payload = b"blob " + str(len(data)).encode("ascii") + b"\0" + data
    return hashlib.sha1(payload).hexdigest()


class DatabaseMigrationContractTests(unittest.TestCase):
    def test_0001_baseline_is_immutable(self):
        self.assertEqual(git_blob_sha1(BASELINE.read_bytes()), EXPECTED_BASELINE_BLOB)

    def test_conversation_projects_live_in_0005_not_baseline(self):
        baseline = BASELINE.read_text(encoding="utf-8")
        migration = PROJECT_MIGRATION.read_text(encoding="utf-8")
        self.assertNotIn("conversation_projects", baseline)
        self.assertIn("CREATE TABLE IF NOT EXISTS conversation_projects", migration)
        self.assertIn("ADD COLUMN IF NOT EXISTS project_id", migration)


if __name__ == "__main__":
    unittest.main()
