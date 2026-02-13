"""Reminder Agent — Lightweight agent for outbound reminder phone calls.

This agent handles brief reminder conversations before scheduled sessions.
It has a limited set of tools focused on confirming, rescheduling, or skipping sessions.

Not a standalone process — the main agent.py entrypoint dispatches this
when a room name starts with "reminder_".
"""

from __future__ import annotations

import functools
import logging
from datetime import datetime, timedelta
from typing import Optional

from livekit.agents import Agent, function_tool

from models.schemas import (
    ReminderOutcome,
    SessionStatus,
)
from prompts.reminder_prompt import build_reminder_prompt
from tools.state import load_state, save_state as persist_state
from tools import calendar as gcal
from tools.availability import get_availability, check_slot_available

logger = logging.getLogger("reminder")


def _log_tool(fn):
    """Decorator that logs tool calls with arguments and results."""
    @functools.wraps(fn)
    async def wrapper(self, *args, **kwargs):
        tool_name = fn.__name__
        arg_parts = []
        for i, v in enumerate(args):
            val_str = str(v)[:80]
            arg_parts.append(f"arg{i}={val_str}")
        for k, v in kwargs.items():
            arg_parts.append(f"{k}={str(v)[:80]}")
        args_str = ", ".join(arg_parts) if arg_parts else "(no args)"
        logger.info("TOOL CALL: %s(%s)", tool_name, args_str)

        try:
            result = await fn(self, *args, **kwargs)
            logger.info("TOOL RESULT: %s -> %s", tool_name, str(result)[:200])
            return result
        except Exception as e:
            logger.error("TOOL ERROR: %s -> %s: %s", tool_name, type(e).__name__, e)
            raise
    return wrapper


class ReminderAgent(Agent):
    """Lightweight agent for reminder phone calls.

    Only has tools for:
    - Checking availability (for rescheduling)
    - Moving calendar events
    - Updating session status (for skipping)
    - Marking reminder complete
    """

    def __init__(self, sessions: list[dict], user_name: str, timezone: str) -> None:
        self._state = load_state()
        self._sessions = sessions
        self._user_name = user_name
        self._timezone = timezone

        logger.info(
            "Reminder agent initialised — user: %s, sessions: %d",
            user_name,
            len(sessions),
        )

        instructions = build_reminder_prompt(user_name, sessions, timezone)
        super().__init__(instructions=instructions)

    # ------------------------------------------------------------------
    # Availability tool (for rescheduling)
    # ------------------------------------------------------------------

    @function_tool
    @_log_tool
    async def get_all_availability(
        self,
        start_date: str,
        end_date: str,
    ) -> str:
        """Get available time slots across a date range for rescheduling.

        Args:
            start_date: Start date in YYYY-MM-DD format.
            end_date: End date in YYYY-MM-DD format.
        """
        self._state = load_state()
        cal_ids = self._state.user.read_calendar_ids
        if not cal_ids:
            return "No calendars configured."

        try:
            availability = get_availability(
                read_calendar_ids=cal_ids,
                start_date=start_date,
                end_date=end_date,
                schedule_context=self._state.schedule_context,
                timezone=self._timezone,
            )

            lines = []
            for date_str, slots in sorted(availability.items()):
                if slots:
                    slot_strs = [f"{s['start']}-{s['end']}" for s in slots]
                    lines.append(f"- {date_str}: {', '.join(slot_strs)}")

            return "Available slots:\n" + "\n".join(lines) if lines else "No availability found."
        except Exception as e:
            return f"Error: {e}"

    # ------------------------------------------------------------------
    # Calendar management tools
    # ------------------------------------------------------------------

    @function_tool
    @_log_tool
    async def move_calendar_event(
        self,
        session_id: str,
        new_start_datetime: str,
    ) -> str:
        """Move a session to a new time.

        Args:
            session_id: The session_id to move.
            new_start_datetime: New start time in ISO format (YYYY-MM-DDTHH:MM:SS).
        """
        self._state = load_state()
        cal_id = self._state.user.write_calendar_id
        if not cal_id:
            return "No calendar configured."

        session = next(
            (s for s in self._state.planned_sessions if s.session_id == session_id), None
        )
        if not session:
            return f"Session {session_id} not found."

        new_start = datetime.fromisoformat(new_start_datetime)
        new_end = new_start + timedelta(minutes=session.duration_minutes)

        # Check availability
        date_str = new_start.strftime("%Y-%m-%d")
        start_time = new_start.strftime("%H:%M")
        is_free = check_slot_available(
            self._state.user.read_calendar_ids,
            date_str,
            start_time,
            session.duration_minutes,
            self._state.schedule_context,
            self._timezone,
        )
        if not is_free:
            return "That time slot isn't available. Try another time."

        try:
            gcal.update_event(
                calendar_id=cal_id,
                event_id=session.gcal_event_id,
                updates={
                    "start_datetime": new_start_datetime,
                    "end_datetime": new_end.isoformat(),
                },
                timezone=self._timezone,
            )

            session.scheduled_date = date_str
            session.scheduled_start = start_time
            persist_state(self._state)

            return f"Session moved to {date_str} at {start_time}."
        except Exception as e:
            return f"Error moving session: {e}"

    @function_tool
    @_log_tool
    async def update_session_status(
        self,
        session_id: str,
        status: str,
    ) -> str:
        """Update session status (use for skipping).

        Args:
            session_id: The session_id to update.
            status: New status: skipped, completed, etc.
        """
        self._state = load_state()

        session = next(
            (s for s in self._state.planned_sessions if s.session_id == session_id), None
        )
        if not session:
            return f"Session {session_id} not found."

        session.status = SessionStatus(status)
        persist_state(self._state)

        return f"Session marked as {status}."

    # ------------------------------------------------------------------
    # Reminder completion tool
    # ------------------------------------------------------------------

    @function_tool
    @_log_tool
    async def mark_reminder_complete(
        self,
        session_id: str,
        outcome: str,
    ) -> str:
        """Mark the reminder call as complete and record the outcome.

        Call this before ending the conversation to record what happened.

        Args:
            session_id: The session_id that was reminded about.
            outcome: The outcome: confirmed, rescheduled, skipped, no_answer, voicemail, error.
        """
        self._state = load_state()

        session = next(
            (s for s in self._state.planned_sessions if s.session_id == session_id), None
        )
        if not session:
            return f"Session {session_id} not found."

        session.reminder_outcome = ReminderOutcome(outcome)
        persist_state(self._state)

        logger.info("Reminder complete for %s: %s", session_id, outcome)
        return f"Reminder outcome recorded: {outcome}."
