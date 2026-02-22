"""Habits AI Voice Agent — main LiveKit entry point.

Connects to OpenAI Realtime API via LiveKit, with tool functions for
Google Calendar integration, availability checking, plan generation,
and state management.
"""

from __future__ import annotations

import functools
import json
import logging
import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from livekit import agents
from livekit.agents import AgentServer, AgentSession, Agent, room_io, function_tool
from livekit.plugins import openai, noise_cancellation
from livekit.plugins.openai.realtime.realtime_model import InputAudioTranscription

from models.schemas import (
    AppState,
    ConversationPhase,
    ConversationLog,
    Goal,
    GoalStatus,
    FitnessPreferences,
    PlannedSession,
    ScheduleContext,
    SessionStatus,
    SessionType,
    TimeWindow,
    RoutineBlock,
)
from prompts.system_prompt import build_system_prompt
from tools.state import load_state, save_state as persist_state
from tools import calendar as gcal
from tools.availability import get_availability, check_slot_available
from tools.planner import generate_plan
from tools.exercises import get_exercises, format_exercise_list
from reminder_agent import ReminderAgent

load_dotenv(".env.local")


# ------------------------------------------------------------------
# Logging setup — console + rotating file
# ------------------------------------------------------------------

LOG_DIR = Path(__file__).parent / "data" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Session log file — one per day, appended
_log_file = LOG_DIR / f"habits_{datetime.now().strftime('%Y-%m-%d')}.log"

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

# Configure root logger
logging.basicConfig(level=logging.DEBUG, handlers=[_file_handler, _console_handler])

