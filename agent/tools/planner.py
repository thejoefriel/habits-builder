"""Session planning logic for generating 4-week fitness plans.

Uses the goal, preferences, schedule context, and availability to create
a realistic plan of specific sessions with dates and times.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, time as dt_time

from models.schemas import (
    Goal,
    ScheduleContext,
    PlannedSession,
    SessionType,
    SessionStatus,
)
import random

from tools.availability import get_free_slots_for_day, _parse_time, _time_to_minutes
from tools.calendar import get_all_events, create_event, HABITS_TAG
from tools.exercises import get_exercises

logger = logging.getLogger(__name__)


# --- Session templates ---

# Maps session types to default title patterns
SESSION_TEMPLATES = {
    SessionType.STRENGTH: [
        "Upper body workout",
        "Lower body workout",
        "Full body strength",
        "Core workout",
    ],
    SessionType.CARDIO: [
        "30min run",
        "Interval training",
        "Cycling session",
        "Swimming",
        "Brisk walk",
    ],
    SessionType.FLEXIBILITY: [
        "Yoga / flexibility",
        "Stretching session",
        "Mobility work",
    ],
    SessionType.MIXED: [
        "Circuit training",
        "Bodyweight workout",
        "Active recovery",
    ],
}


def _choose_session_types(
    goal: Goal,
    sessions_per_week: int,
) -> list[SessionType]:
    """Choose a balanced mix of session types for one week.

    Considers user preferences (likes/dislikes) and fitness level.
    """
    likes = [l.lower() for l in goal.preferences.likes]
    dislikes = [d.lower() for d in goal.preferences.dislikes]

    # Build a preference-weighted pool of session types
    type_scores: dict[SessionType, float] = {
        SessionType.STRENGTH: 1.0,
        SessionType.CARDIO: 1.0,
        SessionType.FLEXIBILITY: 0.5,
        SessionType.MIXED: 0.8,
    }

    # Boost/penalise based on likes/dislikes
    strength_keywords = ["strength", "weights", "bodyweight", "resistance", "pull-up", "push-up"]
    cardio_keywords = ["running", "run", "cycling", "swimming", "walk", "cardio", "hiit"]
    flex_keywords = ["yoga", "stretching", "flexibility", "mobility", "pilates"]

    for like in likes:
        if any(kw in like for kw in strength_keywords):
            type_scores[SessionType.STRENGTH] += 1.0
        if any(kw in like for kw in cardio_keywords):
            type_scores[SessionType.CARDIO] += 1.0
        if any(kw in like for kw in flex_keywords):
            type_scores[SessionType.FLEXIBILITY] += 1.0

    for dislike in dislikes:
        if any(kw in dislike for kw in strength_keywords):
            type_scores[SessionType.STRENGTH] -= 1.5
        if any(kw in dislike for kw in cardio_keywords):
            type_scores[SessionType.CARDIO] -= 1.5
        if any(kw in dislike for kw in flex_keywords):
            type_scores[SessionType.FLEXIBILITY] -= 1.5

    # Remove types with very negative scores
    available_types = [t for t, s in type_scores.items() if s > 0]
    if not available_types:
        available_types = [SessionType.MIXED]

    # Sort by score descending and build a week plan
    sorted_types = sorted(available_types, key=lambda t: type_scores[t], reverse=True)

    weekly_plan = []
    for i in range(sessions_per_week):
        # Cycle through types, favouring higher-scored ones
        session_type = sorted_types[i % len(sorted_types)]
        # Avoid back-to-back same type
        if weekly_plan and weekly_plan[-1] == session_type and len(sorted_types) > 1:
            alt_idx = (sorted_types.index(session_type) + 1) % len(sorted_types)
            session_type = sorted_types[alt_idx]
        weekly_plan.append(session_type)

    return weekly_plan


def _choose_title(session_type: SessionType, goal: Goal, used_titles: set[str]) -> str:
    """Choose a session title based on type and user preferences."""
    likes = [l.lower() for l in goal.preferences.likes]
    templates = SESSION_TEMPLATES[session_type]

    # Prefer titles that match user likes
    for template in templates:
        if template.lower() not in used_titles:
            for like in likes:
                if like in template.lower() or template.lower() in like:
                    used_titles.add(template.lower())
                    return template

    # Fall back to cycling through templates
    for template in templates:
        if template.lower() not in used_titles:
            used_titles.add(template.lower())
            return template

    # If all used, just pick the first one
    return templates[0]


def _determine_sessions_per_week(goal: Goal) -> int:
    """Determine how many sessions per week based on goal and fitness level."""
    weekly_minutes = goal.weekly_time_commitment_minutes or 150

    if goal.fitness_level.lower() in ["beginner", "new", "starting"]:
        # Conservative: 2-3 sessions
        if weekly_minutes <= 90:
            return 2
        elif weekly_minutes <= 180:
            return 3
        else:
            return 3
    elif goal.fitness_level.lower() in ["intermediate", "moderate"]:
        if weekly_minutes <= 120:
            return 3
        elif weekly_minutes <= 240:
            return 4
        else:
            return 4
    else:
        # Advanced
        if weekly_minutes <= 180:
            return 3
        elif weekly_minutes <= 300:
            return 4
        else:
            return 5

    return 3  # safe default


def _determine_session_duration(
    goal: Goal,
    sessions_per_week: int,
) -> int:
    """Determine session duration in minutes."""
    weekly_minutes = goal.weekly_time_commitment_minutes or 150
    avg_duration = weekly_minutes // sessions_per_week

    # Round to nearest 15-min increment, clamped to 15-60
    rounded = max(15, min(60, round(avg_duration / 15) * 15))

    # Beginners get shorter sessions
    if goal.fitness_level.lower() in ["beginner", "new", "starting"]:
        rounded = min(rounded, 30)

    return rounded


def _find_best_slot(
    date: datetime,
    duration_minutes: int,
    free_slots: list[tuple[dt_time, dt_time]],
    schedule_context: ScheduleContext | None,
) -> str | None:
    """Find the best time slot on a given day for a session.

    Prefers the user's preferred exercise times. Returns HH:MM or None.
    """
    if not free_slots:
        return None

    preferred = []
    if schedule_context:
        preferred = [p.lower() for p in schedule_context.preferred_exercise_times]

    day_name = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"][
        date.weekday()
    ]
    is_weekend = day_name in ["saturday", "sunday"]

    # Score each free slot
    scored_slots: list[tuple[float, str]] = []
    for slot_start, slot_end in free_slots:
        slot_start_min = _time_to_minutes(slot_start)
        slot_end_min = _time_to_minutes(slot_end)

        if slot_end_min - slot_start_min < duration_minutes:
            continue

        score = 0.0

        # Preference scoring
        if is_weekend and "saturday_morning" in preferred and 7 * 60 <= slot_start_min <= 12 * 60:
            score += 3.0
        if is_weekend and "sunday_morning" in preferred and 7 * 60 <= slot_start_min <= 12 * 60:
            score += 3.0
        if not is_weekend and "weekday_evenings" in preferred and slot_start_min >= 17 * 60:
            score += 3.0
        if not is_weekend and "weekday_mornings" in preferred and slot_start_min <= 10 * 60:
            score += 3.0

        # Slight preference for later morning / early evening (natural exercise times)
        if 7 * 60 <= slot_start_min <= 10 * 60:
            score += 1.0
        if 17 * 60 <= slot_start_min <= 20 * 60:
            score += 1.0

        # Penalise very early or very late
        if slot_start_min < 7 * 60:
            score -= 2.0
        if slot_start_min > 21 * 60:
            score -= 2.0

        scored_slots.append((score, slot_start.strftime("%H:%M")))

    if not scored_slots:
        return None

    # Return the highest-scored slot
    scored_slots.sort(key=lambda s: s[0], reverse=True)
    return scored_slots[0][1]


def _build_workout_plan(
    session_type: SessionType,
    goal: Goal,
    num_exercises: int = 5,
) -> str:
    """Build a brief workout plan (exercise names) for a session.

    Uses the exercise dataset, filtered by session type, user equipment,
    and constraints. Picks a varied selection of exercises.

    Args:
        session_type: The type of session.
        goal: The user's goal (for equipment and constraints).
        num_exercises: Number of exercises to include.

    Returns:
        Formatted string of exercise names, one per line with "- " prefix.
    """
    exercises = get_exercises(
        session_type=session_type.value,
        equipment=goal.preferences.equipment,
        constraints=goal.preferences.constraints,
        difficulty=goal.fitness_level,
    )

    if not exercises:
        return "- General workout (no specific exercises matched)"

    # Shuffle for variety, then pick up to num_exercises
    selected = list(exercises)
    random.shuffle(selected)
    selected = selected[:num_exercises]

    return "\n".join(f"- {ex['name']}" for ex in selected)


def generate_plan(
    goal: Goal,
    schedule_context: ScheduleContext | None,
    read_calendar_ids: list[str],
    write_calendar_id: str,
    timezone: str = "Europe/London",
    start_from: datetime | None = None,
) -> list[PlannedSession]:
    """Generate a 4-week fitness plan and book sessions into Google Calendar.

    Args:
        goal: The user's fitness goal.
        schedule_context: Schedule constraints and preferences.
        read_calendar_ids: Calendars to check for conflicts.
        write_calendar_id: Calendar to create events in.
        timezone: User's timezone.
        start_from: Date to start planning from (defaults to tomorrow).

    Returns:
        List of PlannedSession objects with gcal_event_ids populated.
    """
    if start_from is None:
        start_from = datetime.now() + timedelta(days=1)
        # Start from next Monday if today is not Monday
        days_until_monday = (7 - start_from.weekday()) % 7
        if days_until_monday > 0:
            start_from += timedelta(days=days_until_monday)

    plan_end = start_from + timedelta(weeks=4)

    sessions_per_week = _determine_sessions_per_week(goal)
    session_duration = _determine_session_duration(goal, sessions_per_week)

    logger.info(
        "Planning %d sessions/week of %d min each for 4 weeks",
        sessions_per_week,
        session_duration,
    )

    # Fetch all calendar events for the plan period
    start_str = start_from.strftime("%Y-%m-%d")
    end_str = plan_end.strftime("%Y-%m-%d")
    calendar_events = get_all_events(read_calendar_ids, start_str, end_str, timezone)

    planned_sessions: list[PlannedSession] = []
    used_titles: set[str] = set()

    # Plan week by week
    for week in range(4):
        week_start = start_from + timedelta(weeks=week)
        session_types = _choose_session_types(goal, sessions_per_week)

        sessions_scheduled_this_week = 0
        last_session_day: int | None = None

        for day_offset in range(7):
            if sessions_scheduled_this_week >= sessions_per_week:
                break

            current_date = week_start + timedelta(days=day_offset)

            # Ensure rest day between sessions (at least 1 day gap)
            if last_session_day is not None and day_offset - last_session_day < 2:
                continue

            # Get free slots for this day
            free_slots = get_free_slots_for_day(
                current_date, calendar_events, schedule_context, session_duration
            )

            best_time = _find_best_slot(
                current_date, session_duration, free_slots, schedule_context
            )

            if best_time is None:
                continue

            # We have a slot - create the session
            session_type = session_types[sessions_scheduled_this_week]
            title = _choose_title(session_type, goal, used_titles)

            session_date_str = current_date.strftime("%Y-%m-%d")
            start_dt_str = f"{session_date_str}T{best_time}:00"

            # Calculate end time
            start_minutes = _time_to_minutes(_parse_time(best_time))
            end_minutes = start_minutes + session_duration
            end_time = f"{end_minutes // 60:02d}:{end_minutes % 60:02d}"
            end_dt_str = f"{session_date_str}T{end_time}:00"

            # Build workout plan from exercise dataset
            workout_plan = _build_workout_plan(session_type, goal)

            # Build event description
            description = (
                f"Fitness session planned by Habits AI agent.\n\n"
                f"Session type: {session_type.value}\n"
                f"Duration: {session_duration} minutes\n\n"
                f"Workout plan:\n{workout_plan}\n\n"
                f"{HABITS_TAG}"
            )

            # Create the calendar event
            try:
                gcal_event_id = create_event(
                    calendar_id=write_calendar_id,
                    title=title,
                    description=description,
                    start_datetime=start_dt_str,
                    end_datetime=end_dt_str,
                    timezone=timezone,
                )
            except Exception as e:
                logger.error("Failed to create event for %s %s: %s", session_date_str, best_time, e)
                continue

            session = PlannedSession(
                session_id=f"sess_{uuid.uuid4().hex[:8]}",
                goal_id=goal.goal_id,
                gcal_event_id=gcal_event_id,
                title=title,
                session_type=session_type,
                duration_minutes=session_duration,
                scheduled_date=session_date_str,
                scheduled_start=best_time,
                status=SessionStatus.UPCOMING,
            )

            planned_sessions.append(session)
            sessions_scheduled_this_week += 1
            last_session_day = day_offset

            logger.info(
                "Scheduled: %s on %s at %s (%d min)",
                title,
                session_date_str,
                best_time,
                session_duration,
            )

    logger.info("Plan complete: %d sessions scheduled over 4 weeks", len(planned_sessions))
    return planned_sessions
