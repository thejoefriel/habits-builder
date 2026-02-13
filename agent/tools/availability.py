"""Availability calculation engine.

Combines calendar events, routine blocks, and sleep window to determine
available time slots for scheduling fitness sessions.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, time as dt_time
from typing import Optional

from models.schemas import ScheduleContext, TimeWindow, RoutineBlock
from tools.calendar import get_all_events

logger = logging.getLogger(__name__)

# Day name mapping for routine blocks
DAY_NAMES = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def _parse_time(t: str) -> dt_time:
    """Parse HH:MM string to time object."""
    parts = t.strip().split(":")
    return dt_time(int(parts[0]), int(parts[1]))


def _time_to_minutes(t: dt_time) -> int:
    """Convert time to minutes since midnight."""
    return t.hour * 60 + t.minute


def _minutes_to_time(m: int) -> dt_time:
    """Convert minutes since midnight to time object."""
    return dt_time(m // 60, m % 60)


def _get_day_name(date: datetime) -> str:
    """Get lowercase day name from a datetime."""
    return DAY_NAMES[date.weekday()]


def get_busy_blocks_for_day(
    date: datetime,
    calendar_events: list[dict],
    schedule_context: Optional[ScheduleContext],
) -> list[tuple[int, int]]:
    """Get all busy blocks for a specific day as (start_minutes, end_minutes) tuples.

    Merges calendar events, routine blocks, and sleep window into a sorted
    list of busy periods.

    Args:
        date: The date to check.
        calendar_events: All calendar events for the date range (pre-fetched).
        schedule_context: User's routine/sleep schedule, if available.

    Returns:
        Sorted list of (start_min, end_min) tuples representing busy periods.
    """
    date_str = date.strftime("%Y-%m-%d")
    day_name = _get_day_name(date)
    busy = []

    # 1. Calendar events for this day
    for event in calendar_events:
        if event.get("is_all_day"):
            # Skip all-day events — these are typically reminders, holidays,
            # or background events, not actual time blocks that prevent exercise.
            continue

        event_start = event.get("start", "")
        event_end = event.get("end", "")

        if not event_start or not event_end:
            continue

        # Check if event falls on this date
        try:
            start_dt = datetime.fromisoformat(event_start)
            end_dt = datetime.fromisoformat(event_end)
        except ValueError:
            continue

        if start_dt.strftime("%Y-%m-%d") != date_str and end_dt.strftime("%Y-%m-%d") != date_str:
            continue

        # Clamp to this day's boundaries
        if start_dt.strftime("%Y-%m-%d") == date_str:
            start_min = _time_to_minutes(start_dt.time())
        else:
            start_min = 0

        if end_dt.strftime("%Y-%m-%d") == date_str:
            end_min = _time_to_minutes(end_dt.time())
        else:
            end_min = 1440

        busy.append((start_min, end_min))

    # 2. Routine blocks for this day of week
    if schedule_context:
        for block in schedule_context.routine_blocks:
            if day_name in block.days:
                start_min = _time_to_minutes(_parse_time(block.start))
                end_min = _time_to_minutes(_parse_time(block.end))
                busy.append((start_min, end_min))

        # 3. Sleep window
        if schedule_context.sleep_window:
            sleep = schedule_context.sleep_window
            sleep_start = _time_to_minutes(_parse_time(sleep.start))
            sleep_end = _time_to_minutes(_parse_time(sleep.end))

            if sleep_start > sleep_end:
                # Overnight sleep: e.g. 23:00 -> 07:30
                # Block from sleep_start to midnight, and midnight to sleep_end
                busy.append((sleep_start, 1440))
                busy.append((0, sleep_end))
            else:
                busy.append((sleep_start, sleep_end))

    # Merge overlapping blocks
    return _merge_blocks(busy)


def _merge_blocks(blocks: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Merge overlapping time blocks into non-overlapping sorted list."""
    if not blocks:
        return []

    sorted_blocks = sorted(blocks, key=lambda b: b[0])
    merged = [sorted_blocks[0]]

    for start, end in sorted_blocks[1:]:
        prev_start, prev_end = merged[-1]
        if start <= prev_end:
            # Overlapping — extend
            merged[-1] = (prev_start, max(prev_end, end))
        else:
            merged.append((start, end))

    return merged


