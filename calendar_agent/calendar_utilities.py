import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from dateutil import parser, tz
from datetime import datetime

from typing import Any, Dict, List, Optional, Type

# scope of calender access
SCOPES = ["https://www.googleapis.com/auth/calendar"]

# Path to OAuth 2.0 client credentials and token
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_FILE = os.path.join(BASE_DIR, "credentials.json")
TOKEN_FILE = os.path.join(BASE_DIR, "token.json")

credentials = None
# The file token.json stores the user's access and refresh tokens, and is
# created automatically when the authorization flow completes for the first
# time.
if os.path.exists(TOKEN_FILE):
    credentials = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
# If there are no (valid) credentials available, let the user log in.
if not credentials or not credentials.valid:
    if credentials and credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
    else:
        flow = InstalledAppFlow.from_client_secrets_file(
            CREDENTIALS_FILE, SCOPES)
        credentials = flow.run_local_server(port=0)
    # Save the credentials for the next run
    with open(TOKEN_FILE, 'w') as token:
        token.write(credentials.to_json())

# build the api resource manually
api_resource = build('calendar', 'v3', credentials=credentials)


class GoogleCalendarBaseTool:
    """Base class for Google Calendar tools."""
    api_resource = None

    def __init__(self, api_resource):
        self.api_resource = api_resource

    @classmethod
    def from_api_resource(cls, api_resource):
        return cls(api_resource=api_resource)



class ListGoogleCalendarEvents(GoogleCalendarBaseTool):
    def _parse_event(self, event, timezone):
        start = event['start'].get('dateTime', event['start'].get('date'))
        start = parser.parse(start).astimezone(tz.gettz(timezone)).strftime('%Y/%m/%d %H:%M:%S')
        end = event['end'].get('dateTime', event['end'].get('date'))
        end = parser.parse(end).astimezone(tz.gettz(timezone)).strftime('%Y/%m/%d %H:%M:%S')
        event_parsed = dict(start=start, end=end)
        for field in ['summary', 'description', 'location', 'hangoutLink']:
            event_parsed[field] = event.get(field, None)
        # ADD THIS LINE:
        event_parsed['id'] = event.get('id')
        return event_parsed

    def _run(self, start_datetime, end_datetime, max_results=10, timezone="Asia/Kolkata"):
        calendar_id = "primary"
        events = []
        start = datetime.strptime(start_datetime, '%Y-%m-%dT%H:%M:%S')
        start = start.replace(tzinfo=tz.gettz(timezone)).isoformat()
        end = datetime.strptime(end_datetime, '%Y-%m-%dT%H:%M:%S')
        end = end.replace(tzinfo=tz.gettz(timezone)).isoformat()
        events_result = self.api_resource.events().list(
            calendarId=calendar_id,
            timeMin=start,
            timeMax=end,
            maxResults=max_results,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        cal_events = events_result.get('items', [])
        events.extend(cal_events)
        events = sorted(events, key=lambda x: x['start'].get('dateTime', x['start'].get('date')))
        return [self._parse_event(e, timezone) for e in events]



class CreateGoogleCalendarEvent(GoogleCalendarBaseTool):
    def _run(self, start_datetime, end_datetime, summary, location="", description="", timezone="Asia/Kolkata"):
        calendar_id = "primary"
        start = datetime.strptime(start_datetime, '%Y-%m-%dT%H:%M:%S')
        start = start.replace(tzinfo=tz.gettz(timezone)).isoformat()
        end = datetime.strptime(end_datetime, '%Y-%m-%dT%H:%M:%S')
        end = end.replace(tzinfo=tz.gettz(timezone)).isoformat()
        body = {
            'summary': summary,
            'start': {'dateTime': start},
            'end': {'dateTime': end}
        }
        if location:
            body['location'] = location
        if description:
            body['description'] = description
        event = self.api_resource.events().insert(calendarId=calendar_id, body=body).execute()
        return "Event created: " + event.get('htmlLink', 'Failed to create event')



class DeleteGoogleCalendarEvent:
    """
    Delete an event from your Google Calendar.

    - Requires only the event ID.
    - Always uses your primary calendar unless another is specified.
    """

    def __init__(self, api_resource):
        self.api_resource = api_resource
        self.calendar_id = "primary"

    def _run(self, event_id, calendar_id=None):
        calendar_id = calendar_id or self.calendar_id
        try:
            self.api_resource.events().delete(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()
            return f"Event {event_id} deleted from calendar {calendar_id}."
        except Exception as e:
            return f"Failed to delete event: {e}"



class PostponeGoogleCalendarEvent:
    """
    Postpone (reschedule) an event in your Google Calendar.

    - Requires event ID and new start/end datetimes.
    - Always uses your primary calendar unless another is specified.
    """

    def __init__(self, api_resource):
        self.api_resource = api_resource
        self.calendar_id = "primary"

    def _run(self, event_id, new_start_datetime, new_end_datetime, timezone="Asia/Kolkata", calendar_id=None):
        calendar_id = calendar_id or self.calendar_id
        try:
            # Get the existing event
            event = self.api_resource.events().get(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()

            # Format new times
            start = datetime.strptime(new_start_datetime, '%Y-%m-%dT%H:%M:%S').replace(
                tzinfo=tz.gettz(timezone)).isoformat()
            end = datetime.strptime(new_end_datetime, '%Y-%m-%dT%H:%M:%S').replace(
                tzinfo=tz.gettz(timezone)).isoformat()

            event['start']['dateTime'] = start
            event['end']['dateTime'] = end
            event['start']['timeZone'] = timezone
            event['end']['timeZone'] = timezone

            updated_event = self.api_resource.events().update(
                calendarId=calendar_id,
                eventId=event_id,
                body=event
            ).execute()

            return f"Event postponed: {updated_event.get('htmlLink', 'No link')}"
        except Exception as e:
            return f"Failed to postpone event: {e}"


if __name__ == '__main__':
    print("All okay")
