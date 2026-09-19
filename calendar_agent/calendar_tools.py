from langchain.tools import tool
from calendar_agent.calendar_utilities import ListGoogleCalendarEvents, CreateGoogleCalendarEvent, DeleteGoogleCalendarEvent, PostponeGoogleCalendarEvent
from calendar_agent.calendar_utilities import api_resource
from typing import TypedDict, cast
from langchain_groq import ChatGroq
from dotenv import load_dotenv
import os

load_dotenv()  # this will load variables from .env into environment

GROQ_API_KEY2 = os.getenv("GROQ_API_KEY2")

llm = ChatGroq(
    model="llama-3.1-8b-instant",
    api_key=GROQ_API_KEY2
)

@tool
def create_event_tool(start_datetime: str, end_datetime: str, summary: str, location: str = "", description: str = "") -> str:
    """
    Create a Google Calendar event.

    Args:
        start_datetime (str): Start datetime (YYYY-MM-DDTHH:MM:SS).
        end_datetime (str): End datetime (YYYY-MM-DDTHH:MM:SS).
        summary (str): Event title.
        location (str, optional): Event location.
        description (str, optional): Event description.

    Returns:
        str: Confirmation message with event link.
    """
    timezone="Asia/Kolkata"
    try:
        tool = CreateGoogleCalendarEvent(api_resource)
        result = tool._run(
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            summary=summary,
            location=location,
            description=description,
            timezone=timezone
        )
        return result
    except Exception as e:
        return f"❌ Error creating event: {e}"

@tool
def list_events_tool(start_datetime: str, end_datetime: str, max_results: int = 10) -> list:
    """
    List Google Calendar events in a date range.

    Args:
        start_datetime (str): Start datetime (YYYY-MM-DDTHH:MM:SS).
        end_datetime (str): End datetime (YYYY-MM-DDTHH:MM:SS).
        max_results (int): Maximum results to return.
        timezone (str): Timezone.

    Returns:
        list: List of event dicts (each includes event ID, summary, times, etc.).
    """
    timezone="Asia/Kolkata"
    try:
        tool = ListGoogleCalendarEvents(api_resource)
        events = tool._run(
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            max_results=max_results,
            timezone=timezone
        )
        return events
    except Exception as e:
        return []

@tool
def postpone_event_tool(
    start_datetime: str,
    end_datetime: str,
    query: str,
    new_start_datetime: str,
    new_end_datetime: str,
) -> str:
    """
    Postpone one or more Google Calendar events based on a natural language user query.
    Uses an LLM to select the correct event(s) if the reference is ambiguous.

    Args:
        start_datetime (str): Start datetime for search window.
        end_datetime (str): End datetime for search window.
        query (str): A descriptive query based on the chat history to identify the event.
        new_start_datetime (str): New start datetime for the event(s).
        new_end_datetime (str): New end datetime for the event(s).

    Returns:
        str: Confirmation message(s) or clarification prompt.
    """
    timezone = "Asia/Kolkata"
    args = {
        "start_datetime": start_datetime,
        "end_datetime": end_datetime
    }

    events = list_events_tool.invoke(args)
    if not events:
        return "No events found in the specified time window."

    # Prepare event options for the LLM
    event_options = [
        f"{idx+1}. {e.get('summary', 'No Title')} at {e.get('start')} (ID: {e.get('id')})"
        for idx, e in enumerate(events)
    ]
    options_text = "\n".join(event_options)

    # Compose LLM prompt
    prompt = (
        f"query: '{query}'\n"
        f"Here are the events found:\n{options_text}\n"
        "Based on the user's query, which event ID(s) best match the intent for postponement? "
        "Just reply with the event ID(s) as a list."
    )

    # Call the LLM to select the best event(s)
    class output(TypedDict):
        event_id: list[str]  # Use the same key as in your delete_event_tool

    llm_response = cast(output, llm.with_structured_output(output).invoke(prompt))
    selected_event_ids = llm_response.get('event_id', [])

    postponed_events = []

    for event_id in selected_event_ids:
        event = next((e for e in events if e.get('id') == event_id), None)
        if not event:
            msg = f"❌ Event ID `{event_id}` not found."
            postponed_events.append(msg)
            continue

        try:
            tool = PostponeGoogleCalendarEvent(api_resource)
            result = tool._run(
                event_id=str(event.get('id')),
                new_start_datetime=new_start_datetime,
                new_end_datetime=new_end_datetime,
                timezone=timezone
            )
            msg = f"✅ Postponed event: **{event.get('summary', 'No Title')}** (`{event_id}`) → {result}"
            postponed_events.append(msg)
        except Exception as e:
            msg = f"❌ Error postponing event `{event_id}`: {e}"
            postponed_events.append(msg)

    return "\n".join(postponed_events)

