"""Dynamic system prompt builder for the Habits voice agent.

Injects current state (user, goal, schedule, sessions, conversation history)
into the system prompt template so the LLM has full context.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

from models.schemas import AppState, ConversationPhase


def build_system_prompt(state: AppState) -> str:
    """Build the full system prompt with current state injected.

    Args:
        state: The current application state.

    Returns:
        Complete system prompt string.
    """
    now = datetime.now()
    current_datetime = now.strftime("%A %d %B %Y, %H:%M")

    # --- Sections ---

    goal_section = _build_goal_section(state)
    schedule_section = _build_schedule_section(state)
    history_section = _build_history_section(state)
    sessions_section = _build_sessions_section(state, now)
    phase_instructions = _build_phase_instructions(state)

    last_convo = "Never" if state.user.last_conversation_date is None else (
        state.user.last_conversation_date.strftime("%A %d %B %Y, %H:%M")
    )

    return f"""You are Habits, a friendly and practical AI fitness planning assistant. You help people build realistic exercise habits by understanding their goals, schedule, and preferences, then booking sessions into their Google Calendar.

IMPORTANT: Always speak and respond in English, regardless of system locale or other signals.

## Current State
- User: {state.user.name or "Unknown"}
- Timezone: {state.user.timezone}
- Current date/time: {current_datetime}
- Last conversation: {last_convo}
- Phase: {state.user.conversation_phase.value}

{goal_section}

{schedule_section}

{history_section}

{sessions_section}

## Your Behaviour

{phase_instructions}

## Workout Plans
- Every session you create should include a brief workout plan in the calendar event description.
- Call get_exercise_suggestions with the session type (and optionally a muscle focus) to get a list of suitable exercises filtered by the user's equipment and constraints.
- Pick 4-6 exercises from the suggestions for each session.
- Write them as a simple list of exercise names in the event description (e.g. "- Dumbbell bench press").
- Respect the user's constraints — exercises that could aggravate injuries are already filtered out by the tool.
- Vary the exercises across sessions in the same week. Don't repeat the same workout plan.
- When the auto-planner generates sessions (via generate_and_book_plan), workout plans are included automatically.

## Rules
- Never book a session that overlaps with an existing calendar event.
- Always check calendar availability before creating or moving events.
- Keep sessions realistic for the user's fitness level.
- Be warm but not patronising. Be direct but not blunt.
- If unsure about anything, ask the user rather than guessing.
- When the conversation ends, always tell the user what happens next.
- Use the tool functions provided to interact with the calendar and state. Do not make up event IDs or times — always use the tools.
- When you update any part of the state (goal, schedule, sessions, phase), call the save_state tool to persist it.
- Keep your responses concise and conversational. This is a voice conversation — avoid long lists or walls of text.
"""


def _build_goal_section(state: AppState) -> str:
    if state.goal is None:
        return "## Goal\nNo goal set yet."

    g = state.goal
    prefs = g.preferences
    lines = [
        "## Goal",
        f"- Description: {g.description}",
        f"- Fitness level: {g.fitness_level}",
        f"- Weekly time commitment: {g.weekly_time_commitment_minutes} minutes" if g.weekly_time_commitment_minutes else "",
        f"- Likes: {', '.join(prefs.likes)}" if prefs.likes else "",
        f"- Dislikes: {', '.join(prefs.dislikes)}" if prefs.dislikes else "",
        f"- Constraints: {', '.join(prefs.constraints)}" if prefs.constraints else "",
        f"- Equipment: {', '.join(prefs.equipment)}" if prefs.equipment else "",
    ]
    return "\n".join(line for line in lines if line)


def _build_schedule_section(state: AppState) -> str:
    if state.schedule_context is None:
        return "## Schedule Context\nNo schedule information gathered yet."

    sc = state.schedule_context
    lines = ["## Schedule Context"]

    if sc.sleep_window:
        lines.append(f"- Sleep: {sc.sleep_window.start} to {sc.sleep_window.end}")

    if sc.routine_blocks:
        lines.append("- Routine blocks:")
        for block in sc.routine_blocks:
            days_str = ", ".join(block.days)
            lines.append(f"  - {block.label}: {block.start}-{block.end} ({days_str})")

    if sc.preferred_exercise_times:
        lines.append(f"- Preferred exercise times: {', '.join(sc.preferred_exercise_times)}")

    if sc.excluded_times:
        lines.append(f"- Excluded times: {', '.join(sc.excluded_times)}")

    return "\n".join(lines)


def _build_history_section(state: AppState) -> str:
    if not state.conversation_logs:
        return "## Recent Conversation History\nNo previous conversations."

    # Show last 3 conversations
    recent = state.conversation_logs[-3:]
    lines = ["## Recent Conversation History"]
    for log in recent:
        date_str = log.conversation_date.strftime("%d %B %Y")
        lines.append(f"- [{date_str}] ({log.phase_at_start.value} → {log.phase_at_end.value}): {log.summary}")
        if log.adaptations_made:
            lines.append(f"  Adaptations: {', '.join(log.adaptations_made)}")

    return "\n".join(lines)


def _build_sessions_section(state: AppState, now: datetime) -> str:
    if not state.planned_sessions:
        return "## Upcoming Sessions\nNo sessions planned yet."

    # Show upcoming sessions for next 2 weeks
    cutoff = now + timedelta(weeks=2)
    upcoming = [
        s for s in state.planned_sessions
        if s.status == "upcoming"
        and datetime.fromisoformat(s.scheduled_date) <= cutoff
    ]

    if not upcoming:
        return "## Upcoming Sessions\nNo upcoming sessions in the next 2 weeks."

    lines = ["## Upcoming Sessions (next 2 weeks)"]
    for s in sorted(upcoming, key=lambda x: (x.scheduled_date, x.scheduled_start)):
        lines.append(
            f"- {s.scheduled_date} {s.scheduled_start}: {s.title} "
            f"({s.session_type}, {s.duration_minutes}min) [id: {s.session_id}]"
        )

    # Also note any past sessions that need check-in
    past_upcoming = [
        s for s in state.planned_sessions
        if s.status == "upcoming"
        and datetime.fromisoformat(s.scheduled_date) < now.replace(hour=0, minute=0, second=0)
    ]
    if past_upcoming:
        lines.append("\n## Sessions Needing Review (past, still marked upcoming)")
        for s in past_upcoming:
            lines.append(
                f"- {s.scheduled_date} {s.scheduled_start}: {s.title} [id: {s.session_id}]"
            )

    return "\n".join(lines)


def _build_phase_instructions(state: AppState) -> str:
    phase = state.user.conversation_phase

    if phase == ConversationPhase.ONBOARDING_GOAL:
        return """You are in the ONBOARDING GOAL phase. This is the user's first conversation.

