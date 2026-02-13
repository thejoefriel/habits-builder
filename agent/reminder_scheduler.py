"""Reminder Scheduler — Background process that triggers reminder calls.

Runs in a loop, checking every 5 minutes for sessions that need reminders.
Calls users 15 minutes before their scheduled session.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

from models.schemas import SessionStatus
from tools.state import load_state, save_state as persist_state
from tools.sip import is_sip_configured, initiate_reminder_call, has_active_session
from tools import calendar as gcal

load_dotenv(".env.local")


# ------------------------------------------------------------------
# Logging setup
# ------------------------------------------------------------------

LOG_DIR = Path(__file__).parent / "data" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

_log_file = LOG_DIR / f"scheduler_{datetime.now().strftime('%Y-%m-%d')}.log"

_file_handler = logging.FileHandler(_log_file, encoding="utf-8")
_file_handler.setLevel(logging.DEBUG)
_file_handler.setFormatter(logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
))

_console_handler = logging.StreamHandler()
_console_handler.setLevel(logging.INFO)
_console_handler.setFormatter(logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
))

logging.basicConfig(level=logging.DEBUG, handlers=[_file_handler, _console_handler])

for _noisy in ("httpcore", "httpx", "urllib3", "google"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

logger = logging.getLogger("scheduler")

# Configuration
CHECK_INTERVAL_SECONDS = 300  # 5 minutes
REMINDER_WINDOW_MINUTES = 15  # Call 15 minutes before session


def get_sessions_needing_reminder() -> list[dict]:
    """Find sessions starting within the reminder window that haven't been reminded.

    Returns:
        List of session dicts ready for reminder calls.
    """
    state = load_state()
    now = datetime.now()
    reminder_cutoff = now + timedelta(minutes=REMINDER_WINDOW_MINUTES)

    sessions_to_remind = []

    for session in state.planned_sessions:
        # Skip if not upcoming or already reminded
        if session.status != SessionStatus.UPCOMING:
            continue
        if session.reminder_sent:
            continue

        # Parse session datetime
        try:
            session_dt = datetime.fromisoformat(
                f"{session.scheduled_date}T{session.scheduled_start}:00"
            )
        except ValueError:
            logger.warning("Invalid datetime for session %s", session.session_id)
            continue

        # Check if session is within reminder window (and not in the past)
        if now <= session_dt <= reminder_cutoff:
            sessions_to_remind.append({
                "session_id": session.session_id,
                "gcal_event_id": session.gcal_event_id,
                "title": session.title,
                "session_type": session.session_type.value,
                "duration_minutes": session.duration_minutes,
                "scheduled_date": session.scheduled_date,
                "scheduled_start": session.scheduled_start,
            })

    return sessions_to_remind


def verify_calendar_event_exists(session: dict, calendar_id: str) -> bool:
    """Verify the calendar event still exists (user hasn't deleted it)."""
    if not session.get("gcal_event_id"):
        return True  # No event ID, assume it exists

    return gcal.event_exists(calendar_id, session["gcal_event_id"])


async def process_reminders() -> None:
    """Main reminder processing loop iteration."""
    state = load_state()

    # Check prerequisites
    if not state.user.phone_number:
        logger.debug("No phone number configured, skipping reminders")
        return

    if not is_sip_configured():
        logger.debug("SIP not configured, skipping reminders")
        return

    if not state.user.write_calendar_id:
        logger.debug("No calendar configured, skipping reminders")
        return

    # Check if user is in an active session
    if await has_active_session(state.user.user_id):
        logger.info("User in active session, skipping reminder calls")
        return

    # Find sessions needing reminders
    sessions_to_remind = get_sessions_needing_reminder()

    if not sessions_to_remind:
        logger.debug("No sessions need reminders")
        return

    logger.info("Found %d session(s) needing reminders", len(sessions_to_remind))

    # Filter out sessions whose calendar events were deleted
    valid_sessions = []
    for session in sessions_to_remind:
        if verify_calendar_event_exists(session, state.user.write_calendar_id):
            valid_sessions.append(session)
        else:
            logger.info(
                "Session %s calendar event deleted, marking as deleted_by_user",
                session["session_id"]
            )
            # Mark the session as deleted
            for s in state.planned_sessions:
                if s.session_id == session["session_id"]:
                    s.status = SessionStatus.DELETED_BY_USER
                    s.reminder_sent = True  # Don't try to remind again
                    break
            persist_state(state)

    if not valid_sessions:
        logger.debug("No valid sessions after calendar check")
        return

    # Initiate the reminder call
    room_name = await initiate_reminder_call(
        phone_number=state.user.phone_number,
        sessions=valid_sessions,
        user_id=state.user.user_id,
        user_name=state.user.name or "there",
        timezone=state.user.timezone,
    )

    if room_name:
        # Mark sessions as reminded
        state = load_state()  # Reload in case it changed
        for session in valid_sessions:
            for s in state.planned_sessions:
                if s.session_id == session["session_id"]:
                    s.reminder_sent = True
                    break
        persist_state(state)
        logger.info("Reminder call initiated in room: %s", room_name)
    else:
        logger.error("Failed to initiate reminder call")


async def run_scheduler() -> None:
    """Run the scheduler loop indefinitely."""
    logger.info("Reminder scheduler starting...")
    logger.info("Check interval: %d seconds", CHECK_INTERVAL_SECONDS)
    logger.info("Reminder window: %d minutes before session", REMINDER_WINDOW_MINUTES)

    if not is_sip_configured():
        logger.warning(
            "SIP not configured. Set LIVEKIT_SIP_TRUNK_ID, LIVEKIT_API_KEY, "
            "LIVEKIT_API_SECRET, and LIVEKIT_URL to enable calls."
        )

    while True:
        try:
            await process_reminders()
        except Exception as e:
            logger.error("Error in reminder processing: %s", e, exc_info=True)

        await asyncio.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    asyncio.run(run_scheduler())
