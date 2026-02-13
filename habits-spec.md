# Habits: AI Voice Agent for Fitness Goal Planning

## Overview

Habits is a voice-first AI agent that helps users set fitness goals, build realistic plans, and book sessions directly into their Google Calendar. It uses OpenAI's Realtime API via LiveKit for voice interaction and Google Calendar API for reading availability and creating/managing events.

This is a single-user MVP. Calendar credentials are stored in `.env`. The goal type is limited to fitness.

---

## Tech Stack

- **Voice**: OpenAI Realtime API via LiveKit (same setup as existing `livekit-voice-agent` project)
- **Calendar**: Google Calendar API (read from multiple calendars, write to one)
- **Storage**: JSON file for persistent state
- **Runtime**: Python (to match existing LiveKit agent setup)

---

## Core Concepts

### Conversation Phases

The AI tracks where the user is in their journey via a `conversation_phase` field:

| Phase | Description |
|---|---|
| `onboarding_goal` | First conversation. Gathering the user's fitness goal, experience, preferences, and constraints. |
| `onboarding_schedule` | Gathering daily routine, commitments not in calendar, preferred exercise times, time commitment, and which calendar to write to. |
| `plan_proposed` | AI has booked sessions into the calendar. Waiting for user to review and come back with feedback. |
| `plan_confirmed` | User has approved the plan. Sessions are active. |
| `check_in` | Ongoing. User returns for check-ins. AI reviews what happened since last conversation and adapts. |

### Event Tagging

All calendar events created by the AI must be identifiable. Use a consistent prefix in the event title:

```
🏋️ Habits: Upper body workout
🏋️ Habits: 30min run
🏋️ Habits: Yoga / flexibility
```

This allows the AI to query its own events and distinguish them from the user's other calendar entries. The event description should also include a machine-readable tag like `[habits-agent]` for reliable filtering.

### No Double-Booking (Hard Rule)

The AI must never create an event that overlaps with any existing event across all connected calendars. This is a hard constraint in the booking logic, not just a preference.

### Calendar Read/Write Split

- **Read**: All calendars in `read_calendar_ids` (to understand total availability)
- **Write**: Only the calendar specified in `write_calendar_id`

---

## Data Model (JSON)

All state is stored in a single JSON file (e.g. `data/state.json`).

```json
{
  "user": {
    "user_id": "joe",
    "name": "Joe",
    "timezone": "Europe/London",
    "conversation_phase": "onboarding_goal",
    "last_conversation_date": null,
    "write_calendar_id": "personal@gmail.com",
    "read_calendar_ids": ["personal@gmail.com", "work@company.com"]
  },
  "goal": {
    "goal_id": "goal_001",
    "user_id": "joe",
    "description": "Get stronger and build a regular exercise habit",
    "goal_type": "fitness",
    "fitness_level": "beginner",
    "preferences": {
      "likes": ["bodyweight exercises", "swimming"],
      "dislikes": ["running", "gym machines"],
      "constraints": ["no gym membership", "bad left knee"],
      "equipment": ["resistance bands", "pull-up bar"]
    },
    "weekly_time_commitment_minutes": 150,
    "created_at": "2026-02-06T10:00:00Z",
    "status": "active"
  },
  "schedule_context": {
    "user_id": "joe",
    "sleep_window": { "start": "23:00", "end": "07:30" },
    "routine_blocks": [
      { "label": "school run", "days": ["monday", "tuesday", "wednesday", "thursday", "friday"], "start": "08:00", "end": "09:00" },
      { "label": "dinner / family time", "days": ["monday", "tuesday", "wednesday", "thursday", "friday"], "start": "18:00", "end": "19:30" }
    ],
    "preferred_exercise_times": ["weekday_evenings", "saturday_morning"],
    "excluded_times": ["before 7am", "friday evenings"]
  },
  "planned_sessions": [
    {
      "session_id": "sess_001",
      "goal_id": "goal_001",
      "gcal_event_id": "abc123xyz",
      "title": "Upper body workout",
      "session_type": "strength",
      "duration_minutes": 30,
      "scheduled_date": "2026-02-10",
      "scheduled_start": "19:30",
      "status": "upcoming",
      "user_feedback": null
    }
  ],
  "conversation_logs": [
    {
      "log_id": "log_001",
      "user_id": "joe",
      "conversation_date": "2026-02-06T10:00:00Z",
      "phase_at_start": "onboarding_goal",
      "phase_at_end": "onboarding_schedule",
      "summary": "User wants to get stronger. Beginner level. Likes bodyweight and swimming. Bad left knee, no gym. Has resistance bands and pull-up bar at home.",
      "adaptations_made": []
    }
  ]
}
```

