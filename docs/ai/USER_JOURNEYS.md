# User Journeys

## Journey 1: First-time onboarding (goal + schedule + plan)

**Actor:** User (first time)

**Preconditions:**
- Agent is running with valid LiveKit, OpenAI, and Google Calendar credentials
- User has a Google account with calendar access
- State is fresh (phase: `onboarding_goal`)

**Flow:**

1. User opens the web frontend
2. User clicks "Talk to Habits" to start a voice call
3. Agent greets the user warmly and explains what Habits does
4. Agent asks what fitness goal the user wants to work towards
5. User describes their goal in their own words
6. Agent explores: fitness level, exercise likes/dislikes, constraints, what's worked before
7. Agent reflects back understanding and confirms the goal
8. Agent transitions: "Great, now let's talk about your schedule"
9. Agent asks about daily routine: sleep, work, commute, regular commitments
10. Agent probes for hidden commitments (things not in the calendar)
11. Agent asks about preferred exercise times and weekly time commitment
12. Agent asks which calendar to write to and which to read from
13. Agent reads the calendar for the next 4 weeks
14. Agent summarises availability: "You seem fairly free on weekday evenings after 7:30..."
15. Agent generates a 4-week plan and books all sessions into the calendar
16. Agent tells the user: "I've added X sessions to your calendar. Take a look and come back when you're ready."
17. Call ends

**Postconditions:**
- State contains: user info, goal, schedule context, planned sessions
- Calendar has sessions booked
- Phase is `plan_proposed`

## Journey 2: Reviewing and adjusting the plan

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
9. Agent updates phase to `plan_confirmed`
10. Call ends

**Postconditions:**
- Calendar events updated
- Phase is `plan_confirmed`

## Journey 3: Check-in (ongoing)

**Actor:** User (returning for regular check-in)

**Preconditions:**
- Phase is `plan_confirmed` or `check_in`
- Some sessions have passed since last conversation

**Flow:**

1. User starts a new voice call
2. Agent checks for deleted events and reviews sessions since last conversation
3. Agent summarises: "It's been X days since we last spoke. You had N sessions planned."
4. Agent asks how each past session went (completed, skipped, partial)
5. Agent captures feedback and listens for signals (too hard, schedule issues, motivation)
6. If adaptation needed, agent proposes changes: "Want me to swap Thursday runs for swimming?"
7. Agent makes changes (checking availability first)
8. Agent previews upcoming sessions and flags any new calendar conflicts
9. If the plan is nearing its end, agent offers to plan the next 4-week cycle
10. Call ends

**Postconditions:**
- Session statuses updated (completed, skipped, etc.)
- Plan adapted if needed
- Conversation log saved
