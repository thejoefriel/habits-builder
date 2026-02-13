# Task Log

## Build Plan

Following the implementation order from the spec (`habits-spec.md`):

1. [x] State management: JSON read/write, data models
2. [x] Google Calendar integration: Auth, list events, create/update/delete events
3. [x] Availability engine: Combine calendar events + routine blocks + sleep window
4. [x] Session planner: Generate a 4-week plan given goal, preferences, and availability
5. [x] LiveKit voice agent: Connect to OpenAI Realtime API, wire up system prompt and tool functions
6. [x] Conversation flow logic: Phase detection, state transitions, conversation log writing
7. [x] Check-in logic: Compare planned vs actual, detect deleted events, adaptation proposals
8. [x] Install dependencies and test onboarding flow
9. [x] End-to-end test with Google Calendar
10. [x] Test plan generation (booking sessions into calendar)
11. [x] Test plan feedback flow (moving/deleting sessions)
12. [x] Test check-in flow (returning after sessions)

## Completed Tasks

### Initial scaffolding — 2026-02-06

- **Goal:** Build the full agent from the spec in one pass
- **Plan:** Follow the spec's implementation order, reusing patterns from the existing livekit-voice-agent project
- **Decisions:**
  - Used uv + pyproject.toml (matching existing project) instead of pip + requirements.txt
  - Used Pydantic for data models (validation, serialization)
  - Used gpt-4o-realtime-preview (not gpt-realtime-mini) for better tool-calling ability
  - Reused same LiveKit Cloud instance and OpenAI API key from existing project
  - Copied frontend from livekit-voice-agent and rebranded (green accent, disabled video/screenshare)
  - Google Calendar credentials obtained via OAuth Playground
- **Files created:**
  - `agent/pyproject.toml`
  - `agent/models/schemas.py` — Pydantic data models
  - `agent/tools/state.py` — JSON state management
  - `agent/tools/calendar.py` — Google Calendar API wrapper
  - `agent/tools/availability.py` — Availability calculation engine
  - `agent/tools/planner.py` — Session planning logic
  - `agent/prompts/system_prompt.py` — Dynamic system prompt builder
  - `agent/agent.py` — Main LiveKit voice agent
  - `agent/.env.local` — Credentials (LiveKit, OpenAI, Google Calendar)
  - `agent/.env.example` — Template for credentials
  - `agent/data/state.json` — Initial empty state
  - `frontend/` — Copied and rebranded from livekit-voice-agent
  - `frontend/.env.local` — LiveKit credentials
  - `.gitignore`
  - `.cursorrules`
  - `docs/ai/` — Full AI documentation suite
- **Follow-ups:**
  - Install dependencies (`uv sync`, `pnpm install`)
  - Test onboarding flow (goal gathering works without Google Calendar)
  - Test full flow with Google Calendar integration

### First run bugs — 2026-02-06

- **Goal:** Get the agent working end-to-end through onboarding
- **Bugs found and fixed:**
  1. **Agent speaking French** — OpenAI Realtime was defaulting to French. Fixed by adding `InputAudioTranscription(model="whisper-1", language="en")` to the RealtimeModel config and an explicit English instruction in the system prompt.
  2. **Calendar API 400 errors** — Google Calendar API requires RFC3339 datetime format with timezone offset. `timeMin`/`timeMax` were missing the `Z` suffix. Fixed in `tools/calendar.py`.
  3. **All-day events blocking entire days** — Events like "Skincare (AM)" were treated as blocking the whole day, resulting in "No availability". Fixed in `tools/availability.py` to skip all-day events since they're typically reminders, not real time blocks.
- **Logging added:** Structured file + console logging with tool call tracing (`data/logs/habits_YYYY-MM-DD.log`). Every tool invocation logs function name, arguments, and result.
- **Files changed:**
  - `agent/agent.py` — logging setup, `@_log_tool` decorator, `InputAudioTranscription` config
  - `agent/tools/calendar.py` — RFC3339 `Z` suffix on timeMin/timeMax
  - `agent/tools/availability.py` — skip all-day events instead of blocking
  - `agent/prompts/system_prompt.py` — explicit English language instruction
  - `.gitignore` — added `agent/data/logs/`
- **Follow-ups:**
  - Test plan generation (does it book sessions correctly?)
  - Test plan feedback (moving/removing sessions)
  - Test check-in flow

### Exercise workout plans — 2026-02-06

- **Goal:** Each calendar event should include a brief workout plan (exercise names) tailored to the session type, user equipment, and constraints
- **Approach:** Hybrid — curated exercise dataset (90 exercises) as reference, agent assembles plans from it
- **Decisions:**
  - Created `data/exercises.json` with 90 exercises across strength (38), cardio (16), flexibility (18), mixed (18)
  - Each exercise tagged with: equipment needed, difficulty, muscle groups, constraint tags (wrist_caution, knee_caution, wrist_friendly, knee_friendly)
  - Constraint filtering: exercises tagged `wrist_caution` excluded if user has wrist injury, etc.
  - Equipment filtering: bodyweight exercises always available, equipment exercises only if user has the gear
  - Planner auto-generates workout plans for each session via `_build_workout_plan()`
  - Agent has `get_exercise_suggestions` tool for manual session creation
  - System prompt instructs agent to include 4-6 exercises per session
- **Files created:**
  - `agent/data/exercises.json` — exercise dataset
  - `agent/tools/exercises.py` — loader and filter module
- **Files changed:**
  - `agent/agent.py` — added `get_exercise_suggestions` tool, imported exercises module
  - `agent/tools/planner.py` — added `_build_workout_plan()`, included in event descriptions
  - `agent/prompts/system_prompt.py` — added workout plan instructions
- **Follow-ups:**
  - Test that generated events include workout plans in calendar
  - Test agent uses `get_exercise_suggestions` when creating sessions manually
