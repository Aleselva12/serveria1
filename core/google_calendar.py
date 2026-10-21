"""Google Calendar provider used as the authoritative user calendar.

The OAuth token is intentionally separate from Gmail so Calendar can be
reauthorized without touching mail access. Client credentials may be shared.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
ROME = ZoneInfo("Europe/Rome")

TOKEN_PATH = Path(os.getenv(
    "CORA_GOOGLE_CALENDAR_TOKEN_PATH",
    "/state/google-calendar/token.json",
)).expanduser()
CREDENTIALS_PATH = Path(os.getenv(
    "CORA_GOOGLE_CALENDAR_CREDENTIALS_PATH",
    os.getenv("CORA_GMAIL_CREDENTIALS_PATH", "/state/gmail/credentials.json"),
)).expanduser()


class GoogleCalendarNotConnected(RuntimeError):
    pass


def token_exists() -> bool:
    return TOKEN_PATH.is_file()


def _credentials() -> Credentials:
    if not TOKEN_PATH.is_file():
        raise GoogleCalendarNotConnected("Google Calendar non collegato.")
    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
        os.chmod(TOKEN_PATH, 0o600)
    if not creds.valid:
        raise GoogleCalendarNotConnected("Token Google Calendar non valido: ricollega l'account.")
    return creds


def service():
    return build("calendar", "v3", credentials=_credentials(), cache_discovery=False)


def status() -> dict:
    if not token_exists():
        return {
            "connected": False,
            "provider": "local",
            "tokenPath": str(TOKEN_PATH),
            "credentialsAvailable": CREDENTIALS_PATH.is_file(),
        }
    try:
        result = service().events().list(
            calendarId="primary",
            timeMin=datetime.now(timezone.utc).isoformat(),
            maxResults=1,
            singleEvents=True,
            orderBy="startTime",
        ).execute()
        return {
            "connected": True,
            "provider": "google",
            "tokenPath": str(TOKEN_PATH),
            "credentialsAvailable": CREDENTIALS_PATH.is_file(),
            "reachable": True,
            "nextSyncTokenAvailable": bool(result.get("nextSyncToken")),
        }
    except Exception as error:
        return {
            "connected": True,
            "provider": "google",
            "tokenPath": str(TOKEN_PATH),
            "credentialsAvailable": CREDENTIALS_PATH.is_file(),
            "reachable": False,
            "error": type(error).__name__ + ": " + str(error),
        }


def _event_times(event: dict) -> tuple[str, str, bool]:
    start = event.get("start") or {}
    end = event.get("end") or {}
    if start.get("date"):
        return start["date"] + "T00:00:00+00:00", end["date"] + "T00:00:00+00:00", True
    return start["dateTime"], end["dateTime"], False


def _reminder_minutes(event: dict) -> int | None:
    reminders = event.get("reminders") or {}
    for reminder in reminders.get("overrides") or []:
        if reminder.get("method") == "popup" and isinstance(reminder.get("minutes"), int):
            return reminder["minutes"]
    return 30 if reminders.get("useDefault") else None


def normalize(event: dict) -> dict:
    start, end, all_day = _event_times(event)
    created = event.get("created") or event.get("updated") or datetime.now(timezone.utc).isoformat()
    updated = event.get("updated") or created
    return {
        "id": event["id"],
        "title": event.get("summary") or "(senza titolo)",
        "start": start,
        "end": end,
        "all_day": all_day,
        "notes": event.get("description") or "",
        "reminder_minutes": _reminder_minutes(event),
        "version": max(1, int(event.get("sequence") or 0) + 1),
        "created_by": "Google Calendar",
        "updated_by": "Google Calendar",
        "created_at": created,
        "updated_at": updated,
        "deleted_at": None,
        "provider": "google",
        "html_link": event.get("htmlLink"),
    }


def _google_body(data: dict) -> dict:
    all_day = bool(data.get("all_day"))
    if all_day:
        start_dt = datetime.fromisoformat(str(data["start"]).replace("Z", "+00:00")).astimezone(ROME)
        end_dt = datetime.fromisoformat(str(data["end"]).replace("Z", "+00:00")).astimezone(ROME)
        start = {"date": start_dt.date().isoformat()}
        end = {"date": end_dt.date().isoformat()}
    else:
        start = {"dateTime": data["start"], "timeZone": "Europe/Rome"}
        end = {"dateTime": data["end"], "timeZone": "Europe/Rome"}
    reminder = data.get("reminder_minutes")
    reminders = (
        {"useDefault": False, "overrides": [{"method": "popup", "minutes": int(reminder)}]}
        if reminder is not None
        else {"useDefault": False, "overrides": []}
    )
    return {
        "summary": str(data["title"]).strip(),
        "description": data.get("notes") or "",
        "start": start,
        "end": end,
        "reminders": reminders,
        "extendedProperties": {
            "private": {"coraManaged": "true"}
        },
    }


def list_events(start: datetime, end: datetime) -> list[dict]:
    result = service().events().list(
        calendarId="primary",
        timeMin=start.astimezone(timezone.utc).isoformat(),
        timeMax=end.astimezone(timezone.utc).isoformat(),
        singleEvents=True,
        orderBy="startTime",
        maxResults=2500,
    ).execute()
    return [normalize(event) for event in result.get("items", []) if event.get("status") != "cancelled"]


def get_event(event_id: str) -> dict:
    return normalize(service().events().get(calendarId="primary", eventId=event_id).execute())


def create_event(data: dict) -> dict:
    event = service().events().insert(
        calendarId="primary",
        body=_google_body(data),
        sendUpdates="none",
    ).execute()
    return normalize(event)


def update_event(event_id: str, data: dict) -> dict:
    event = service().events().patch(
        calendarId="primary",
        eventId=event_id,
        body=_google_body(data),
        sendUpdates="none",
    ).execute()
    return normalize(event)


def delete_event(event_id: str) -> dict:
    previous = get_event(event_id)
    service().events().delete(
        calendarId="primary",
        eventId=event_id,
        sendUpdates="none",
    ).execute()
    return {**previous, "deleted_at": datetime.now(timezone.utc).isoformat()}


def verify_access() -> bool:
    service().events().list(
        calendarId="primary",
        timeMin=datetime.now(timezone.utc).isoformat(),
        maxResults=1,
        singleEvents=True,
    ).execute()
    return True
