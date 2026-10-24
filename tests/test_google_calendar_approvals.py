"""Isolated Google Calendar and owner-approval contracts; no Google account required."""
import json
import os
import unittest
from datetime import datetime
from unittest.mock import Mock, patch
from uuid import uuid4

from core import google_calendar
from core import calendar_api
from core import calendar as local
from core.calendar_tools import calendar_tools_for

DATA = {
    "title": "Visita cliente",
    "start": "2026-10-26T09:00:00+01:00",
    "end": "2026-10-26T10:00:00+01:00",
}


class GoogleCalendarApprovalTests(unittest.TestCase):
    def test_etag_is_real_revision_and_daylight_saving_is_preserved(self):
        event = {
            "id": "google_event_non_uuid",
            "etag": '"revision-A"',
            "summary": "Test",
            "start": {"date": "2026-03-29"},
            "end": {"date": "2026-03-30"},
        }
        normalized = google_calendar.normalize(event)
        self.assertEqual(normalized["start"], "2026-03-29T00:00:00+01:00")
        self.assertEqual(normalized["end"], "2026-03-30T00:00:00+02:00")
        self.assertTrue(normalized["all_day"])
        event["etag"] = '"revision-B"'
        self.assertNotEqual(normalized["version"], google_calendar.normalize(event)["version"])

    def test_google_update_requires_fresh_revision_and_if_match(self):
        current = {
            "id": "non-uuid-id",
            "etag": '"old"',
            "version": 42,
        }
        request = Mock()
        request.headers = {}
        request.execute.return_value = {
            "id": "non-uuid-id", "etag": '"new"',
            "start": {"dateTime": DATA["start"]},
            "end": {"dateTime": DATA["end"]},
        }
        service = Mock()
        service.events.return_value.patch.return_value = request
        with patch.object(google_calendar, "get_event", return_value=current), patch.object(google_calendar, "service", return_value=service):
            with self.assertRaises(local.CalendarConflict):
                google_calendar.update_event(current["id"], DATA, expected_version=41)
            self.assertFalse(request.execute.called)
            result = google_calendar.update_event(current["id"], DATA, expected_version=42)
        self.assertEqual(request.headers["If-Match"], '"old"')
        self.assertEqual(result["id"], current["id"])

    def test_google_update_rejects_etag_changed_during_request(self):
        from httplib2 import Response
        from googleapiclient.errors import HttpError
        current = {"id": "non-uuid-id", "etag": '"old"', "version": 42}
        request = Mock()
        request.headers = {}
        request.execute.side_effect = HttpError(Response({"status": 412}), b"precondition failed")
        service = Mock()
        service.events.return_value.patch.return_value = request
        with patch.object(google_calendar, "get_event", return_value=current), \
             patch.object(google_calendar, "service", return_value=service):
            with self.assertRaises(local.CalendarConflict):
                google_calendar.update_event(current["id"], DATA, expected_version=42)
        self.assertEqual(request.headers["If-Match"], '"old"')

    def test_google_agent_write_is_durable_proposal_not_a_direct_write(self):
        tool = next(t for t in calendar_tools_for("supervisor") if t.name == "calendar_create_event")
        with patch.object(google_calendar, "token_exists", return_value=True), \
             patch.object(google_calendar, "connection_fingerprint", return_value="fingerprint"), \
             patch.object(google_calendar, "create_event") as create, \
             patch("core.permissions.policy_overrides", return_value={}), \
             patch("core.operation_journal.begin", return_value=None), \
             patch("core.governance.propose", return_value={"id": uuid4()}) as propose:
            result = tool.invoke(DATA)
        wire = json.loads(result)
        self.assertEqual(wire["status"], "pending")
        self.assertFalse(create.called)
        self.assertIn("calendar_google_provider:fingerprint", propose.call_args.kwargs["actions"])

    def test_calendar_ui_only_lists_approvals_for_calendar_tools(self):
        calendar_row = dict(id=uuid4(), actor="supervisor",
                            capability_id="supervisor.calendar_delete_event",
                            payload={"event_id": "google_non_uuid", "version": 3, "reason": "Prova"},
                            status="pending", created_at=datetime(2026, 10, 24))
        other = {**calendar_row, "id": uuid4(), "capability_id": "supervisor.forget_memory_tool"}
        with patch.object(google_calendar, "token_exists", return_value=True), \
             patch.object(calendar_api.governance, "list_approvals", return_value=[calendar_row, other]):
            pending = calendar_api.proposals()
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["event_id"], "google_non_uuid")
        self.assertEqual(pending[0]["expected_version"], 3)


@unittest.skipUnless(os.getenv('CORA_RUNTIME_TEST_DATABASE_URL'), 'Requires disposable PostgreSQL+pgvector')
class GoogleApprovalPostgresTests(unittest.TestCase):
    def test_durable_owner_approval_once_and_oauth_switch_blocks_execution(self):
        from core import governance, permissions
        from core.database import db_connection, close_pool
        governance.load_capabilities()
        tool = next(t for t in calendar_tools_for('supervisor') if t.name == 'calendar_create_event')
        identifiers = []
        try:
            with patch.object(google_calendar, 'token_exists', return_value=True), \
                 patch.object(google_calendar, 'connection_fingerprint', return_value='synthetic-account-A') as fingerprint, \
                 patch.object(permissions, 'policy_overrides', return_value={}), \
                 patch.object(google_calendar, 'create_event', return_value={'id': 'synthetic-google-event'}) as create:
                proposal = json.loads(tool.invoke({**DATA, 'title': 'Synthetic ' + str(uuid4())}))
                self.assertEqual(proposal['status'], 'pending')
                identifiers.append(proposal['approval_id'])
                create.assert_not_called()
                result = governance.resolve(identifiers[-1], True, 'synthetic-owner')
                self.assertEqual(result['status'], 'approved')
                self.assertEqual(create.call_args.kwargs['request_id'], identifiers[-1])
                with self.assertRaises(ValueError):
                    governance.resolve(identifiers[-1], True, 'synthetic-owner')
                self.assertEqual(create.call_count, 1)
                proposal = json.loads(tool.invoke({**DATA, 'title': 'Synthetic ' + str(uuid4())}))
                identifiers.append(proposal['approval_id'])
                fingerprint.return_value = 'synthetic-account-B'
                with self.assertRaises(RuntimeError):
                    governance.resolve(identifiers[-1], True, 'synthetic-owner')
                self.assertEqual(create.call_count, 1)
                with db_connection() as conn:
                    row = conn.execute('SELECT status FROM action_approvals WHERE id=%s', (identifiers[-1],)).fetchone()
                self.assertIn(row['status'], ('failed', 'uncertain'))
        finally:
            with db_connection() as conn:
                for identifier in identifiers:
                    conn.execute('DELETE FROM action_approvals WHERE id=%s', (identifier,))
            close_pool()


if __name__ == "__main__":
    unittest.main()