@tool
def delete_event_tool(
    start_datetime: str,
    end_datetime: str,
    query: str,
) -> str:
    """
    Delete a Google Calendar event based on a natural language user query.
    Uses an LLM to select the correct event if the reference is ambiguous.

    Args:
        start_datetime (str): Start datetime for search window (YYYY-MM-DDTHH:MM:SS).
        end_datetime (str): End datetime for search window (YYYY-MM-DDTHH:MM:SS).
        query (str): A descriptive query based on the chat history to identify the event.

    Returns:
        str: Confirmation message(s) detailing the deleted events or any errors encountered.
    """
    args = {
        "start_datetime": start_datetime,
        "end_datetime": end_datetime
    }
    events = list_events_tool.invoke(args)
    if not events:
        return "No events found in the specified time window."

    # Prepare event options for the LLM
    event_options = [
        f"{idx+1}. {e.get('summary', 'No Title')} at {e.get('start')} (ID: {e.get('id')})"
        for idx, e in enumerate(events)
    ]
    options_text = "\n".join(event_options)

    # Compose LLM prompt
    prompt = (
        f"Target event description: '{query}'\n"
        f"Here are the events found:\n{options_text}\n"
        "Based on the user's query, which event ID(s) best match the intent for deletion? "
        "Just reply with the event ID(s) as a list."
    )

    # Call the LLM to select the best event
    class output(TypedDict):
        event_id: list[str]

    llm_response = cast(output, llm.with_structured_output(output).invoke(prompt))
    selected_event_ids = llm_response.get('event_id', [])

    # Loop through all selected event IDs and delete each
    deleted_events = []

    for event_id in selected_event_ids:  # This is now a list
        # Find the event by exact match of ID
        event = next((e for e in events if e.get('id') == event_id), None)
        if not event:
            msg = f"❌ Event ID `{event_id}` not found."
            deleted_events.append(msg)
            continue

        try:
            tool = DeleteGoogleCalendarEvent(api_resource)
            result = tool._run(
                event_id=str(event.get('id')),
                calendar_id=None  # Defaults to 'primary' or configured calendar
            )
            msg = f"✅ Deleted event: **{event.get('summary', 'No Title')}** (`{event_id}`) → {result}"
            deleted_events.append(msg)
        except Exception as e:
            msg = f"❌ Error deleting event `{event_id}`: {e}"
            deleted_events.append(msg)

    # Return summary of all deletions
    return "\n".join(deleted_events)

calendar_tools = [
    create_event_tool,
    list_events_tool,
    postpone_event_tool,
    delete_event_tool
]

if __name__ == '__main__':
    print("--- 1. Listing Events ---")
    list_res = list_events_tool.invoke({
        "start_datetime": "2026-06-15T00:00:00",
        "end_datetime": "2026-06-15T23:59:59"
    })
    print(list_res)

    print("\n--- 2. Creating 2 Events ---")
    create_res_1 = create_event_tool.invoke({
        "start_datetime": "2026-06-15T10:00:00",
        "end_datetime": "2026-06-15T11:00:00",
        "summary": "JARVIS Alpha Sync",
        "description": "First automated test event",
        "location": "Virtual"
    })
    print(create_res_1)

    create_res_2 = create_event_tool.invoke({
        "start_datetime": "2026-06-15T14:00:00",
        "end_datetime": "2026-06-15T15:00:00",
        "summary": "JARVIS Beta Sync",
        "description": "Second automated test event",
        "location": "Virtual"
    })
    print(create_res_2)

    print("\n--- 3. Postponing an Event ---")
    postpone_res = postpone_event_tool.invoke({
        "start_datetime": "2026-06-15T00:00:00",
        "end_datetime": "2026-06-15T23:59:59",
        "query": "postpone the Alpha Sync to 12 PM",
        "new_start_datetime": "2026-06-15T12:00:00",
        "new_end_datetime": "2026-06-15T13:00:00"
    })
    print(postpone_res)

    print("\n--- 4. Deleting Both Events ---")
    delete_res_1 = delete_event_tool.invoke({
        "start_datetime": "2026-06-15T00:00:00",
        "end_datetime": "2026-06-15T23:59:59",
        "query": "delete the Alpha Sync meeting"
    })
    print(delete_res_1)

    delete_res_2 = delete_event_tool.invoke({
        "start_datetime": "2026-06-15T00:00:00",
        "end_datetime": "2026-06-15T23:59:59",
        "query": "delete the Beta Sync meeting"
    })
    print(delete_res_2)
