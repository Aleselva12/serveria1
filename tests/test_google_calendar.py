import unittest
import os
from unittest.mock import MagicMock, patch
from datetime import datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient

from core import google_calendar
from core.calendar_api import router


class GoogleCalendarProviderTests(unittest.TestCase):
    def test_status_without_token_does_not_contact_google_or_expose_path(self):
        with patch.object(google_calendar, "token_exists", return_value=False), \
                patch.object(google_calendar, "service") as service:
            result = google_calendar.status()
        self.assertFalse(result["connected"])
        self.assertEqual(result["provider"], "local")
        self.assertNotIn("tokenPath", result)
        service.assert_not_called()

    def test_status_success_preserves_provider_fields_without_token_path(self):
        service = MagicMock()
        service.events.return_value.list.return_value.execute.return_value = {"nextSyncToken": "secret-sync"}
        with patch.object(google_calendar, "token_exists", return_value=True), \
                patch.object(google_calendar, "service", return_value=service):
            result = google_calendar.status()
        self.assertTrue(result["connected"])
        self.assertTrue(result["reachable"])
        self.assertTrue(result["nextSyncTokenAvailable"])
        self.assertNotIn("tokenPath", result)
        self.assertNotIn("secret-sync", str(result))

    def test_provider_api_redacts_credentials_and_upstream_exceptions(self):
        app = FastAPI()
        app.include_router(router)
        secret = "refresh_token=secret-token /private/token.json https://google.test/?key=secret-key"
        for stage in ("credentials", "request"):
            with self.subTest(stage=stage):
                service = MagicMock()
                service.events.return_value.list.return_value.execute.side_effect = RuntimeError(secret)
                with patch.dict(os.environ, {"CORA_CALENDAR_TOKEN": "owner"}), \
                        patch.object(google_calendar, "token_exists", return_value=True), \
                        patch.object(google_calendar, "service", **(
                            {"side_effect": ValueError(secret)} if stage == "credentials"
                            else {"return_value": service}
                        )), TestClient(app) as client:
                    self.assertEqual(client.get("/api/v1/calendar/provider").status_code, 401)
                    response = client.get("/api/v1/calendar/provider", headers={"Authorization": "Bearer owner"})
                self.assertEqual(response.status_code, 200)
                result = response.json()
                self.assertTrue(result["connected"])
                self.assertFalse(result["reachable"])
                self.assertEqual(result["error"], "Google Calendar non disponibile. Verifica il collegamento e riprova.")
                self.assertNotIn("tokenPath", result)
                for sensitive in ("secret-token", "/private/", "google.test", "secret-key", "ValueError", "RuntimeError"):
                    self.assertNotIn(sensitive, response.text)

    def test_normalize_timed_event_and_popup_reminder(self):
        event = google_calendar.normalize({
            "id": "google-1",
            "summary": "Sveglia test",
            "description": "Prova",
            "start": {"dateTime": "2026-10-23T08:00:00+02:00"},
            "end": {"dateTime": "2026-10-23T08:15:00+02:00"},
            "reminders": {"useDefault": False, "overrides": [{"method": "popup", "minutes": 30}]},
            "sequence": 2,
            "created": "2026-10-22T20:00:00Z",
            "updated": "2026-10-22T20:10:00Z",
        })
        self.assertEqual(event["id"], "google-1")
        self.assertEqual(event["reminder_minutes"], 30)
        self.assertFalse(event["all_day"])
        self.assertEqual(event["version"], 3)

    def test_google_body_keeps_rome_timezone_and_reminder(self):
        body = google_calendar._google_body({
            "title": "Appuntamento",
            "start": "2026-10-23T08:00:00+02:00",
            "end": "2026-10-23T08:30:00+02:00",
            "all_day": False,
            "notes": "Nota",
            "reminder_minutes": 15,
        })
        self.assertEqual(body["start"]["timeZone"], "Europe/Rome")
        self.assertEqual(body["reminders"]["overrides"][0], {"method": "popup", "minutes": 15})
        self.assertEqual(body["extendedProperties"]["private"]["coraManaged"], "true")

    def test_publish_local_events_is_idempotent(self):
        class Call:
            def __init__(self, value):
                self.value = value
            def execute(self):
                return self.value

        class Events:
            def __init__(self):
                self.inserted = []
            def list(self, **kwargs):
                return Call({
                    "items": [{
                        "id": "already-google",
                        "extendedProperties": {
                            "private": {
                                "coraManaged": "true",
                                "coraLocalEventId": "local-1",
                            }
                        },
                    }]
                })
            def insert(self, **kwargs):
                self.inserted.append(kwargs["body"])
                return Call({"id": "google-2"})

        class Service:
            def __init__(self):
                self.resource = Events()
            def events(self):
                return self.resource

        fake = Service()
        events = [
            {
                "id": "local-1",
                "title": "Già inviato",
                "start": "2026-10-23T08:00:00+02:00",
                "end": "2026-10-23T08:30:00+02:00",
                "all_day": False,
                "notes": "",
                "reminder_minutes": 30,
            },
            {
                "id": "local-2",
                "title": "Nuovo",
                "start": "2026-10-24T08:00:00+02:00",
                "end": "2026-10-24T08:30:00+02:00",
                "all_day": False,
                "notes": "",
                "reminder_minutes": 15,
            },
        ]
        with patch.object(google_calendar, "service", return_value=fake):
            result = google_calendar.publish_local_events(events)
        self.assertEqual(result["sent"], 1)
        self.assertEqual(result["skipped"], 1)
        self.assertEqual(result["failed"], 0)
        self.assertEqual(
            fake.resource.inserted[0]["extendedProperties"]["private"]["coraLocalEventId"],
            "local-2",
        )

    def test_google_body_all_day_uses_exclusive_end_date(self):
        body = google_calendar._google_body({
            "title": "Giornata",
            "start": "2026-10-23T00:00:00+02:00",
            "end": "2026-10-24T00:00:00+02:00",
            "all_day": True,
            "notes": "",
            "reminder_minutes": None,
        })
        self.assertEqual(body["start"], {"date": "2026-10-23"})
        self.assertEqual(body["end"], {"date": "2026-10-24"})
        self.assertEqual(body["reminders"], {"useDefault": False, "overrides": []})


    def test_sync_uses_deterministic_ids_even_when_listing_is_stale(self):
        from googleapiclient.errors import HttpError
        from httplib2 import Response
        class Request:
            def __init__(self, call): self.call = call
            def execute(self): return self.call()
        class Events:
            def __init__(self): self.saved = {}; self.insert_count = 0
            def list(self, **kwargs): return Request(lambda: {"items": []})
            def insert(self, **kwargs):
                body = kwargs["body"]
                def insert_once():
                    if body["id"] in self.saved:
                        raise HttpError(Response({"status": 409}), b"Duplicate ID")
                    self.insert_count += 1
                    self.saved[body["id"]] = body
                    return body
                return Request(insert_once)
            def get(self, **kwargs):
                return Request(lambda: self.saved[kwargs["eventId"]])
        class Service:
            def __init__(self): self.resource = Events()
            def events(self): return self.resource
        fake = Service()
        local = [{
            "id": "local-1", "title": "Prova", "start": "2026-10-24T10:00:00+02:00",
            "end": "2026-10-24T11:00:00+02:00", "all_day": False,
            "notes": "", "reminder_minutes": None,
        }]
        with patch.object(google_calendar, "service", return_value=fake):
            first = google_calendar.publish_local_events(local)
            second = google_calendar.publish_local_events(local)
        self.assertEqual(first["sent"], 1)
        self.assertEqual(second["sent"], 0)
        self.assertEqual(second["skipped"], 1)
        self.assertEqual(fake.resource.insert_count, 1)

    def test_timeout_after_insert_is_reconciled_without_retry(self):
        class Request:
            def __init__(self, call): self.call = call
            def execute(self): return self.call()
        class Events:
            def __init__(self): self.saved = {}; self.inserts = 0
            def list(self, **kwargs): return Request(lambda: {"items":[]})
            def insert(self, **kwargs):
                def commit_then_timeout():
                    self.inserts += 1
                    self.saved[kwargs["body"]["id"]] = kwargs["body"]
                    raise TimeoutError("connection lost after commit")
                return Request(commit_then_timeout)
            def get(self, **kwargs):
                return Request(lambda: self.saved[kwargs["eventId"]])
        class Service:
            def __init__(self): self.resource = Events()
            def events(self): return self.resource
        fake = Service()
        with patch.object(google_calendar, "service", return_value=fake):
            result = google_calendar.publish_local_events([{
                "id":"id-1", "title":"Test", "start":"2026-10-24T10:00:00+02:00",
                "end":"2026-10-24T11:00:00+02:00", "all_day":False,
            }])
        self.assertEqual(result["skipped"], 1)
        self.assertEqual(result["failed"], 0)
        self.assertEqual(fake.resource.inserts, 1)


    def test_manual_create_reuses_request_id_after_lost_ack(self):
        class Request:
            def __init__(self, call): self.call = call
            def execute(self): return self.call()
        class Events:
            def __init__(self): self.saved = {}; self.created = 0
            def insert(self, **kwargs):
                body = kwargs["body"]
                def insert_once():
                    if body["id"] in self.saved:
                        raise TimeoutError("lost acknowledgement")
                    self.created += 1
                    self.saved[body["id"]] = {**body, "etag": '"v1"'}
                    return self.saved[body["id"]]
                return Request(insert_once)
            def get(self, **kwargs): return Request(lambda: self.saved[kwargs["eventId"]])
        class Service:
            def __init__(self): self.resource = Events()
            def events(self): return self.resource
        data = {"title":"Impegno", "start":"2026-10-24T10:00:00+02:00",
                "end":"2026-10-24T11:00:00+02:00", "all_day":False}
        fake = Service()
        with patch.object(google_calendar, "service", return_value=fake):
            first = google_calendar.create_event(data, request_id="stable-key")
            again = google_calendar.create_event(data, request_id="stable-key")
        self.assertEqual(first["id"], again["id"])
        self.assertEqual(fake.resource.created, 1)

    def test_manual_replay_rejects_changed_payload(self):
        data = {"title": "Test", "start": "2026-10-24T10:00:00+02:00",
                "end": "2026-10-24T11:00:00+02:00", "notes": "original"}
        original = google_calendar._google_body(data)
        service = MagicMock()
        service.events.return_value.insert.return_value.execute.side_effect = TimeoutError()
        service.events.return_value.get.return_value.execute.return_value = original
        for change in ({"start": "2026-10-24T10:30:00+02:00"},
                       {"end": "2026-10-24T12:00:00+02:00"},
                       {"notes": "changed"}, {"reminder_minutes": 12}):
            with self.subTest(change=change), patch.object(google_calendar, "service", return_value=service):
                with self.assertRaises(ValueError):
                    google_calendar.create_event({**data, **change}, request_id="same-key")

    def test_manual_replay_accepts_equivalent_google_time_serialization(self):
        data = {"title": "Test", "start": "2026-10-24T08:00:00Z",
                "end": "2026-10-24T09:00:00Z"}
        existing = google_calendar._google_body(data)
        existing.update(id='synthetic', start={'dateTime': '2026-10-24T10:00:00+02:00'},
                        end={'dateTime': '2026-10-24T11:00:00+02:00'}, reminders={'useDefault': False})
        existing.pop('description')
        service = MagicMock()
        service.events.return_value.insert.return_value.execute.side_effect = TimeoutError()
        service.events.return_value.get.return_value.execute.return_value = existing
        with patch.object(google_calendar, 'service', return_value=service):
            self.assertEqual(google_calendar.create_event(data, request_id='same')['id'], 'synthetic')


if __name__ == "__main__":
    unittest.main()
