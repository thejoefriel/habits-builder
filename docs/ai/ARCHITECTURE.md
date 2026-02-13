# Architecture

## System overview

```
┌─────────────────┐     LiveKit      ┌──────────────────┐
│   Frontend       │◄───(voice +────►│   Python Agent    │
│   (Next.js)      │    text)         │   (LiveKit Agent) │
└─────────────────┘                  └──────┬───────────┘
                                            │
                                    ┌───────┼────────┐
                                    │       │        │
                              ┌─────▼─────┐ │  ┌─────▼──────┐
                              │  OpenAI    │ │  │  Google    │
                              │  Realtime  │ │  │  Calendar  │
                              │  API       │ │  │  API       │
                              └───────────┘ │  └────────────┘
                                      ┌─────▼─────┐
                                      │  JSON     │
                                      │  State    │
                                      │  File     │
                                      └───────────┘
```

## Components

### Backend — `agent/`

- **agent.py** — Main entry point. Configures the LiveKit voice agent with:
  - Dynamic system prompt (built from current state, injecting goal/schedule/sessions/phase)
  - 14 tool functions for calendar operations, state management, plan generation, and check-ins
  - Phase-aware opening messages (greet differently based on onboarding vs check-in)
- **models/schemas.py** — Pydantic models for all state: User, Goal, ScheduleContext, PlannedSession, ConversationLog, AppState
- **tools/state.py** — JSON file read/write for persistent state
- **tools/calendar.py** — Google Calendar API wrapper (list, create, update, delete events; Habits tagging)
- **tools/availability.py** — Availability engine: merges calendar events + routine blocks + sleep window → free slots
- **tools/planner.py** — Session planner: generates 4-week plans based on goal, preferences, and availability
- **prompts/system_prompt.py** — Builds the full system prompt with current state injected

### Frontend — `frontend/`

- **Next.js app** — Web interface where the user connects to the agent
- **LiveKit client SDK** — Handles the voice connection from the browser
- **API route** — `/api/connection-details` generates LiveKit tokens

## Data flow

### Onboarding
1. User opens frontend → connects to LiveKit room
2. Agent joins room → greets user, starts goal gathering
3. Conversational exchange via voice (OpenAI Realtime handles STT + LLM + TTS)
4. Agent saves goal via `save_goal` tool → persisted to state.json
5. Agent transitions to schedule phase → gathers routine, sleep, preferences
6. Agent saves schedule via `save_schedule_context` tool
7. Agent reads Google Calendar via `get_calendar_availability` tool
8. Agent calls `generate_and_book_plan` → books sessions into calendar
9. State updated to `plan_proposed`

### Check-ins
1. User returns → agent detects `plan_confirmed` or `check_in` phase
2. Agent calls `check_for_deleted_events` → detects manually removed sessions
3. Agent calls `get_sessions_since_last_conversation` → reviews what happened
4. Conversational review of each session (completed/skipped/partial)
5. Agent adapts plan if needed (move/delete/create sessions)
6. Agent previews upcoming week, flags new conflicts

## Conversation phases

| Phase | Description |
|---|---|
| `onboarding_goal` | First conversation. Gathering fitness goal, experience, preferences. |
| `onboarding_schedule` | Gathering routine, preferred times, calendar preferences. |
| `plan_proposed` | Sessions booked. Waiting for user review and feedback. |
| `plan_confirmed` | User approved the plan. Sessions are active. |
| `check_in` | Ongoing. Reviewing progress and adapting. |

## Event tagging

All calendar events created by the agent use:
- Title prefix: `🏋️ Habits: `
- Description tag: `[habits-agent]`

This allows reliable filtering of agent-created events vs the user's other calendar entries.

## Hard rules

- **No double-booking**: The agent must never create an event that overlaps with any existing event across all connected calendars.
- **Read/write split**: Read from all calendars in `read_calendar_ids`, write only to `write_calendar_id`.
