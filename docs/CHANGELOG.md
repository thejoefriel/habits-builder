# Changelog

## [Unreleased]

- Migrate state from JSON file to PostgreSQL JSONB storage
- Add psycopg2-binary dependency and DATABASE_URL environment variable
- Include one-time migration script (scripts/migrate_json_to_pg.py) for existing state.json data
- Update documentation to reflect PostgreSQL requirement and setup instructions
- Simplified documentation structure: consolidated 9 docs → 7 docs by merging user-stories + user-journeys → user-flows.md and project-overview into README.md
- Updated documentation workflow to trigger on every PR merge (not just feature-spec changes) with infinite loop guards
- Rewrote doc update script to accept PR diffs as primary context with feature specs as optional input
- Renamed TASK_LOG.md to AI_LOG.md and made it optional
- Strengthened AGENTS.md with commit → PR → stop pattern and expanded self-check procedures
- Project scaffolded with full agent implementation
- Data models defined (Pydantic): User, Goal, ScheduleContext, PlannedSession, ConversationLog, AppState
- State management: JSON file read/write
- Google Calendar integration: list, create, update, delete events with Habits tagging
- Availability engine: merges calendar events + routine blocks + sleep window into free slots
- Session planner: generates 4-week plans based on goal, preferences, and availability
- Dynamic system prompt builder: injects current state and phase-specific instructions
- LiveKit voice agent with 14 tool functions for calendar, state, planning, and check-ins
- Frontend copied from livekit-voice-agent and rebranded for Habits
- Environment files configured with LiveKit, OpenAI, and Google Calendar credentials
- AI documentation created (docs/ai/)
- Fixed: Agent language forced to English via InputAudioTranscription config
- Fixed: Google Calendar API RFC3339 datetime format (added Z suffix)
- Fixed: All-day events no longer block entire days in availability calculation
- Added: Structured file logging with tool call tracing (data/logs/)
- Added: Exercise dataset (90 exercises) with constraint-aware filtering (data/exercises.json)
- Added: Workout plans included in calendar event descriptions (4-6 exercises per session)
- Added: get_exercise_suggestions tool for agent to query exercises by type/muscle/equipment