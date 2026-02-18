# User Stories

## Personas

### Joe (Primary User)

- **Who**: Someone who wants to build a regular exercise habit but struggles with consistency
- **Goals**: Exercise regularly, have a realistic plan that fits their schedule, not forget sessions
- **Pain points**: Plans fall apart when life gets busy, forgets to work out, feels guilty about missed sessions
- **Tech comfort**: High

---

## Stories

### Goal Setting

#### US-001: Set a fitness goal through conversation

**As a** user, **I want to** tell the agent about my fitness goals in my own words **so that** it understands what I'm trying to achieve.

**Acceptance criteria:**
- [ ] Agent asks about my goal, fitness level, and preferences
- [ ] Agent captures likes, dislikes, and constraints (injuries, equipment)
- [ ] Agent reflects back understanding and confirms before moving on

#### US-002: Provide my phone number for reminders

**As a** user, **I want to** give the agent my phone number **so that** it can call me before sessions as a reminder.

**Acceptance criteria:**
- [ ] Agent asks for phone number during onboarding
- [ ] I can decline without blocking the rest of the flow
- [ ] Phone number is stored securely in my profile

### Schedule Discovery

#### US-003: Describe my daily routine

**As a** user, **I want to** tell the agent about my schedule (work, sleep, commitments) **so that** it only books sessions when I'm genuinely free.

**Acceptance criteria:**
- [ ] Agent asks about sleep/wake times, work hours, regular commitments
- [ ] Agent probes for things not in my calendar (school run, meals, etc.)
- [ ] Agent confirms understanding before generating a plan

#### US-004: Set preferred exercise times

**As a** user, **I want to** specify when I prefer to exercise **so that** sessions are booked at times that feel natural.

**Acceptance criteria:**
- [ ] Agent asks about preferred times (weekday evenings, weekend mornings, etc.)
- [ ] Agent asks how much weekly time feels realistic
- [ ] Preferences are respected in plan generation

### Plan Generation

#### US-005: Get a personalised 4-week plan

**As a** user, **I want to** have the agent generate a plan of sessions booked directly into my Google Calendar **so that** I don't have to plan anything myself.

**Acceptance criteria:**
- [ ] Plan respects my calendar availability (no double-booking)
- [ ] Plan respects my routine blocks and sleep window
- [ ] Sessions vary by type (strength, cardio, flexibility)
- [ ] Each session has a brief workout plan (exercise names)
- [ ] Conservative for beginners (2-3 sessions/week, 30 min)

#### US-006: Review and adjust the plan

**As a** user, **I want to** review the booked sessions and request changes **so that** the plan works for my actual life.

**Acceptance criteria:**
- [ ] Agent asks if I've reviewed the calendar
- [ ] I can request moves, deletions, or additions
- [ ] Agent checks availability before rebooking
- [ ] Loop continues until I confirm I'm happy

### Phone Reminders

#### US-007: Receive a reminder call before each session

**As a** user, **I want to** get a phone call 15 minutes before each session **so that** I don't forget to exercise.

**Acceptance criteria:**
- [ ] Call arrives ~15 minutes before the session
- [ ] Agent introduces itself and mentions the upcoming session
- [ ] Call is brief (under 2 minutes unless rescheduling)

#### US-008: Confirm, reschedule, or skip during a reminder call

**As a** user, **I want to** tell the reminder agent whether I'm ready, need to reschedule, or want to skip **so that** my plan stays realistic.

**Acceptance criteria:**
- [ ] If I confirm: agent encourages and ends call
- [ ] If I reschedule: agent checks availability, moves the event, confirms new time
- [ ] If I skip: agent marks it, no guilt, call ends
- [ ] Outcome is recorded for check-in review

#### US-009: Not be harassed by retry calls

**As a** user, **I want** the system to only call once per session **so that** I don't feel pressured.

**Acceptance criteria:**
- [ ] Maximum one call attempt per session
- [ ] No answer is logged as `no_answer` — no retry
- [ ] Missed calls are discussed at next check-in, not re-called

### Check-ins

#### US-010: Review progress in a check-in conversation

**As a** user, **I want to** return and discuss how my sessions went **so that** the plan adapts to reality.

**Acceptance criteria:**
- [ ] Agent detects which sessions happened since last conversation
- [ ] Agent asks about each past session (completed, skipped, partial)
- [ ] Agent incorporates reminder call outcomes into the review
- [ ] Agent proposes adaptations if patterns emerge

#### US-011: Have the plan adapt based on feedback

**As a** user, **I want to** give feedback (too hard, schedule changed, lost motivation) **so that** the plan evolves with me.

**Acceptance criteria:**
- [ ] Agent can modify session types, frequency, or duration
- [ ] Agent checks availability before making changes
- [ ] Agent previews upcoming week and flags conflicts
- [ ] If plan is ending, agent offers to generate the next 4-week cycle