---

## Conversation Flows

### Flow 1: Onboarding - Goal (Phase: `onboarding_goal`)

**Trigger**: First time user opens the app (no existing state).

**AI behaviour**:
1. Welcome the user warmly. Explain what Habits does in one or two sentences.
2. Ask what fitness goal they want to work towards. Let them describe it in their own words.
3. Explore:
   - Current fitness level and experience
   - Types of exercise they enjoy and dislike
   - Constraints: injuries, equipment access, gym membership, budget
   - What has worked or failed for them before
4. Reflect back understanding and confirm the goal.
5. Transition: "Great, now let's talk about your schedule so I can find the right times for you."
6. Update `conversation_phase` to `onboarding_schedule`.

**Data written**: `user` (basic fields), `goal`, first `conversation_log`.

### Flow 2: Onboarding - Schedule (Phase: `onboarding_schedule`)

**Trigger**: Phase is `onboarding_schedule` (either continuing from Flow 1 or resuming).

**AI behaviour**:
1. Ask about their general daily routine:
   - What time do they sleep and wake up?
   - Work hours?
   - Commute?
   - Regular commitments NOT in the calendar (childcare, meals, recurring social things)
2. Actively probe for hidden commitments: "Are there regular things in your evenings or weekends that wouldn't show up in your calendar?"
3. Ask about preferred times for exercise: morning vs evening, weekdays vs weekends.
4. Ask how much time per week feels realistic. Offer anchors: "Most people find 2-3 sessions of 30-60 minutes works well. Does that sound about right, or more or less?"
5. Ask which calendar they want sessions added to: personal, work, or both.
6. Read the user's calendars for the next 4 weeks.
7. Summarise what availability looks like: "You seem fairly free on weekday evenings after 7:30, and Saturday mornings look open."
8. Transition to plan generation.
9. Update `conversation_phase` to `plan_proposed`.

**Data written**: `schedule_context`, updated `user` (calendar IDs), `conversation_log`.

### Flow 3: Plan Proposal (Phase: `plan_proposed`)

**Trigger**: AI has gathered all context and is ready to create the plan.

**AI behaviour**:
1. Using the goal, preferences, schedule context, and calendar availability, generate a 4-week plan of specific sessions.
2. Each session should have:
   - A descriptive title (e.g. "Upper body workout", "30min swim", "Yoga / flexibility")
   - A session type (strength, cardio, flexibility, mixed)
   - A duration (15, 30, 45, or 60 minutes)
   - A specific date and start time
3. Respect all constraints:
   - No overlap with existing calendar events (across all read calendars)
   - No overlap with routine blocks or sleep window
   - Only during preferred times where possible
   - Total weekly time within the user's stated commitment
   - Session types aligned with likes/dislikes and constraints
4. Book all sessions into the designated calendar via Google Calendar API.
5. Store each session in `planned_sessions` with the returned `gcal_event_id`.
6. Tell the user: "I've added [X] sessions to your calendar over the next 4 weeks. Take a look and come back to me when you're ready - tell me if anything needs changing."
7. End the conversation. Phase remains `plan_proposed`.

**Data written**: `planned_sessions`, `conversation_log`.

