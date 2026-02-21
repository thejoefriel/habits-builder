# Architecture

## System overview

```
┌─────────────────┐     LiveKit      ┌──────────────────┐
│   Frontend       │◄───(voice +────►│   Python Agent    │
│   (Next.js)      │    text)         │   (LiveKit Agent) │
└─────────────────┘                  └──────┬───────────┘
                                            │
                             ┌──────────────┼──────────────┐
                             │              │              │
                      ┌─────▼─────┐  ┌─────▼──────┐ ┌─────▼──────┐
                      │  OpenAI    │  │  Google    │ │  Twilio    │
                      │  Realtime  │  │  Calendar  │ │  SIP       │
                      │  API       │  │  API       │ │  Trunk     │
                      └───────────┘  └────────────┘ └─────┬──────┘
                                                           │
┌─────────────────┐     LiveKit SIP     ┌─────────────────▼────┐
│   Phone Call     │◄───(outbound)─────►│   Reminder Agent     │
│   (User's Phone) │                     │   (LiveKit Agent)    │
└─────────────────┘                     └─────────┬────────────┘
                                                  │
                                          ┌───────▼─────┐
                                          │ PostgreSQL  │
                                          │ (JSONB)     │
                                          │             │
                                          └─────────────┘
```

## Components

### Backend — `agent/`

- **agent.py** — Main entry point. Configures the LiveKit voice agent with:
  - Dynamic system prompt (built from current state, injecting goal/schedule/sessions/phase)
  - 14 tool functions for calendar operations, state management, plan generation, and check-ins
  - Phase-aware opening messages (greet differently based on onboarding vs check-in)
- **reminder_scheduler.py** — Background process that checks for upcoming sessions every 5 minutes and triggers phone call reminders
- **reminder_agent.py** — Lightweight voice agent for phone call reminders with limited tools
- **models/schemas.py** — Pydantic models for all state: User, Goal, ScheduleContext, PlannedSession, ConversationLog, AppState
- **tools/state.py** — PostgreSQL JSONB read/write for persistent state
- **tools/calendar.py** — Google Calendar API wrapper (list, create, update, delete events; Habits tagging)
- **tools/availability.py** — Availability engine: merges calendar events + routine blocks + sleep window → free slots
- **tools/planner.py** — Session planner: generates 4-week plans based on goal, preferences, and availability
- **tools/sip.py** — LiveKit SIP integration for outbound phone calls
- **prompts/system_prompt.py** — Builds the full system prompt with current state injected
- **prompts/reminder_prompt.py** — Builds reminder-specific system prompt with session context

### Frontend — `frontend/`

- **Next.js app** — Web interface where the user connects to the agent
- **LiveKit client SDK** — Handles the voice connection from the browser
- **API route** — `/api/connection-details` generates LiveKit tokens

### Phone Reminder System

- **Twilio SIP trunk** — Routes outbound calls from LiveKit to the phone network
- **LiveKit SIP integration** — Bridges phone calls to LiveKit rooms where reminder agent operates
- **Reminder scheduler** — Monitors upcoming sessions and triggers calls 15 minutes before start time

## Data flow

### Onboarding
1. User opens frontend → connects to LiveKit room
2. Agent joins room → greets user, starts goal gathering
3. Conversational exchange via voice (OpenAI Realtime handles STT + LLM + TTS)
4. Agent saves goal via `save_goal` tool → persisted to PostgreSQL
5. Agent asks for phone number for reminders
6. Agent transitions to schedule phase → gathers routine, sleep, preferences
7. Agent saves schedule via `save_schedule_context` tool
8. Agent reads Google Calendar via `get_calendar_availability` tool
9. Agent calls `generate_and_book_plan` → books sessions into calendar
10. State updated to `plan_proposed`

### Phone Reminders
1. Reminder scheduler checks for upcoming sessions every 5 minutes
2. For sessions starting within 15 minutes: verifies calendar event exists, user not in active session
3. Initiates outbound SIP call via LiveKit to user's phone
4. Reminder agent joins the call when user picks up
5. Brief conversation: confirm ready / reschedule / skip
6. Agent updates session status and calendar as needed
7. Call ends, reminder marked as sent

### Check-ins
1. User returns → agent detects `plan_confirmed` or `check_in` phase
2. Agent calls `check_for_deleted_events` → detects manually removed sessions
3. Agent calls `get_sessions_since_last_conversation` → reviews what happened
4. Conversational review of each session (completed/skipped/partial/no_answer)
5. Agent adapts plan if needed (move/delete/create sessions)
6. Agent previews upcoming week, flags new conflicts

## Conversation phases

| Phase | Description |
|---|---|
| `onboarding_goal` | First conversation. Gathering fitness goal, experience, preferences, and phone number. |
| `onboarding_schedule` | Gathering routine, preferred times, calendar preferences. |
| `plan_proposed` | Sessions booked. Waiting for user review and feedback. |
| `plan_confirmed` | User approved the plan. Sessions are active. Phone reminders enabled. |
| `check_in` | Ongoing. Reviewing progress and adapting. |

## Event tagging

All calendar events created by the agent use:
- Title prefix: `🏋️ Habits: `
- Description tag: `[habits-agent]`

This allows reliable filtering of agent-created events vs the user's other calendar entries.

## Phone reminder edge cases

- **No answer**: Timeout after 30 seconds, mark as `no_answer`
- **Voicemail**: Twilio AMD detection, leave short message, mark as `voicemail`
- **User in main session**: Skip call entirely to avoid interruption
- **Calendar event deleted**: Skip call, update session status
- **Call failure**: Log error, mark as `error`, do not retry

## Database

### PostgreSQL JSONB State Storage

- Single table: `app_state` with id=1 row containing JSONB data
- Auto-initialization: table created on first state access
- Module-level connection pooling for efficiency
- Pydantic model validation on read/write
- One-time migration script (`scripts/migrate_json_to_pg.py`) for JSON file → PostgreSQL

### State Schema

```sql
CREATE TABLE app_state (
    id INTEGER PRIMARY KEY DEFAULT 1,
    data JSONB NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW()
);
```

## Hard rules

- **No double-booking**: The agent must never create an event that overlaps with any existing event across all connected calendars.
- **Read/write split**: Read from all calendars in `read_calendar_ids`, write only to `write_calendar_id`.
- **One reminder per session**: Never retry failed reminder calls to avoid harassment.