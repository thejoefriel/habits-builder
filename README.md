# Habits — AI Fitness Planner

A voice-first AI agent that helps users build exercise habits. You speak to it, it learns your goals and schedule, books sessions into your Google Calendar, and calls you before each one as a friendly reminder.

## How it works

1. **Onboarding** — The agent gathers your fitness goal, experience, preferences, constraints, and phone number via voice conversation
2. **Schedule discovery** — It learns your routine, sleep schedule, and preferred exercise times
3. **Plan generation** — It reads your Google Calendar, finds free slots, and books a 4-week plan of sessions
4. **Feedback** — You review the calendar and tell the agent what to change
5. **Phone reminders** — 15 minutes before each session, the system calls you to confirm, reschedule, or skip
6. **Check-ins** — You return periodically to review progress and adapt the plan

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12+, LiveKit Agents framework |
| Frontend | Next.js 15, React 19, TypeScript, TailwindCSS |
| Voice | LiveKit (client + server SDKs), OpenAI Realtime API |
| AI model | GPT-4o Realtime (voice + reasoning) |
| Calendar | Google Calendar API (OAuth2) |
| Phone calls | Twilio SIP trunk + LiveKit SIP integration |
| State | JSON file (no database) |

### External integrations

- **LiveKit** — real-time voice communication between user and agent, SIP calling
- **OpenAI Realtime API** — powers the voice agent's conversational ability
- **Google Calendar API** — reads availability from multiple calendars, writes sessions to one
- **Twilio** — phone service for outbound reminder calls

## Getting started

### Prerequisites

- Python 3.12+ with [uv](https://docs.astral.sh/uv/)
- Node.js 18+ with [pnpm](https://pnpm.io/)
- A [LiveKit Cloud](https://cloud.livekit.io/) account
- An [OpenAI](https://platform.openai.com/) API key
- A Google Cloud project with Calendar API enabled
- (Optional) A Twilio account with SIP trunking for phone reminders

### Environment variables

**Agent** (`agent/.env.local`):

```
LIVEKIT_API_KEY=<your_livekit_api_key>
LIVEKIT_API_SECRET=<your_livekit_api_secret>
LIVEKIT_URL=wss://<project>.livekit.cloud
OPENAI_API_KEY=<your_openai_api_key>
GOOGLE_CLIENT_ID=<your_google_client_id>
GOOGLE_CLIENT_SECRET=<your_google_client_secret>
GOOGLE_REFRESH_TOKEN=<your_google_refresh_token>
LIVEKIT_SIP_TRUNK_ID=<your_sip_trunk_id>
```

**Frontend** (`frontend/.env.local`):

```
LIVEKIT_API_KEY=<your_livekit_api_key>
LIVEKIT_API_SECRET=<your_livekit_api_secret>
LIVEKIT_URL=wss://<project>.livekit.cloud
```

Copy the `.env.example` files in each directory and fill in your credentials.

### Running locally

```bash
# Install dependencies
cd agent && uv sync
cd frontend && pnpm install

# Start the agent
cd agent && python agent.py dev

# Start the reminder scheduler (separate terminal)
cd agent && python reminder_scheduler.py

# Start the frontend
cd frontend && pnpm dev
```

Open [http://localhost:3000](http://localhost:3000) and click "Talk to Habits" to start a voice session.

## Project structure

```
agent/                  Python backend
├── agent.py            Main voice agent entry point
├── reminder_agent.py   Phone reminder agent
├── reminder_scheduler.py  Background scheduler for reminder calls
├── models/             Pydantic data models
├── tools/              Calendar, availability, planner, state, SIP
├── prompts/            Dynamic system prompt builders
├── data/               State file, exercise dataset, logs
│   └── exercises.json  90 exercises for workout plan generation
frontend/               Next.js web frontend
├── components/         Voice UI, chat transcript, session view
├── app/                Next.js app router
docs/                   Project documentation
├── technical-design.md Architecture and data flow
├── user-flows.md       Personas, user stories, and journeys
├── product-playbook.md Product description for agents and stakeholders
├── common-components.md Shared patterns and conventions
├── features/           Individual feature specs
├── CHANGELOG.md        What changed and when
├── AI_LOG.md           AI development log with decisions
scripts/                Automation scripts
├── update_docs.py      AI-powered doc updater
.github/
├── doc-schema.yml      Standard documentation schema
├── workflows/          GitHub Actions
```

## Documentation

| Document | What it covers |
|---|---|
| [Technical Design](docs/technical-design.md) | Architecture, components, data flow, integrations |
| [User Flows](docs/user-flows.md) | Personas, user stories, and end-to-end journeys |
| [Product Playbook](docs/product-playbook.md) | Features, roles, tone, FAQ |
| [Common Components](docs/common-components.md) | Shared patterns and conventions |
| [Feature Specs](docs/features/) | Individual feature designs |

## Conventions

- Building incrementally — each feature is added and understood before moving to the next
- This is a learning project — code should be clear and well-commented where the logic isn't obvious
- State is a single JSON file — no database
- Single-user MVP — no auth, no multi-tenancy

## License

Private — not open source.