def get_free_slots_for_day(
    date: datetime,
    calendar_events: list[dict],
    schedule_context: Optional[ScheduleContext],
    min_slot_minutes: int = 30,
) -> list[tuple[dt_time, dt_time]]:
    """Get available time slots for a specific day.

    Args:
        date: The date to check.
        calendar_events: All calendar events for the date range (pre-fetched).
        schedule_context: User's routine/sleep schedule.
        min_slot_minutes: Minimum slot duration to return.

    Returns:
        List of (start_time, end_time) tuples representing free periods.
    """
    busy = get_busy_blocks_for_day(date, calendar_events, schedule_context)

    # Find gaps between busy blocks
    free = []
    prev_end = 0

    for start, end in busy:
        if start - prev_end >= min_slot_minutes:
            free.append((_minutes_to_time(prev_end), _minutes_to_time(start)))
        prev_end = max(prev_end, end)

    # Check gap after last block until end of day
    if 1440 - prev_end >= min_slot_minutes:
        free.append((_minutes_to_time(prev_end), dt_time(23, 59)))

    return free


def get_availability(
    read_calendar_ids: list[str],
    start_date: str,
    end_date: str,
    schedule_context: Optional[ScheduleContext],
    timezone: str = "Europe/London",
    min_slot_minutes: int = 30,
) -> dict[str, list[dict[str, str]]]:
    """Get availability across a date range, checking all calendars.

    Args:
        read_calendar_ids: Calendar IDs to check for conflicts.
        start_date: Start date (YYYY-MM-DD).
        end_date: End date (YYYY-MM-DD).
        schedule_context: User's routine/sleep schedule.
        timezone: Timezone for calendar queries.
        min_slot_minutes: Minimum slot duration to include.

    Returns:
        Dict mapping date strings to lists of {start, end} time slot dicts.
    """
    # Fetch all calendar events for the range
    calendar_events = get_all_events(read_calendar_ids, start_date, end_date, timezone)

    availability = {}
    current = datetime.fromisoformat(start_date)
    end = datetime.fromisoformat(end_date)

    while current <= end:
        date_str = current.strftime("%Y-%m-%d")
        free_slots = get_free_slots_for_day(
            current, calendar_events, schedule_context, min_slot_minutes
        )
        availability[date_str] = [
            {"start": slot[0].strftime("%H:%M"), "end": slot[1].strftime("%H:%M")}
            for slot in free_slots
        ]
        current += timedelta(days=1)

    return availability


def check_slot_available(
    read_calendar_ids: list[str],
    date: str,
    start_time: str,
    duration_minutes: int,
    schedule_context: Optional[ScheduleContext],
    timezone: str = "Europe/London",
) -> bool:
    """Check if a specific time slot is available (no conflicts).

    Args:
        read_calendar_ids: Calendar IDs to check.
        date: Date string (YYYY-MM-DD).
        start_time: Start time (HH:MM).
        duration_minutes: Duration of the proposed session.
        schedule_context: User's routine/sleep schedule.
        timezone: Timezone for calendar queries.

    Returns:
        True if the slot is completely free.
    """
    calendar_events = get_all_events(read_calendar_ids, date, date, timezone)
    date_dt = datetime.fromisoformat(date)

    busy = get_busy_blocks_for_day(date_dt, calendar_events, schedule_context)

    slot_start = _time_to_minutes(_parse_time(start_time))
    slot_end = slot_start + duration_minutes

    for busy_start, busy_end in busy:
        # Check for overlap
        if slot_start < busy_end and slot_end > busy_start:
            return False

    return True