**Plan generation logic guidelines**:
- Start conservatively. 2-3 sessions per week for beginners.
- Vary session types across the week (don't do strength every day).
- Leave rest days between intense sessions.
- For beginners, prefer shorter sessions (30 min) initially.
- Include warm-up/cool-down in the duration (don't add extra time).

### Flow 4: Plan Feedback (Phase: `plan_proposed`)

**Trigger**: User returns and indicates they've reviewed the calendar.

**AI behaviour**:
1. Recognise the user is in `plan_proposed` phase.
2. Ask: "Have you had a chance to look at your calendar?"
3. If yes, capture feedback:
   - "Tuesday is too early" -> move the session
   - "That's too many sessions" -> remove some
   - "Can you add a Saturday session?" -> add one
   - "Friday doesn't work" -> reschedule
4. For each change:
   - Check calendar availability before rebooking
   - Update the Google Calendar event (move, delete, or create new)
   - Update the corresponding `planned_session` record
5. Confirm each change verbally.
6. Ask: "Does the plan look good now, or do you want more changes?"
7. Loop until the user confirms they're happy.
8. Update `conversation_phase` to `plan_confirmed`.

**Data written**: Updated `planned_sessions`, `conversation_log`.

### Flow 5: Check-in (Phase: `plan_confirmed` or `check_in`)

**Trigger**: User returns after plan is confirmed. This is the ongoing conversation type.

**AI behaviour**:
1. On start, automatically:
   - Get the current date and time
   - Get the last conversation date
   - Query Google Calendar for all tagged Habits events since last conversation
   - Cross-reference with `planned_sessions`:
     - If a session's `gcal_event_id` no longer exists in the calendar -> set status to `deleted_by_user`
     - Sessions in the past with status still `upcoming` -> need to ask about
2. Summarise: "It's been [X] days since we last spoke. You had [N] sessions planned. How did they go?"
3. For each past session, ask if they completed it, skipped it, or partially did it. Capture brief feedback.
4. Listen for signals:
   - Too hard / too easy
   - Enjoying or hating specific session types
   - Schedule not working
   - Motivation dipping
   - Life changes affecting availability
5. If adaptation is needed:
   - Propose specific changes: "Want me to swap Thursday runs for swimming?"
   - Re-check calendar availability before making changes
   - Update events and session records
6. Look ahead to the coming week:
   - Preview upcoming sessions
   - Check for new calendar conflicts that appeared since the plan was made
   - Flag clashes: "Looks like something's been added on Wednesday evening - want me to move that session?"
7. If the 4-week plan is nearing its end, propose a new 4-week cycle.
8. Update `conversation_phase` to `check_in` (if not already).

**Data written**: Updated `planned_sessions` (statuses, feedback), `conversation_log` with summary and adaptations.

**Tone guidelines for check-ins**:
- Be encouraging but not patronising. No "Great job, champ!" energy.
- If sessions were missed, don't guilt. Ask what got in the way and adapt.
- If the user is struggling, suggest reducing rather than pushing harder.
- If the user deleted events manually, acknowledge it: "I noticed you removed the Wednesday session - was that one not working for you?"

---

## Google Calendar Integration

### Authentication

MVP uses hardcoded OAuth credentials stored in `.env`:

```
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REFRESH_TOKEN=...
```

### Required API Operations

| Operation | When Used |
|---|---|
| List calendars | Onboarding (to let user choose which to read/write) |
| List events (date range) | Schedule discovery, plan generation, check-ins |
| Create event | Plan generation |
| Update event (time, title) | Plan feedback, check-in adaptations |
| Delete event | Plan feedback (removing sessions) |
| Get event by ID | Check-ins (verifying events still exist) |

### Event Format

```json
{
  "summary": "🏋️ Habits: Upper body workout",
  "description": "Fitness session planned by Habits AI agent.\n\nSession type: strength\nDuration: 30 minutes\n\n[habits-agent]",
  "start": {
    "dateTime": "2026-02-10T19:30:00",
    "timeZone": "Europe/London"
  },
  "end": {
    "dateTime": "2026-02-10T20:00:00",
    "timeZone": "Europe/London"
  },
  "reminders": {
    "useDefault": false,
    "overrides": [
      { "method": "popup", "minutes": 15 }
    ]
  }
}
```

---

## Voice Agent System Prompt (Template)

The LiveKit voice agent should receive a system prompt that includes the current state. Here's the structure:

```
You are Habits, a friendly and practical AI fitness planning assistant. You help people build realistic exercise habits by understanding their goals, schedule, and preferences, then booking sessions into their Google Calendar.

## Current State
- User: {user.name}
- Timezone: {user.timezone}
- Current date/time: {current_datetime}
- Last conversation: {user.last_conversation_date}
- Phase: {user.conversation_phase}

## Goal
{goal object, if exists}

## Schedule Context
{schedule_context object, if exists}

## Recent Conversation History
{last 3 conversation_log summaries}

## Upcoming Sessions
{planned_sessions with status "upcoming" for next 2 weeks}

## Your Behaviour

Based on the current phase, follow the appropriate conversation flow:
- onboarding_goal: Gather the user's fitness goal, experience, preferences, and constraints.
- onboarding_schedule: Gather their routine, availability, preferred exercise times, and calendar preference.
- plan_proposed: Check if they've reviewed the calendar. Capture feedback and adjust.
- plan_confirmed / check_in: Review what happened since last conversation. Adapt the plan if needed.

## Rules
- Never book a session that overlaps with an existing calendar event.
- Always check calendar availability before creating or moving events.
- Keep sessions realistic for the user's fitness level.
- Be warm but not patronising. Be direct but not blunt.
- If unsure about anything, ask the user rather than guessing.
- When the conversation ends, always tell the user what happens next.
```

---

## Tool Functions

The voice agent needs access to these tool functions (called via LiveKit function calling):

### `get_calendar_events(calendar_id, start_date, end_date)`
Returns all events from the specified calendar within the date range.

### `get_all_availability(start_date, end_date)`
Reads all `read_calendar_ids`, combines with `routine_blocks` and `sleep_window`, returns available time slots.

### `create_calendar_event(calendar_id, title, description, start_datetime, end_datetime)`
Creates an event and returns the `gcal_event_id`.

### `update_calendar_event(calendar_id, event_id, updates)`
Updates an existing event (time, title, etc).

### `delete_calendar_event(calendar_id, event_id)`
Deletes an event.

### `get_habits_events_since(date)`
Queries the write calendar for all events with the `[habits-agent]` tag since the given date. Returns list with event IDs, times, and titles.

### `save_state(state_updates)`
Writes updated state to the JSON file.

### `get_state()`
Reads current state from the JSON file.

---

## File Structure

```
habits/
├── .env                          # Google Calendar credentials, OpenAI API key, LiveKit config
├── data/
│   └── state.json                # Persistent state (user, goal, sessions, logs)
├── agent.py                      # Main LiveKit voice agent entry point
├── prompts/
│   └── system_prompt.py          # System prompt builder (injects current state)
├── tools/
│   ├── calendar.py               # Google Calendar API wrapper
│   ├── availability.py           # Availability calculation logic
│   ├── planner.py                # Session planning / scheduling logic
│   └── state.py                  # JSON state read/write
├── models/
│   └── schemas.py                # Data model definitions (dataclasses or Pydantic)
└── requirements.txt
```

---

## Implementation Order (Suggested)

1. **State management**: JSON read/write, data models
2. **Google Calendar integration**: Auth, list events, create/update/delete events
3. **Availability engine**: Combine calendar events + routine blocks + sleep window to calculate free slots
4. **Session planner**: Generate a 4-week plan given goal, preferences, and availability
5. **LiveKit voice agent**: Connect to OpenAI Realtime API, wire up system prompt and tool functions
6. **Conversation flow logic**: Phase detection, state transitions, conversation log writing
7. **Check-in logic**: Compare planned vs actual, detect deleted events, adaptation proposals

---

## Open Questions / Future Considerations

- **Plan progression**: How does the plan evolve over multiple 4-week cycles? (Start simple: just replan with updated preferences.)
- **Multiple goal types**: The data model supports this via `goal_type` but the planning logic is fitness-only for now.
- **Multi-user**: Requires adding auth flow and per-user state files. The data model is ready for this.
- **Visual interface**: Currently voice-only with calendar as the visual layer. A web UI showing plan overview and progress could come later.
- **Pause/resume**: User should be able to say "pause my plan for 2 weeks" and have all upcoming events removed, then replanned when they resume.
