# Project Overview

## What this app is

A voice-first AI agent that helps users set fitness goals, build realistic exercise plans, and book sessions directly into their Google Calendar. The agent guides users through goal setting, schedule discovery, plan generation, and ongoing check-ins — all via natural voice conversation.

## Who uses it

- **User (single-user MVP)** — someone who wants to build a regular exercise habit. They speak to the agent via a web interface and review the resulting calendar events.

## How it works (high level)

1. The user connects via the web frontend and starts a voice conversation.
2. **Onboarding — Goal:** The agent gathers their fitness goal, experience level, preferences, likes/dislikes, and constraints (injuries, equipment, etc.).
3. **Onboarding — Schedule:** The agent learns their daily routine, sleep schedule, regular commitments not in the calendar, and preferred exercise times.
4. **Plan generation:** The agent reads their Google Calendar for availability, generates a 4-week plan of specific sessions, and books them all into the calendar.
5. **Feedback:** The user reviews the calendar and tells the agent what to change. Sessions are moved, added, or removed.
6. **Check-ins:** The user returns periodically. The agent reviews what happened since last time (completed, skipped, deleted sessions), gathers feedback, and adapts the plan.

## Tech stack

- **Backend**: Python 3.12+ with LiveKit Agents framework, OpenAI Realtime API
- **Frontend**: Next.js 15, React 19, TypeScript, TailwindCSS, Radix UI
- **Real-time voice**: LiveKit client/server SDKs
- **AI model**: OpenAI Realtime (gpt-4o-realtime-preview)
- **Calendar**: Google Calendar API (OAuth2)
- **State**: JSON file (`agent/data/state.json`)
- **Package managers**: Python (uv), Node (pnpm)

## External integrations

- **LiveKit** — real-time voice communication between user and agent
- **OpenAI Realtime API** — powers the voice agent's conversational ability
- **Google Calendar API** — reads availability from multiple calendars, writes sessions to one

## How to run locally

1. `cd agent && uv sync` — install Python dependencies
2. `cd frontend && pnpm install` — install frontend dependencies
3. Copy `.env.example` files and fill in credentials
4. `cd agent && python agent.py dev` — start the agent
5. `cd frontend && pnpm dev` — start the frontend
6. Open `http://localhost:3000`

## Key directories

- `agent/` — Python backend, voice agent logic, tools, state management
- `agent/models/` — Pydantic data models
- `agent/tools/` — Calendar API, availability engine, planner, state management
- `agent/prompts/` — Dynamic system prompt builder
- `frontend/` — Next.js web frontend with voice UI
- `docs/ai/` — AI-readable project documentation

## Conventions

- Building incrementally — each feature is added and understood before moving to the next
- This is a learning project — code should be clear and well-commented where the logic isn't obvious
- State is a single JSON file — no database
- Single-user MVP — no auth, no multi-tenancy
