# User Flows

## Personas

### Joe (Primary User)

- **Who**: Someone who wants to build a regular exercise habit but struggles with consistency
- **Goals**: Exercise regularly, have a realistic plan that fits their schedule, not forget sessions
- **Pain points**: Plans fall apart when life gets busy, forgets to work out, feels guilty about missed sessions
- **Tech comfort**: High

---

## User Stories

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

---

## User Journeys

### Journey 1: First-time onboarding (goal + schedule + plan)

**Actor:** User (first time)

**Preconditions:**
- Agent is running with valid LiveKit, OpenAI, Google Calendar, Twilio credentials, and PostgreSQL
- User has a Google account with calendar access
- State is fresh (phase: `onboarding_goal`)

**Flow:**

1. User opens the web frontend
2. User clicks "Talk to Habits" to start a voice call
3. Agent greets the user warmly and explains what Habits does
4. Agent asks what fitness goal the user wants to work towards
5. User describes their goal in their own words
6. Agent explores: fitness level, exercise likes/dislikes, constraints, what's worked before
7. Agent asks for the user's phone number for reminder calls (user can decline)
8. Agent reflects back understanding and confirms the goal
9. Agent transitions: "Great, now let's talk about your schedule"
10. Agent asks about daily routine: sleep, work, commute, regular commitments
11. Agent probes for hidden commitments (things not in the calendar)
12. Agent asks about preferred exercise times and weekly time commitment
13. Agent asks which calendar to write to and which to read from
14. Agent reads the calendar for the next 4 weeks
15. Agent summarises availability: "You seem fairly free on weekday evenings after 7:30..."
16. Agent generates a 4-week plan and books all sessions into the calendar
17. Agent tells the user: "I've added X sessions to your calendar. I'll also call you 15 minutes before each one as a reminder. Take a look and come back when you're ready."
18. Call ends

**Postconditions:**
- State contains: user info (including phone number), goal, schedule context, planned sessions
- Calendar has sessions booked
- Phase is `plan_proposed`
- Reminder scheduler will begin monitoring for upcoming sessions

### Journey 2: Reviewing and adjusting the plan

**Actor:** User (returning after plan was booked)

**Preconditions:**
- Phase is `plan_proposed`
- Sessions exist in the calendar

**Flow:**

1. User starts a new voice call
2. Agent asks if they've had a chance to look at their calendar
3. User provides feedback: "Tuesday is too early", "Can you add a Saturday session?"
4. For each change, agent checks calendar availability
5. Agent moves/deletes/creates events as needed
6. Agent confirms each change verbally
7. Agent asks: "Does the plan look good now?"
8. User confirms they're happy
9. Agent updates phase to `plan_confirmed` and confirms reminder calls will start
10. Call ends

**Postconditions:**
- Calendar events updated
- Phase is `plan_confirmed`
- Phone reminders are now active for upcoming sessions

### Journey 3: Phone reminder call

**Actor:** User (receiving reminder call)

**Preconditions:**
- Phase is `plan_confirmed` or `check_in`
- A session is starting within 15 minutes
- User has provided a phone number
- Reminder hasn't been sent for this session yet

**Flow:**

1. Reminder scheduler detects upcoming session
2. System verifies calendar event still exists and user isn't in active app session
3. System initiates outbound call to user's phone
4. User's phone rings
5. **If user answers:**
   - Reminder agent: "Hi [name], this is Habits calling about your [session type] session in 15 minutes. Are you ready for it?"
   - **If "Yes/Ready":** Agent encourages and ends call
   - **If "Reschedule":** Agent checks availability, moves the event, confirms new time
   - **If "Skip":** Agent marks as skipped, no guilt, ends call
6. **If no answer:** Timeout after 30 seconds, mark as `no_answer`
7. **If voicemail:** Leave brief message or hang up, mark as `voicemail`
8. Session updated with reminder outcome

**Postconditions:**
- Session marked with `reminder_sent: true` and appropriate `reminder_outcome`
- Calendar updated if session was rescheduled
- User either proceeds with session or has made alternative arrangement

### Journey 4: Check-in (ongoing)

**Actor:** User (returning for regular check-in)

**Preconditions:**
- Phase is `plan_confirmed` or `check_in`
- Some sessions have passed since last conversation

**Flow:**

1. User starts a new voice call
2. Agent checks for deleted events and reviews sessions since last conversation
3. Agent summarises: "It's been X days since we last spoke. You had N sessions planned."
4. Agent asks how each past session went, including reminder call outcomes:
   - "I called you before Tuesday's run - you rescheduled it to Wednesday. How did that go?"
   - "I couldn't reach you before Friday's strength session. Did you end up doing it?"
5. Agent captures feedback and listens for signals (too hard, schedule issues, motivation, reminder preferences)
6. If adaptation needed, agent proposes changes: "Want me to swap Thursday runs for swimming?"
7. Agent makes changes (checking availability first)
8. Agent previews upcoming sessions and flags any new calendar conflicts
9. If reminder calls aren't working well, agent offers to adjust timing or approach
10. If the plan is nearing its end, agent offers to plan the next 4-week cycle
11. Call ends

**Postconditions:**
- Session statuses updated (completed, skipped, etc.)
- Plan adapted if needed
- Conversation log saved with reminder feedback
- Future reminder approach adjusted if requested

### Journey 5: Edge cases during reminder calls

**Actor:** User (various edge case scenarios)

#### Scenario A: Multiple sessions in reminder window

1. System detects two sessions starting within 15 minutes
2. Single call handles both: "Hi, you've got yoga at 7pm and a quick strength session at 7:45. How are we looking?"
3. User responds to each session individually
4. Agent handles different outcomes for each session

#### Scenario B: User wants full check-in during reminder

1. Reminder call begins normally
2. User starts discussing broader topics: "Actually, I've been struggling with motivation lately..."
3. Agent politely redirects: "Let's save that for when you open the app. For now, are you good for this yoga session?"
4. Keeps call focused on the immediate session

#### Scenario C: Calendar event was deleted

1. Scheduler finds session to remind about
2. Pre-call check discovers calendar event no longer exists
3. No call is made
4. Session status updated to `deleted_by_user`
5. Will be discussed at next check-in

**Postconditions:**
- Appropriate session statuses and reminder outcomes recorded
- User experience remains focused and helpful
- No unnecessary or confusing calls are made