import unittest
from unittest.mock import patch
from datetime import datetime

from core import google_calendar


class GoogleCalendarProviderTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
