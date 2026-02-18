# Agent Rules — {project_name}

Rules for AI coding agents working in this repository. This is the single source of truth — tool-specific config (`.cursor/rules/`, `CLAUDE.md`) should point here, not duplicate content.

## Workflow

1. Read relevant code and docs first.
2. Produce a short plan (bullets) and list files you will touch.
3. Wait for approval before making changes.
4. Execute one step at a time. After each step:
   - State what changed
   - Why it changed
   - What to check next

## Safety

- Do not run terminal commands unless you ask first and the user approves.
- If a command is necessary, propose the exact command and the reason.

## Simplicity

- Match existing patterns. Don't introduce new architecture, folders, or libraries unless asked.
- Prefer reuse over creation — check for existing components, utilities, and helpers first.
- Keep functions small and readable. Prefer better naming over scattered comments.
- Avoid over-engineering and speculative future-proofing.

## Git Workflow

- Never push directly to main. Always create a feature branch and open a PR.
- Branch naming: `feature/feature-name`, `fix/bug-name`, `docs/doc-name`.
- When committing: create a new branch first, commit, push, then open a PR using `gh pr create`.
- Wait for PR approval before merging unless told otherwise.

### Incremental Commits

Commit at logical checkpoints — don't batch everything into one large commit. Good commit points:

- A single feature or fix is complete and working
- A logical unit of work is done (e.g., data model changes before the code that uses them)
- Before switching to a different type of change (e.g., backend to frontend)
- When changes are self-contained and testable

Before committing, check in: "This would be a good time to commit because [reason]. Ready to commit?"

## Task Logging

Maintain `/docs/TASK_LOG.md` as a running record for every non-trivial task:

- Date
- Goal
- Plan
- Decisions made
- Files changed
- Follow-ups / TODOs

If context is missing or you are unsure about something, say so and point to which doc would resolve it.

## Testing

- Do not add or run tests unless asked.
- If changes create risk, propose what tests or checks the user should run.

## Self-Check

At the start of each session, before beginning any task:

1. **Verify rules setup is current.** Search the web for the latest best practice on AI agent rules for the tools this project uses (include the current year). If the approach has changed, flag it and recommend migrating.
2. **Check for stale docs.** If `docs/TASK_LOG.md` or `docs/CHANGELOG.md` exist, skim recent entries to understand where the project left off.
3. **Check for running processes.** Before starting dev servers or long-running commands, check if they're already running.
4. **Flag drift.** If you notice code patterns that contradict these rules, flag it rather than silently following the drift.
