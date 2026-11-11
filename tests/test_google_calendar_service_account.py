"""Service account contracts: no Google network calls or private keys."""
import json
import tempfile
import unittest
from datetime import UTC
from pathlib import Path
from unittest.mock import patch

from core import google_calendar as provider


class ServiceAccountTests(unittest.TestCase):
    def test_service_account_needs_explicit_shared_calendar(self):
        with patch.object(provider, "SERVICE_ACCOUNT_PATH", Path("/not/required.json")), patch.dict("os.environ", {"CORA_GOOGLE_CALENDAR_ID": "primary"}):
            with self.assertRaises(provider.GoogleCalendarNotConnected):
                provider.calendar_id()

    def test_service_account_connection_fingerprint_is_pinned_to_calendar(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "service.json"
            path.write_text(json.dumps({"type": "service_account", "client_email": "cora@example.test"}))
            with patch.object(provider, "SERVICE_ACCOUNT_PATH", path), patch.dict("os.environ", {"CORA_GOOGLE_CALENDAR_ID": "shared@example.test"}):
                self.assertTrue(provider.token_exists())
                first = provider.connection_fingerprint()
                self.assertNotIn("cora@example.test", first)
                with patch.dict("os.environ", {"CORA_GOOGLE_CALENDAR_ID": "different@example.test"}):
                    self.assertNotEqual(first, provider.connection_fingerprint())

    def test_missing_key_is_not_silently_replaced_with_oauth(self):
        with patch.object(provider, "SERVICE_ACCOUNT_PATH", Path("/not/there.json")), patch.dict("os.environ", {"CORA_GOOGLE_CALENDAR_ID": "shared@example.test"}):
            with self.assertRaises(provider.GoogleCalendarNotConnected):
                provider._credentials()

    def test_read_and_write_target_shared_calendar(self):
        from datetime import datetime, timedelta
        from unittest.mock import MagicMock
        service = MagicMock()
        service.events.return_value.list.return_value.execute.return_value = {"items": []}
        with patch.object(provider, "SERVICE_ACCOUNT_PATH", Path("/not/required.json")), patch.dict("os.environ", {"CORA_GOOGLE_CALENDAR_ID": "shared@example.test"}), patch.object(provider, "service", return_value=service):
            provider.list_events(datetime.now(UTC), datetime.now(UTC) + timedelta(days=1))
        self.assertEqual(service.events.return_value.list.call_args.kwargs["calendarId"], "shared@example.test")


if __name__ == "__main__":
    unittest.main()