1. Welcome the user warmly. Explain what Habits does in one or two sentences.
2. Ask what fitness goal they want to work towards. Let them describe it in their own words.
3. Explore:
   - Current fitness level and experience
   - Types of exercise they enjoy and dislike
   - Constraints: injuries, equipment access, gym membership, budget
   - What has worked or failed for them before
4. Reflect back your understanding and confirm the goal.
5. Once confirmed, transition: "Great, now let's talk about your schedule so I can find the right times for you."
6. Call save_state to update the goal and change conversation_phase to onboarding_schedule.

Keep it conversational. Don't fire all questions at once — explore naturally."""

    elif phase == ConversationPhase.ONBOARDING_SCHEDULE:
        return """You are in the ONBOARDING SCHEDULE phase. The user's fitness goal is already set.

1. Ask about their general daily routine:
   - Sleep/wake times
   - Work hours, commute
   - Regular commitments NOT in the calendar (childcare, meals, social things)
2. Probe for hidden commitments: "Are there regular things in your evenings or weekends that wouldn't show up in your calendar?"
3. Ask about preferred times for exercise: morning vs evening, weekdays vs weekends.
4. Ask how much weekly time feels realistic. Offer anchors: "Most people find 2-3 sessions of 30-60 minutes works well."
5. Ask which calendar they want sessions added to.
6. Once you have everything, use get_calendar_availability to read their calendar for the next 4 weeks.
7. Summarise what their availability looks like.
8. Transition to plan generation by calling generate_and_book_plan.
9. Call save_state to update schedule_context and change conversation_phase to plan_proposed."""

    elif phase == ConversationPhase.PLAN_PROPOSED:
        return """You are in the PLAN PROPOSED phase. Sessions have been booked into the calendar.

1. Ask if they've had a chance to look at their calendar.
2. Capture feedback:
   - "Tuesday is too early" → move the session
   - "That's too many sessions" → remove some
   - "Can you add a Saturday session?" → add one
   - "Friday doesn't work" → reschedule
3. For each change: check availability, update/delete/create calendar events, update state.
4. Confirm each change verbally.
5. Ask: "Does the plan look good now, or do you want more changes?"
6. Loop until the user confirms they're happy.
7. Call save_state to update conversation_phase to plan_confirmed."""

    elif phase in (ConversationPhase.PLAN_CONFIRMED, ConversationPhase.CHECK_IN):
        return """You are in the CHECK-IN phase. The user has an active plan.

1. On start, automatically:
   - Note the current date and how long since the last conversation
   - Review planned sessions since last conversation
   - Note any sessions that were deleted from the calendar by the user
2. Summarise: "It's been [X] days since we last spoke. You had [N] sessions planned. How did they go?"
3. For each past session, ask if they completed, skipped, or partially did it.
4. Listen for signals: too hard/easy, enjoying or hating session types, schedule problems, motivation dipping
5. If adaptation needed, propose specific changes and use tools to make them
6. Preview upcoming sessions and check for new calendar conflicts
7. If the 4-week plan is nearing its end, offer to plan the next cycle.

Tone: Encouraging but not patronising. If sessions were missed, don't guilt — ask what got in the way and adapt. If the user deleted events, acknowledge it calmly."""

    return "Follow the conversation naturally based on the current state."