# Quiet down noisy third-party loggers in the file
for _noisy in ("httpcore", "httpx", "urllib3", "google", "openai", "websockets"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

logger = logging.getLogger("habits")
logger.info("Log file: %s", _log_file)


def _log_tool(fn):
    """Decorator that logs tool calls with arguments and results."""
    @functools.wraps(fn)
    async def wrapper(self, *args, **kwargs):
        tool_name = fn.__name__
        # Build a compact representation of the arguments
        arg_parts = []
        for i, v in enumerate(args):
            val_str = str(v)
            if len(val_str) > 120:
                val_str = val_str[:120] + "..."
            arg_parts.append(f"arg{i}={val_str}")
        for k, v in kwargs.items():
            val_str = str(v)
            if len(val_str) > 120:
                val_str = val_str[:120] + "..."
            arg_parts.append(f"{k}={val_str}")
        args_str = ", ".join(arg_parts) if arg_parts else "(no args)"

        logger.info("TOOL CALL: %s(%s)", tool_name, args_str)

        try:
            result = await fn(self, *args, **kwargs)
            # Log result (truncated for readability)
            result_str = str(result)
            if len(result_str) > 300:
                result_str = result_str[:300] + f"... ({len(result_str)} chars total)"
            logger.info("TOOL RESULT: %s -> %s", tool_name, result_str)
            return result
        except Exception as e:
            logger.error("TOOL ERROR: %s -> %s: %s", tool_name, type(e).__name__, e)
            raise
    return wrapper


class HabitsAgent(Agent):
    """Voice agent for fitness goal planning and calendar management."""

    def __init__(self) -> None:
        # Load current state and build the system prompt
        self._state = load_state()
        self._session_start_phase = self._state.user.conversation_phase

        logger.info(
            "Agent initialised — phase: %s, user: %s",
            self._state.user.conversation_phase.value,
            self._state.user.name or "(unnamed)",
        )

        instructions = build_system_prompt(self._state)

        super().__init__(instructions=instructions)

    # ------------------------------------------------------------------
    # State management tools
    # ------------------------------------------------------------------

    @function_tool
    @_log_tool
    async def get_current_state(self) -> str:
        """Get the current application state including user info, goal, schedule, and sessions.
        Use this to check what information has been gathered so far."""
        self._state = load_state()
        return self._state.model_dump_json(indent=2)

    @function_tool
    @_log_tool
    async def update_user_info(
        self,
        name: Optional[str] = None,
        timezone: Optional[str] = None,
        phone_number: Optional[str] = None,
        conversation_phase: Optional[str] = None,
        write_calendar_id: Optional[str] = None,
        read_calendar_ids: Optional[str] = None,
    ) -> str:
        """Update user information and conversation phase.

        Args:
            name: User's name.
            timezone: User's timezone (e.g. 'Europe/London').
            phone_number: User's phone number in E.164 format (e.g. '+44xxxxxxxxxx') for reminder calls.
            conversation_phase: New phase. One of: onboarding_goal, onboarding_schedule, plan_proposed, plan_confirmed, check_in.
            write_calendar_id: Calendar ID to write events to.
            read_calendar_ids: Comma-separated list of calendar IDs to read from.
        """
        self._state = load_state()

        if name is not None:
            self._state.user.name = name
        if timezone is not None:
            self._state.user.timezone = timezone
        if phone_number is not None:
            self._state.user.phone_number = phone_number
        if conversation_phase is not None:
            self._state.user.conversation_phase = ConversationPhase(conversation_phase)
        if write_calendar_id is not None:
            self._state.user.write_calendar_id = write_calendar_id
        if read_calendar_ids is not None:
            self._state.user.read_calendar_ids = [
                c.strip() for c in read_calendar_ids.split(",")
            ]

        self._state.user.last_conversation_date = datetime.now()
        persist_state(self._state)
        return f"User info updated. Phase is now: {self._state.user.conversation_phase.value}"

    @function_tool
    @_log_tool
    async def save_goal(
        self,
        description: str,
        fitness_level: str,
        weekly_time_commitment_minutes: Optional[int] = None,
        likes: Optional[str] = None,
        dislikes: Optional[str] = None,
        constraints: Optional[str] = None,
        equipment: Optional[str] = None,
    ) -> str:
        """Save or update the user's fitness goal.

        Args:
            description: Description of the fitness goal in the user's own words.
            fitness_level: User's current fitness level (beginner, intermediate, advanced).
            weekly_time_commitment_minutes: Total weekly time commitment in minutes.
            likes: Comma-separated list of exercise types the user enjoys.
            dislikes: Comma-separated list of exercise types the user dislikes.
            constraints: Comma-separated list of constraints (injuries, no gym, etc).
            equipment: Comma-separated list of available equipment.
        """
        self._state = load_state()

        goal = Goal(
            goal_id=self._state.goal.goal_id if self._state.goal else f"goal_{uuid.uuid4().hex[:6]}",
            user_id=self._state.user.user_id,
            description=description,
            fitness_level=fitness_level,
            weekly_time_commitment_minutes=weekly_time_commitment_minutes,
            preferences=FitnessPreferences(
                likes=[l.strip() for l in (likes or "").split(",") if l.strip()],
                dislikes=[d.strip() for d in (dislikes or "").split(",") if d.strip()],
                constraints=[c.strip() for c in (constraints or "").split(",") if c.strip()],
                equipment=[e.strip() for e in (equipment or "").split(",") if e.strip()],
            ),
            created_at=datetime.now(),
            status=GoalStatus.ACTIVE,
        )

        self._state.goal = goal
        persist_state(self._state)
        return f"Goal saved: {description} (fitness level: {fitness_level})"

    @function_tool
    @_log_tool
    async def save_schedule_context(
        self,
        sleep_start: Optional[str] = None,
        sleep_end: Optional[str] = None,
        preferred_exercise_times: Optional[str] = None,
        excluded_times: Optional[str] = None,
        routine_blocks_json: Optional[str] = None,
    ) -> str:
        """Save or update the user's schedule context.

        Args:
            sleep_start: Bedtime in HH:MM format (e.g. '23:00').
            sleep_end: Wake time in HH:MM format (e.g. '07:30').
            preferred_exercise_times: Comma-separated preferences (e.g. 'weekday_evenings,saturday_morning').
            excluded_times: Comma-separated excluded times (e.g. 'before 7am,friday evenings').
            routine_blocks_json: JSON array of routine blocks. Each block: {"label": "...", "days": ["monday",...], "start": "HH:MM", "end": "HH:MM"}.
        """
        self._state = load_state()

        sc = self._state.schedule_context or ScheduleContext(user_id=self._state.user.user_id)

        if sleep_start and sleep_end:
            sc.sleep_window = TimeWindow(start=sleep_start, end=sleep_end)

        if preferred_exercise_times is not None:
            sc.preferred_exercise_times = [
                p.strip() for p in preferred_exercise_times.split(",") if p.strip()
            ]

        if excluded_times is not None:
            sc.excluded_times = [
                e.strip() for e in excluded_times.split(",") if e.strip()
            ]

        if routine_blocks_json:
            try:
                blocks_data = json.loads(routine_blocks_json)
                sc.routine_blocks = [RoutineBlock(**b) for b in blocks_data]
            except (json.JSONDecodeError, Exception) as e:
                return f"Error parsing routine blocks JSON: {e}"

        self._state.schedule_context = sc
        persist_state(self._state)
        return "Schedule context saved."

    # ------------------------------------------------------------------
    # Calendar tools
    # ------------------------------------------------------------------

    @function_tool
    @_log_tool
    async def list_user_calendars(self) -> str:
        """List all Google Calendars accessible to the user.
        Returns calendar names and IDs. Use during onboarding to let the user choose which calendars to read from and write to."""
        try:
            calendars = gcal.list_calendars()
            lines = [f"- {c['summary']} (ID: {c['id']}){' [PRIMARY]' if c['primary'] else ''}" for c in calendars]
            return "Available calendars:\n" + "\n".join(lines)
        except Exception as e:
            return f"Error listing calendars: {e}"

    @function_tool
    @_log_tool
    async def get_calendar_events(
        self,
        start_date: str,
        end_date: str,
    ) -> str:
        """Get all events from the user's calendars within a date range.

        Args:
            start_date: Start date in YYYY-MM-DD format.
            end_date: End date in YYYY-MM-DD format.
        """
        self._state = load_state()
        cal_ids = self._state.user.read_calendar_ids
        if not cal_ids:
            return "No read calendars configured. Ask the user which calendars to read from."

        try:
            events = gcal.get_all_events(
                cal_ids, start_date, end_date, self._state.user.timezone
            )
            if not events:
                return f"No events found between {start_date} and {end_date}."

            lines = []
            for e in events:
                lines.append(f"- {e['start']} to {e['end']}: {e['summary']}")
            return f"Events ({len(events)}):\n" + "\n".join(lines)
        except Exception as e:
            return f"Error fetching events: {e}"

    @function_tool
    @_log_tool
    async def get_calendar_availability(
        self,
        start_date: str,
        end_date: str,
    ) -> str:
        """Get available time slots across a date range, considering all calendars, routine blocks, and sleep schedule.

        Args:
            start_date: Start date in YYYY-MM-DD format.
            end_date: End date in YYYY-MM-DD format.
        """
        self._state = load_state()
        cal_ids = self._state.user.read_calendar_ids
        if not cal_ids:
            return "No read calendars configured. Ask the user which calendars to read from."

        try:
            availability = get_availability(
                read_calendar_ids=cal_ids,
                start_date=start_date,
                end_date=end_date,
                schedule_context=self._state.schedule_context,
                timezone=self._state.user.timezone,
            )

            lines = []
            for date_str, slots in sorted(availability.items()):
                if slots:
                    slot_strs = [f"{s['start']}-{s['end']}" for s in slots]
                    lines.append(f"- {date_str}: {', '.join(slot_strs)}")
                else:
                    lines.append(f"- {date_str}: No availability")

            return "Availability:\n" + "\n".join(lines)
        except Exception as e:
            return f"Error calculating availability: {e}"

    @function_tool
    @_log_tool
    async def create_calendar_event(
        self,
        title: str,
        session_type: str,
        start_datetime: str,
        duration_minutes: int,
    ) -> str:
        """Create a single fitness session event in the user's calendar.

        Args:
            title: Session title (e.g. 'Upper body workout'). Will be prefixed with the Habits emoji.
            session_type: Type of session: strength, cardio, flexibility, or mixed.
            start_datetime: Start time in ISO format (YYYY-MM-DDTHH:MM:SS).
            duration_minutes: Duration of the session in minutes.
        """
        self._state = load_state()
        cal_id = self._state.user.write_calendar_id
        if not cal_id:
            return "No write calendar configured. Ask the user which calendar to write to."

        # Calculate end time
        start_dt = datetime.fromisoformat(start_datetime)
        end_dt = start_dt + timedelta(minutes=duration_minutes)
        end_datetime = end_dt.isoformat()

        # Check availability first
        date_str = start_dt.strftime("%Y-%m-%d")
        start_time = start_dt.strftime("%H:%M")
        is_free = check_slot_available(
            self._state.user.read_calendar_ids,
            date_str,
            start_time,
            duration_minutes,
            self._state.schedule_context,
            self._state.user.timezone,
        )
        if not is_free:
            return f"Cannot create event: the time slot {start_datetime} for {duration_minutes} minutes conflicts with an existing event or routine block."

        description = (
            f"Fitness session planned by Habits AI agent.\n\n"
            f"Session type: {session_type}\n"
            f"Duration: {duration_minutes} minutes"
        )

        try:
            event_id = gcal.create_event(
                calendar_id=cal_id,
                title=title,
                description=description,
                start_datetime=start_datetime,
                end_datetime=end_datetime,
                timezone=self._state.user.timezone,
            )

            # Add to planned sessions
            session = PlannedSession(
                session_id=f"sess_{uuid.uuid4().hex[:8]}",
                goal_id=self._state.goal.goal_id if self._state.goal else "goal_001",
                gcal_event_id=event_id,
                title=title,
                session_type=SessionType(session_type),
                duration_minutes=duration_minutes,
                scheduled_date=date_str,
                scheduled_start=start_time,
                status=SessionStatus.UPCOMING,
            )
            self._state.planned_sessions.append(session)
            persist_state(self._state)

            return f"Event created: {title} on {date_str} at {start_time} ({duration_minutes}min). Event ID: {event_id}, Session ID: {session.session_id}"
        except Exception as e:
            return f"Error creating event: {e}"

    @function_tool
    @_log_tool
    async def move_calendar_event(
        self,
        session_id: str,
        new_start_datetime: str,
    ) -> str:
        """Move an existing session to a new time.

        Args:
            session_id: The session_id of the session to move.
            new_start_datetime: New start time in ISO format (YYYY-MM-DDTHH:MM:SS).
        """
        self._state = load_state()
        cal_id = self._state.user.write_calendar_id
        if not cal_id:
            return "No write calendar configured."

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
            self._state.user.timezone,
        )
        if not is_free:
            return f"Cannot move session: the new time slot conflicts with an existing event."

        try:
            gcal.update_event(
                calendar_id=cal_id,
                event_id=session.gcal_event_id,
                updates={
                    "start_datetime": new_start_datetime,
                    "end_datetime": new_end.isoformat(),
                },
                timezone=self._state.user.timezone,
            )

            session.scheduled_date = date_str
            session.scheduled_start = start_time
            persist_state(self._state)

            return f"Session moved to {date_str} at {start_time}."
        except Exception as e:
            return f"Error moving event: {e}"

    @function_tool
    @_log_tool
    async def delete_session(self, session_id: str) -> str:
        """Delete a planned session and remove it from the calendar.

        Args:
            session_id: The session_id of the session to delete.
        """
        self._state = load_state()
        cal_id = self._state.user.write_calendar_id
        if not cal_id:
            return "No write calendar configured."

        session = next(
            (s for s in self._state.planned_sessions if s.session_id == session_id), None
        )
        if not session:
            return f"Session {session_id} not found."

        try:
            if session.gcal_event_id:
                gcal.delete_event(cal_id, session.gcal_event_id)
            session.status = SessionStatus.CANCELLED
            persist_state(self._state)
            return f"Session '{session.title}' on {session.scheduled_date} deleted."
        except Exception as e:
            return f"Error deleting event: {e}"

    @function_tool
    @_log_tool
    async def update_session_status(
        self,
        session_id: str,
        status: str,
        feedback: Optional[str] = None,
    ) -> str:
        """Update the status of a planned session (e.g. after a check-in).

        Args:
            session_id: The session_id to update.
            status: New status: completed, skipped, partial, deleted_by_user.
            feedback: Optional user feedback about the session.
        """
        self._state = load_state()

        session = next(
            (s for s in self._state.planned_sessions if s.session_id == session_id), None
        )
        if not session:
            return f"Session {session_id} not found."

        session.status = SessionStatus(status)
        if feedback:
            session.user_feedback = feedback
        persist_state(self._state)

        return f"Session '{session.title}' status updated to {status}."

    # ------------------------------------------------------------------
    # Plan generation tool
    # ------------------------------------------------------------------

    @function_tool
    @_log_tool
    async def generate_and_book_plan(self) -> str:
        """Generate a 4-week fitness plan and book all sessions into the calendar.
        Uses the saved goal, schedule context, and calendar availability.
        Call this when you have all the information needed (goal + schedule + calendar preferences)."""
        self._state = load_state()

        if not self._state.goal:
            return "Cannot generate plan: no goal has been saved yet."
        if not self._state.user.write_calendar_id:
            return "Cannot generate plan: no write calendar configured."
        if not self._state.user.read_calendar_ids:
            return "Cannot generate plan: no read calendars configured."

        try:
            sessions = generate_plan(
                goal=self._state.goal,
                schedule_context=self._state.schedule_context,
                read_calendar_ids=self._state.user.read_calendar_ids,
                write_calendar_id=self._state.user.write_calendar_id,
                timezone=self._state.user.timezone,
            )

            self._state.planned_sessions.extend(sessions)
            self._state.user.conversation_phase = ConversationPhase.PLAN_PROPOSED
            self._state.user.last_conversation_date = datetime.now()
            persist_state(self._state)

            # Build summary
            lines = [f"Plan generated: {len(sessions)} sessions over 4 weeks.\n"]
            for s in sessions:
                lines.append(
                    f"- {s.scheduled_date} {s.scheduled_start}: {s.title} "
                    f"({s.session_type.value}, {s.duration_minutes}min)"
                )

            return "\n".join(lines)
        except Exception as e:
            return f"Error generating plan: {e}"

    # ------------------------------------------------------------------
    # Exercise suggestions tool
    # ------------------------------------------------------------------

    @function_tool
    @_log_tool
    async def get_exercise_suggestions(
        self,
        session_type: Optional[str] = None,
        muscle_focus: Optional[str] = None,
    ) -> str:
        """Get exercise suggestions for a workout session based on the user's equipment and constraints.

        Call this when creating a session or when the user asks what exercises to do.
        Use the results to pick 4-6 exercises for the session's workout plan.

        Args:
            session_type: Type of session: strength, cardio, flexibility, or mixed. If omitted, returns exercises of all types.
            muscle_focus: Optional muscle group to focus on (e.g. 'chest', 'back', 'legs', 'core').
        """
        self._state = load_state()

        # Normalise session_type — LLM sometimes passes empty string
        clean_type = session_type.strip().lower() if session_type and session_type.strip() else None

        equipment = self._state.goal.preferences.equipment if self._state.goal else []
        constraints = self._state.goal.preferences.constraints if self._state.goal else []
        difficulty = self._state.goal.fitness_level if self._state.goal else "beginner"

        exercises = get_exercises(
            session_type=clean_type,
            equipment=equipment,
            constraints=constraints,
            difficulty=difficulty,
            muscle_focus=muscle_focus,
        )

        return format_exercise_list(exercises)

    # ------------------------------------------------------------------
    # Check-in tools
    # ------------------------------------------------------------------

    @function_tool
    @_log_tool
    async def check_for_deleted_events(self) -> str:
        """Check which planned sessions have been manually deleted from the calendar by the user.
        Use this at the start of a check-in conversation."""
        self._state = load_state()
        cal_id = self._state.user.write_calendar_id
        if not cal_id:
            return "No write calendar configured."

        deleted = []
        for session in self._state.planned_sessions:
            if session.status == SessionStatus.UPCOMING and session.gcal_event_id:
                if not gcal.event_exists(cal_id, session.gcal_event_id):
                    session.status = SessionStatus.DELETED_BY_USER
                    deleted.append(session)

        if deleted:
            persist_state(self._state)
            lines = [f"Found {len(deleted)} sessions deleted by user:"]
            for s in deleted:
                lines.append(f"- {s.scheduled_date} {s.scheduled_start}: {s.title}")
            return "\n".join(lines)

        return "No sessions have been deleted from the calendar."

    @function_tool
    @_log_tool
    async def get_sessions_since_last_conversation(self) -> str:
        """Get all planned sessions since the last conversation date.
        Use this at the start of a check-in to review what happened."""
        self._state = load_state()

        last_date = self._state.user.last_conversation_date
        if not last_date:
            return "No previous conversation recorded."

        now = datetime.now()
        relevant = [
            s for s in self._state.planned_sessions
            if datetime.fromisoformat(s.scheduled_date) >= last_date.replace(hour=0, minute=0, second=0)
            and datetime.fromisoformat(s.scheduled_date) <= now
        ]

        if not relevant:
            return "No sessions were scheduled since the last conversation."

        lines = [f"Sessions since last conversation ({last_date.strftime('%d %B')}):\n"]
        for s in sorted(relevant, key=lambda x: (x.scheduled_date, x.scheduled_start)):
            lines.append(
                f"- {s.scheduled_date} {s.scheduled_start}: {s.title} "
                f"[status: {s.status.value}] [id: {s.session_id}]"
            )

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Conversation logging
    # ------------------------------------------------------------------

    @function_tool
    @_log_tool
    async def save_conversation_log(
        self,
        summary: str,
        adaptations: Optional[str] = None,
    ) -> str:
        """Save a summary of the current conversation. Call this at the end of each conversation.

        Args:
            summary: Brief summary of what was discussed and decided.
            adaptations: Comma-separated list of adaptations made (if any).
        """
        self._state = load_state()

        log = ConversationLog(
            log_id=f"log_{uuid.uuid4().hex[:6]}",
            user_id=self._state.user.user_id,
            conversation_date=datetime.now(),
            phase_at_start=self._session_start_phase,
            phase_at_end=self._state.user.conversation_phase,
            summary=summary,
            adaptations_made=[a.strip() for a in (adaptations or "").split(",") if a.strip()],
        )

        self._state.conversation_logs.append(log)
        self._state.user.last_conversation_date = datetime.now()
        persist_state(self._state)

        return "Conversation log saved."


