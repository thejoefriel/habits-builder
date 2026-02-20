# Agent Rules — {project_name}

Rules for AI coding agents working in this repository. This is the single source of truth — tool-specific config (`.cursor/rules/`, `CLAUDE.md`) should point here, not duplicate content.

## Workflow

Every task follows this sequence. Do not skip steps.

1. **Read** — Read `AGENTS.md` (this file), then relevant code and docs.
2. **Plan** — Produce a short plan (bullets), list files you will touch, and name the branch you will create.
3. **Wait** — Do not start making changes until the user approves the plan.
4. **Execute** — One step at a time. After each step, state: what changed, why, and what to check next.
5. **Commit** — When a logical unit of work is complete, ask: "Ready to commit?" Do not continue to the next unit of work.
6. **PR** — After committing, push and create a PR. Stop. Do not start the next task until the user says to.

**Hard rule:** Each logical unit of work (feature, fix, phase) = one branch = one PR. Never stack unrelated work on the same branch.

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
- One logical unit of work per branch. Never add unrelated changes to an existing branch.
- Wait for PR approval before merging unless told otherwise.

### Commit → PR → Stop

After completing a unit of work:

1. Ask: "This would be a good time to commit because [reason]. Ready to commit?"
2. Commit with a clear message.
3. Push the branch and create a PR using `gh pr create`.
4. **Stop.** Do not start the next task. Wait for the user to merge or give further instructions.

Starting the next piece of work before the current PR is merged breaks the review cycle and documentation automation triggers.

### What counts as one unit of work

- A single feature or fix, complete and working
- A logical grouping (e.g., data model changes before the code that uses them)
- A phase of a larger project (Phase 1, Phase 2, etc.)

If in doubt, it's a separate branch.

## AI Log

Maintain `/docs/AI_LOG.md` as an optional running record for non-trivial tasks:

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

At the start of every session, before doing anything else:

1. **Read this file.** Open and read `AGENTS.md`. Do not rely on memory from a previous session.
2. **Check git state.** Run `git status`, `gh pr list --state open`, and `git branch` to understand what's in progress.
3. **Check for stale docs.** If `docs/AI_LOG.md` or `docs/CHANGELOG.md` exist, skim recent entries to understand where the project left off.
4. **Check for running processes.** Before starting dev servers or long-running commands, check if they're already running.
5. **Verify rules setup is current.** Search the web for the latest best practice on AI agent rules for the tools this project uses (include the current year). If the approach has changed, flag it and recommend migrating.
6. **Flag drift.** If you notice code patterns that contradict these rules, flag it rather than silently following the drift.
