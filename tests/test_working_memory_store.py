"""Working memory SQL contract, without a database."""
import json
import unittest
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

from core.domain import working_memory


class WorkingMemoryTests(unittest.TestCase):
    def setUp(self):
        self.connection = MagicMock()
        @contextmanager
        def connect():
            yield self.connection
        target = patch.object(working_memory, "db_connection", connect)
        target.start()
        self.addCleanup(target.stop)

    def test_set_upserts_trimmed_keys_and_unicode_json_with_a_minimum_ttl(self):
        self.connection.execute.return_value.fetchone.return_value = {"agent_id": "a"}
        before = datetime.now(UTC)
        row = working_memory.set_working_memory(agent_id=" a ", thread_id=" t ", state={"città": 1}, ttl_minutes=0)
        self.assertEqual(row, {"agent_id": "a"})
        sql, params = self.connection.execute.call_args.args
        self.assertIn("ON CONFLICT (agent_id, thread_id)", sql)
        self.assertEqual(params[:3], ("a", "t", json.dumps({"città": 1}, ensure_ascii=False)))
        self.assertGreaterEqual(params[3], before + timedelta(minutes=1))
        self.assertLess(params[3], before + timedelta(minutes=2))
        self.connection.commit.assert_called_once()

    def test_clear_reports_whether_a_row_was_removed(self):
        for count, expected in ((1, True), (0, False)):
            self.connection.execute.return_value.rowcount = count
            self.assertIs(working_memory.clear_working_memory(agent_id="a", thread_id="t"), expected)

    def test_list_purges_expired_rows_before_reading(self):
        self.connection.execute.return_value.fetchall.return_value = [{"agent_id": "a"}]
        self.assertEqual(working_memory.list_working_memory(), [{"agent_id": "a"}])
        first, second = (call.args[0] for call in self.connection.execute.call_args_list)
        self.assertIn("DELETE FROM working_memory", first)
        self.assertIn("expires_at <= NOW()", first)
        self.assertIn("ORDER BY updated_at DESC", second)
        self.connection.commit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