# ------------------------------------------------------------------
# LiveKit server setup
# ------------------------------------------------------------------

server = AgentServer()


@server.rtc_session(agent_name="habits-agent")
async def entrypoint(ctx: agents.JobContext):
    room_name = ctx.room.name if ctx.room else "unknown"
    logger.info("SESSION START — room: %s", room_name)
    await ctx.connect()

    # ------------------------------------------------------------------
    # Reminder call rooms (outbound phone calls via SIP)
    # ------------------------------------------------------------------
    if room_name.startswith("reminder_"):
        logger.info("Detected reminder room — launching ReminderAgent")
        await _handle_reminder_room(ctx)
        return

    # ------------------------------------------------------------------
    # Normal web-based agent session
    # ------------------------------------------------------------------
    session = AgentSession(
        llm=openai.realtime.RealtimeModel(
            voice="alloy",
            model="gpt-4o-realtime-preview",
            input_audio_transcription=InputAudioTranscription(
                model="whisper-1",
                language="en",
            ),
        ),
    )

    agent = HabitsAgent()

    await session.start(
        room=ctx.room,
        agent=agent,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=noise_cancellation.BVC(),
            ),
        ),
    )

    # Generate the opening message based on the current phase
    phase = agent._state.user.conversation_phase
    logger.info("OPENING — phase: %s", phase.value)
    if phase == ConversationPhase.ONBOARDING_GOAL:
        await session.generate_reply(
            instructions="Welcome the user warmly. Introduce yourself as Habits, their AI fitness planning assistant. Briefly explain that you'll help them set fitness goals and book sessions into their Google Calendar. Then ask what fitness goal they'd like to work towards."
        )
    elif phase == ConversationPhase.ONBOARDING_SCHEDULE:
        await session.generate_reply(
            instructions="Welcome the user back. Remind them you've captured their fitness goal. Now you need to understand their daily routine and schedule to find the best times for exercise. Start by asking about their typical day — when they wake up, their work hours, and any regular commitments."
        )
    elif phase == ConversationPhase.PLAN_PROPOSED:
        await session.generate_reply(
            instructions="Welcome the user back. Their fitness plan has been booked into their calendar. Ask if they've had a chance to look at it and whether they'd like to make any changes."
        )
    elif phase in (ConversationPhase.PLAN_CONFIRMED, ConversationPhase.CHECK_IN):
        await session.generate_reply(
            instructions="Welcome the user back for a check-in. Before speaking, use the check_for_deleted_events and get_sessions_since_last_conversation tools to understand what's happened since the last conversation. Then summarise and ask how their sessions went."
        )


