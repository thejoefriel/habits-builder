"""Google Calendar API wrapper for Habits agent."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from typing import Any, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

HABITS_TAG = "[habits-agent]"
HABITS_EMOJI_PREFIX = "🏋️ Habits: "

# Scopes required for reading/writing calendar events
SCOPES = ["https://www.googleapis.com/auth/calendar"]


def _get_credentials() -> Credentials:
    """Build OAuth2 credentials from environment variables."""
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
    refresh_token = os.environ.get("GOOGLE_REFRESH_TOKEN")

    if not all([client_id, client_secret, refresh_token]):
        raise ValueError(
            "Missing Google Calendar credentials. "
            "Set GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, and GOOGLE_REFRESH_TOKEN in .env"
        )

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=SCOPES,
    )
    creds.refresh(Request())
    return creds


def _get_service():
    """Build the Google Calendar API service."""
    creds = _get_credentials()
    return build("calendar", "v3", credentials=creds)


def list_calendars() -> list[dict[str, str]]:
    """List all calendars accessible to the user.

    Returns a list of dicts with 'id' and 'summary' keys.
    """
    service = _get_service()
    result = service.calendarList().list().execute()
    calendars = []
    for item in result.get("items", []):
        calendars.append({
            "id": item["id"],
            "summary": item.get("summary", item["id"]),
            "primary": item.get("primary", False),
        })
    return calendars


def get_events(
    calendar_id: str,
    start_date: str,
    end_date: str,
    timezone: str = "Europe/London",
) -> list[dict[str, Any]]:
    """Get all events from a calendar within a date range.

    Args:
        calendar_id: The calendar ID to query.
        start_date: Start date in YYYY-MM-DD format.
        end_date: End date in YYYY-MM-DD format.
        timezone: Timezone for the query.

    Returns:
        List of event dicts with id, summary, start, end, description.
    """
    service = _get_service()

    # Google Calendar API requires RFC3339 with timezone offset
    time_min = f"{start_date}T00:00:00Z"
    time_max = f"{end_date}T23:59:59Z"

    events_result = (
        service.events()
        .list(
            calendarId=calendar_id,
            timeMin=time_min,
            timeMax=time_max,
            timeZone=timezone,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )

    events = []
    for event in events_result.get("items", []):
        start = event.get("start", {})
        end = event.get("end", {})
        events.append({
            "id": event["id"],
            "summary": event.get("summary", "(no title)"),
            "start": start.get("dateTime", start.get("date", "")),
            "end": end.get("dateTime", end.get("date", "")),
            "description": event.get("description", ""),
            "is_all_day": "date" in start and "dateTime" not in start,
        })

    return events


def get_all_events(
    calendar_ids: list[str],
    start_date: str,
    end_date: str,
    timezone: str = "Europe/London",
) -> list[dict[str, Any]]:
    """Get events from multiple calendars, merged and sorted by start time."""
    all_events = []
    for cal_id in calendar_ids:
        try:
            events = get_events(cal_id, start_date, end_date, timezone)
            for event in events:
                event["calendar_id"] = cal_id
            all_events.extend(events)
        except Exception as e:
            logger.error("Failed to read calendar %s: %s", cal_id, e)

    all_events.sort(key=lambda e: e["start"])
    return all_events


def create_event(
    calendar_id: str,
    title: str,
    description: str,
    start_datetime: str,
    end_datetime: str,
    timezone: str = "Europe/London",
) -> str:
    """Create a calendar event and return the event ID.

    Args:
        calendar_id: Calendar to create the event in.
        title: Event title (will be prefixed with Habits emoji).
        description: Event description (Habits tag will be appended).
        start_datetime: ISO format datetime string (YYYY-MM-DDTHH:MM:SS).
        end_datetime: ISO format datetime string (YYYY-MM-DDTHH:MM:SS).
        timezone: Timezone for the event.

    Returns:
        The created event's ID.
    """
    service = _get_service()

    # Ensure Habits prefix and tag
    summary = title if title.startswith(HABITS_EMOJI_PREFIX) else f"{HABITS_EMOJI_PREFIX}{title}"
    if HABITS_TAG not in description:
        description = f"{description}\n\n{HABITS_TAG}"

    event_body = {
        "summary": summary,
        "description": description,
        "start": {
            "dateTime": start_datetime,
            "timeZone": timezone,
        },
        "end": {
            "dateTime": end_datetime,
            "timeZone": timezone,
        },
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "popup", "minutes": 15},
            ],
        },
    }

    event = service.events().insert(calendarId=calendar_id, body=event_body).execute()
    logger.info("Created event: %s (%s)", event["id"], summary)
    return event["id"]


def update_event(
    calendar_id: str,
    event_id: str,
    updates: dict[str, Any],
    timezone: str = "Europe/London",
) -> None:
    """Update an existing calendar event.

    Args:
        calendar_id: Calendar containing the event.
        event_id: The event ID to update.
        updates: Dict with optional keys: title, description, start_datetime, end_datetime.
        timezone: Timezone for datetime fields.
    """
    service = _get_service()

    # Fetch the existing event
    event = service.events().get(calendarId=calendar_id, eventId=event_id).execute()

    if "title" in updates:
        title = updates["title"]
        event["summary"] = (
            title if title.startswith(HABITS_EMOJI_PREFIX) else f"{HABITS_EMOJI_PREFIX}{title}"
        )

    if "description" in updates:
        desc = updates["description"]
        if HABITS_TAG not in desc:
            desc = f"{desc}\n\n{HABITS_TAG}"
        event["description"] = desc

    if "start_datetime" in updates:
        event["start"] = {
            "dateTime": updates["start_datetime"],
            "timeZone": timezone,
        }

    if "end_datetime" in updates:
        event["end"] = {
            "dateTime": updates["end_datetime"],
            "timeZone": timezone,
        }

    service.events().update(calendarId=calendar_id, eventId=event_id, body=event).execute()
    logger.info("Updated event: %s", event_id)


def delete_event(calendar_id: str, event_id: str) -> None:
    """Delete a calendar event.

    Args:
        calendar_id: Calendar containing the event.
        event_id: The event ID to delete.
    """
    service = _get_service()
    service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
    logger.info("Deleted event: %s", event_id)


def event_exists(calendar_id: str, event_id: str) -> bool:
    """Check if a specific event still exists in the calendar."""
    service = _get_service()
    try:
        event = service.events().get(calendarId=calendar_id, eventId=event_id).execute()
        return event.get("status") != "cancelled"
    except Exception:
        return False


def get_habits_events_since(
    calendar_id: str,
    since_date: str,
    timezone: str = "Europe/London",
) -> list[dict[str, Any]]:
    """Get all Habits-tagged events since a given date.

    Args:
        calendar_id: The calendar to search (typically the write calendar).
        since_date: Date string in YYYY-MM-DD format.
        timezone: Timezone for the query.

    Returns:
        List of Habits events with id, summary, start, end.
    """
    # Search up to 8 weeks out to cover full plan window
    end_date = (
        datetime.fromisoformat(since_date) + timedelta(weeks=8)
    ).strftime("%Y-%m-%d")

    events = get_events(calendar_id, since_date, end_date, timezone)

    # Filter to only Habits-tagged events
    habits_events = [
        e for e in events
        if HABITS_TAG in e.get("description", "") or HABITS_EMOJI_PREFIX in e.get("summary", "")
    ]

    return habits_events
