"""Google Calendar provider used as the authoritative user calendar.

The OAuth token is intentionally separate from Gmail so Calendar can be
reauthorized without touching mail access. Client credentials may be shared.
"""
from __future__ import annotations

import os
import hashlib
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


def connection_fingerprint() -> str:
    """Pin an approval to one OAuth account without persisting its token."""
    credentials = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if not credentials.refresh_token:
        raise GoogleCalendarNotConnected("Token Google senza refresh token: ricollega l'account.")
    identity = (str(credentials.client_id or "") + ":" + credentials.refresh_token).encode("utf-8")
    return hashlib.sha256(identity).hexdigest()


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
            "credentialsAvailable": CREDENTIALS_PATH.is_file(),
            "reachable": True,
            "nextSyncTokenAvailable": bool(result.get("nextSyncToken")),
        }
    except Exception:
        # Provider exceptions may contain OAuth secrets, URLs or local paths.
        # Keep the public status independent of their message and class.
        return {
            "connected": True,
            "provider": "google",
            "credentialsAvailable": CREDENTIALS_PATH.is_file(),
            "reachable": False,
            "error": "Google Calendar non disponibile. Verifica il collegamento e riprova.",
        }


def _event_times(event: dict) -> tuple[str, str, bool]:
    start = event.get("start") or {}
    end = event.get("end") or {}
    if start.get("date"):
        return (datetime.fromisoformat(start["date"]).replace(tzinfo=ROME).isoformat(),
                datetime.fromisoformat(end["date"]).replace(tzinfo=ROME).isoformat(), True)
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
    # Google sequence may stay unchanged after an ordinary edit; its ETag is the revision.
    etag = event.get("etag")
    version = (int(hashlib.sha256(etag.encode("utf-8")).hexdigest()[:12], 16) + 1
               if isinstance(etag, str) and etag else max(1, int(event.get("sequence") or 0) + 1))
    return {
        "id": event["id"],
        "title": event.get("summary") or "(senza titolo)",
        "start": start,
        "end": end,
        "all_day": all_day,
        "notes": event.get("description") or "",
        "reminder_minutes": _reminder_minutes(event),
        "version": version,
        "etag": etag,
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
    private = {"coraManaged": "true"}
    local_event_id = str(data.get("local_event_id") or "").strip()
    if local_event_id:
        private["coraLocalEventId"] = local_event_id
    return {
        "summary": str(data["title"]).strip(),
        "description": data.get("notes") or "",
        "start": start,
        "end": end,
        "reminders": reminders,
        "extendedProperties": {"private": private},
    }


def list_events(start: datetime, end: datetime) -> list[dict]:
    if (start.tzinfo is None or end.tzinfo is None or end <= start
            or end - start > timedelta(days=370)):
        raise ValueError("Intervallo non valido: indica il fuso e al massimo 370 giorni.")
    calendar_service = service()
    items: list[dict] = []
    page_token = None
    while True:
        params = dict(calendarId="primary",
                      timeMin=start.astimezone(timezone.utc).isoformat(),
                      timeMax=end.astimezone(timezone.utc).isoformat(),
                      singleEvents=True, orderBy="startTime", maxResults=2500)
        if page_token:
            params["pageToken"] = page_token
        result = calendar_service.events().list(**params).execute()
        items.extend(normalize(event) for event in result.get("items", [])
                     if event.get("status") != "cancelled")
        page_token = result.get("nextPageToken")
        if not page_token:
            return items


def get_event(event_id: str) -> dict:
    return normalize(service().events().get(calendarId="primary", eventId=event_id).execute())


def create_event(data: dict) -> dict:
    event = service().events().insert(
        calendarId="primary",
        body=_google_body(data),
        sendUpdates="none",
    ).execute()
    return normalize(event)


def _managed_local_event_ids(calendar_service=None) -> set[str]:
    calendar_service = calendar_service or service()
    identifiers: set[str] = set()
    page_token = None
    while True:
        params = {
            "calendarId": "primary",
            "privateExtendedProperty": "coraManaged=true",
            "maxResults": 2500,
            "singleEvents": True,
            "showDeleted": False,
        }
        if page_token:
            params["pageToken"] = page_token
        result = calendar_service.events().list(**params).execute()
        for event in result.get("items", []):
            private = ((event.get("extendedProperties") or {}).get("private") or {})
            local_id = private.get("coraLocalEventId")
            if local_id:
                identifiers.add(str(local_id))
        page_token = result.get("nextPageToken")
        if not page_token:
            return identifiers


def publish_local_events(events: list[dict]) -> dict:
    """Idempotently export local future events to the user's primary calendar."""
    calendar_service = service()
    existing = _managed_local_event_ids(calendar_service)
    sent: list[dict] = []
    skipped: list[str] = []
    failed: list[dict] = []
    for local in events:
        local_id = str(local["id"])
        if local_id in existing:
            skipped.append(local_id)
            continue
        payload = {**local, "local_event_id": local_id}
        try:
            created = calendar_service.events().insert(
                calendarId="primary",
                body=_google_body(payload),
                sendUpdates="none",
            ).execute()
            sent.append({
                "localEventId": local_id,
                "googleEventId": created.get("id"),
                "title": local.get("title") or "",
            })
            existing.add(local_id)
        except Exception as error:
            failed.append({
                "localEventId": local_id,
                "title": local.get("title") or "",
                "error": type(error).__name__,
            })
    return {
        "sent": len(sent),
        "skipped": len(skipped),
        "failed": len(failed),
        "sentEvents": sent,
        "failedEvents": failed[:20],
    }


def _conditional_event_request(event_id: str, expected_version: int, *, data: dict | None = None) -> dict:
    """Reject stale revisions, then atomically enforce ETag using Google's If-Match."""
    from core.calendar import CalendarConflict
    previous = get_event(event_id)
    if previous["version"] != expected_version:
        raise CalendarConflict("L'evento Google è cambiato: rileggilo prima di procedere.")
    etag = previous.get("etag")
    if not etag:
        raise CalendarConflict("Google non ha fornito una revisione verificabile: modifica rifiutata.")
    calendar_service = service()
    if data is None:
        request = calendar_service.events().delete(
            calendarId="primary", eventId=event_id, sendUpdates="none",
        )
    else:
        request = calendar_service.events().patch(
            calendarId="primary", eventId=event_id, body=_google_body(data), sendUpdates="none",
        )
    request.headers["If-Match"] = etag
    try:
        result = request.execute()
    except HttpError as error:
        if error.resp.status == 412:
            raise CalendarConflict("L'evento è cambiato su Google Calendar: aggiorna prima di approvare.") from error
        raise
    if data is not None:
        return normalize(result)
    return {**previous, "deleted_at": datetime.now(timezone.utc).isoformat()}


def update_event(event_id: str, data: dict, *, expected_version: int) -> dict:
    return _conditional_event_request(event_id, expected_version, data=data)


def delete_event(event_id: str, *, expected_version: int) -> dict:
    return _conditional_event_request(event_id, expected_version)


def verify_access() -> bool:
    service().events().list(
        calendarId="primary",
        timeMin=datetime.now(timezone.utc).isoformat(),
        maxResults=1,
        singleEvents=True,
    ).execute()
    return True