async def _handle_reminder_room(ctx: agents.JobContext):
    """Handle an outbound reminder phone call room.

    The SIP participant (phone user) is already in the room, placed there
    by CreateSIPParticipant. We parse their metadata to understand which
    sessions to remind about, then launch the ReminderAgent.
    """
    import asyncio as _asyncio

    metadata = {}
    room_name = ctx.room.name if ctx.room else "unknown"

    # Strategy 1: Read room metadata (set when room was created)
    if ctx.room and ctx.room.metadata:
        logger.debug("Room metadata present: %s", ctx.room.metadata[:200])
        try:
            metadata = json.loads(ctx.room.metadata)
        except json.JSONDecodeError:
            logger.warning("Failed to parse room metadata")

    # Strategy 2: Check participant metadata
    if not metadata.get("sessions"):
        logger.debug(
            "No sessions in room metadata, checking %d remote participants",
            len(ctx.room.remote_participants) if ctx.room else 0,
        )
        for pid, participant in (ctx.room.remote_participants.items() if ctx.room else {}):
            logger.debug("Participant %s metadata: %s", pid, participant.metadata[:200] if participant.metadata else "(none)")
            if participant.metadata:
                try:
                    metadata = json.loads(participant.metadata)
                    if metadata.get("sessions"):
                        break
                except json.JSONDecodeError:
                    continue

    # Strategy 3: Fetch room info from LiveKit API (most reliable)
    if not metadata.get("sessions"):
        logger.info("Fetching room metadata from LiveKit API for room: %s", room_name)
        try:
            lk_url = os.environ.get("LIVEKIT_URL", "")
            lk_key = os.environ.get("LIVEKIT_API_KEY", "")
            lk_secret = os.environ.get("LIVEKIT_API_SECRET", "")
            if lk_url and lk_key and lk_secret:
                from livekit import api as lk_api
                lk = lk_api.LiveKitAPI(lk_url, lk_key, lk_secret)

                # List participants to get their metadata
                parts_resp = await lk.room.list_participants(
                    lk_api.ListParticipantsRequest(room=room_name)
                )
                for p in parts_resp.participants:
                    logger.debug("API participant %s metadata: %s", p.identity, p.metadata[:200] if p.metadata else "(none)")
                    if p.metadata:
                        try:
                            candidate = json.loads(p.metadata)
                            if candidate.get("sessions"):
                                metadata = candidate
                                break
                        except json.JSONDecodeError:
                            continue

                # Also try room metadata via rooms list
                if not metadata.get("sessions"):
                    rooms_resp = await lk.room.list_rooms(lk_api.ListRoomsRequest(names=[room_name]))
                    for r in rooms_resp.rooms:
                        logger.debug("API room %s metadata: %s", r.name, r.metadata[:200] if r.metadata else "(none)")
                        if r.metadata:
                            try:
                                candidate = json.loads(r.metadata)
                                if candidate.get("sessions"):
                                    metadata = candidate
                                    break
                            except json.JSONDecodeError:
                                continue

                await lk.aclose()
        except Exception as e:
            logger.error("Failed to fetch room metadata from API: %s", e)

    user_name = metadata.get("user_name", "there")
    timezone = metadata.get("timezone", "Europe/London")
    sessions = metadata.get("sessions", [])

    if not sessions:
        logger.error("No sessions found in room or participant metadata for reminder room")
        return

    logger.info(
        "Reminder room — user: %s, sessions: %d (%s)",
        user_name,
        len(sessions),
        ", ".join(s.get("title", "?") for s in sessions),
    )

    # Wait for the phone participant to actually join (i.e. user picks up)
    logger.info("Waiting for phone participant to join room...")
    try:
        phone_participant = await ctx.wait_for_participant(
            identity=f"phone_{metadata.get('user_id', 'user')}",
        )
        logger.info("Phone participant joined: %s", phone_participant.identity)
    except Exception as e:
        logger.warning("wait_for_participant raised %s: %s — starting anyway", type(e).__name__, e)

    # Use a fast REST-based TTS for the instant greeting,
    # and the Realtime model for the actual conversation
    session = AgentSession(
        llm=openai.realtime.RealtimeModel(
            voice="alloy",
            model="gpt-4o-realtime-preview",
            input_audio_transcription=InputAudioTranscription(
                model="whisper-1",
                language="en",
            ),
        ),
        tts=openai.TTS(voice="alloy", model="gpt-4o-mini-tts"),
    )

    agent = ReminderAgent(
        sessions=sessions,
        user_name=user_name,
        timezone=timezone,
    )

    await session.start(
        room=ctx.room,
        agent=agent,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=noise_cancellation.BVC(),
            ),
        ),
    )

    # Instant greeting via fast TTS — plays immediately while Realtime model warms up
    session_titles = ", ".join(s.get("title", "workout") for s in sessions)
    logger.info("Playing instant greeting via TTS...")
    greeting = await session.say(
        f"Hi {user_name}! It's Habits calling with a quick reminder about your {session_titles}. One moment.",
        allow_interruptions=False,
    )
    await greeting

    # Hand off to the AI for the real conversation
    logger.info("Starting AI reminder conversation about: %s", session_titles)
    await session.generate_reply(
        instructions=f"You've just been connected to {user_name} on a phone call and a greeting has already been played. Now remind them about their upcoming session: {session_titles}. Ask if they're all set or need to make a change. Keep it brief."
    )


if __name__ == "__main__":
    agents.cli.run_app(server)
