# Common Components and Patterns

## UI library

- **Radix UI** — headless component primitives
- **TailwindCSS** — utility-first styling
- **shadcn/ui** — pre-built components built on Radix + Tailwind
- **LiveKit React Components** — voice UI components

## Key frontend components

- Voice connection controls (start/end call) — `components/agents-ui/`
- Audio visualisers (bar, grid, radial) — `components/agents-ui/`
- Chat transcript — `components/app/chat-transcript.tsx`
- Session view — `components/app/session-view.tsx`
- Welcome view — `components/app/welcome-view.tsx`

## Agent patterns

### System prompt
- Built dynamically from current state (`prompts/system_prompt.py`)
- Injects: user info, goal, schedule context, recent conversation history, upcoming sessions
- Phase-specific instructions tell the LLM what to do next

### Tool functions
- Defined as `@function_tool` methods on the `HabitsAgent` class
- Always reload state from disk before operating (`self._state = load_state()`)
- Always persist state after changes (`persist_state(self._state)`)
- Calendar tools check availability before creating/moving events

### State management
- Single JSON file: `agent/data/state.json`
- Read with `load_state()`, write with `save_state()`
- Pydantic models for validation (`models/schemas.py`)

## Reuse rules

- Before creating a new component, search for existing equivalents
- Prefer extending existing components over adding near-duplicates
- Use shadcn/ui patterns for any new UI elements
- Keep tool functions focused — one operation per tool
