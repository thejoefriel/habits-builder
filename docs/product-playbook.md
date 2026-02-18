# Product Playbook: Habits AI Fitness Planner

This document describes how Habits works. It is used by the AI agent to understand the product.

---

## Product Summary

**Product Name:** Habits

**What it does:** A voice-powered AI assistant that helps users build realistic exercise habits. The user speaks to the agent, which understands their fitness goals, learns their schedule, generates a personalised plan, books sessions directly into their Google Calendar, and calls them before each session as a friendly reminder.

**Who uses it:**
- A single user (MVP) who wants to get into a regular exercise routine

**Key value:** Instead of manually planning workouts and finding time in the calendar, the user just has a conversation. The agent handles scheduling, rescheduling, and adapting the plan over time. Phone reminders ensure sessions don't get forgotten.

---

## User Roles

| Role | Description | What they can do |
|------|-------------|------------------|
| User | Someone wanting to build an exercise habit | Talk to the agent, set goals, review calendar, provide feedback, do check-ins, receive phone reminders |

**Note:** Single-user MVP. No login system. Credentials are stored in `.env`.

---

## Features

### Voice Conversation
- User speaks to the agent via microphone
- Agent responds with voice (text-to-speech via OpenAI Realtime)
- Natural, conversational flow — not a form

### Goal Setting
The agent gathers:
- Fitness goal (in the user's own words)
- Current fitness level (beginner, intermediate, advanced)
- Exercise likes and dislikes
- Constraints (injuries, equipment access, gym membership)
- What's worked or failed before
- Phone number for reminder calls

### Schedule Discovery
The agent learns:
- Sleep/wake times
- Work hours and commute
- Regular commitments not in the calendar (childcare, meals, social)
- Preferred exercise times (weekday evenings, weekend mornings, etc.)
- How much weekly time feels realistic

### Calendar Integration
- Reads all connected calendars to understand total availability
- Writes sessions to one designated calendar
- Creates events with `🏋️ Habits:` prefix and `[habits-agent]` tag
- Never double-books — checks all calendars before creating events

### Plan Generation
- Creates a 4-week plan of specific sessions
- Each session has: title, type (strength/cardio/flexibility/mixed), duration, date, time
- Respects: calendar availability, routine blocks, sleep window, preferred times, fitness level
- Conservative for beginners (2-3 sessions/week, 30 min)
- Varied session types with rest days between intense sessions

### Phone Reminders
- System calls user 15 minutes before each session
- Brief voice conversation to confirm, reschedule, or skip
- Reminder agent can check availability and move calendar events
- No guilt if user needs to skip — agent adapts
- Handles edge cases: no answer, voicemail, user already in app

### Plan Feedback
- User reviews the calendar and reports back
- Agent handles changes: move sessions, remove sessions, add sessions
- Always checks availability before rebooking
- Loops until user confirms they're happy

### Check-ins
- User returns periodically for progress review
- Agent detects: completed sessions, skipped sessions, manually deleted events, reminder outcomes
- Gathers feedback on each session
- Adapts the plan based on signals (too hard/easy, schedule changes, motivation)
- Previews upcoming week and flags new calendar conflicts

---

## Conversation Phases

| Phase | What happens |
|-------|--------------|
| `onboarding_goal` | First conversation — gather fitness goal, preferences, and phone number |
| `onboarding_schedule` | Gather daily routine, calendar preferences, exercise times |
| `plan_proposed` | Sessions booked — waiting for user review |
| `plan_confirmed` | User approved the plan — sessions active, phone reminders enabled |
| `check_in` | Ongoing — review progress, adapt plan, discuss reminder outcomes |

---

## Reminder Call Guidelines

### For the Reminder Agent
- Keep calls brief (under 2 minutes unless rescheduling)
- Be friendly but focused — this isn't a full coaching session
- Ask if they're ready, or if they need to change anything
- If rescheduling: check availability and move the event
- If skipping: no guilt, mark as skipped, optionally suggest alternative
- If user wants to chat: politely redirect to opening the app

### Reminder Outcomes
- `confirmed` — user ready for the session
- `rescheduled` — session moved to different time
- `skipped` — user chose to skip, no guilt
- `no_answer` — call went to voicemail or no pickup
- `voicemail` — answering machine detected
- `error` — technical failure in calling

---

## Tone Guidelines

- Be warm but not patronising. No "Great job, champ!" energy.
- Be direct but not blunt.
- If sessions were missed, don't guilt. Ask what got in the way and adapt.
- If the user is struggling, suggest reducing rather than pushing harder.
- If the user deleted events manually, acknowledge it calmly.
- If unsure, ask the user rather than guessing.
- Keep voice responses concise — this is a spoken conversation, not a wall of text.
- **For phone reminders**: Be extra brief and focused. The user might be busy.

---

## What This Product Does NOT Have

- No user accounts or login system (single-user MVP)
- No database (state is a JSON file)
- No web dashboard for viewing the plan (calendar IS the visual layer)
- No email notifications (phone calls are the notification system)
- No file upload or image sharing
- No multi-goal support (fitness only for now)
- No retry logic for failed reminder calls (one attempt only)

---

## Common Terminology

| Term | Meaning |
|------|----------|
| Session | A planned exercise event in the calendar |
| Plan | A 4-week set of sessions |
| Check-in | A return conversation where the user reviews progress |
| Phase | Where the user is in their journey (onboarding → planning → check-ins) |
| Routine block | A recurring commitment not in the calendar (e.g. school run) |
| Habits tag | The `[habits-agent]` marker in event descriptions |
| Reminder call | Phone call 15 minutes before a session |
| Reminder outcome | What happened during the reminder call |

---

## FAQ

**Q: Can I use this without a microphone?**
A: No, this is a voice-only interface.

**Q: What if I don't have a Google Calendar?**
A: You need a Google account with Calendar access. The agent reads and writes to Google Calendar.

**Q: Can I edit sessions directly in my calendar?**
A: Yes. If you move or delete events, the agent will detect this at the next check-in.

**Q: What if I don't want phone reminders?**
A: During onboarding, you can decline to provide a phone number. No reminders will be sent.

**Q: What if I don't answer the reminder call?**
A: No problem. The system won't retry, and you can discuss what happened at your next check-in.

**Q: Can I reschedule during a reminder call?**
A: Yes. The reminder agent can check your availability and move the session to a better time.

**Q: What happens after the 4-week plan ends?**
A: The agent will offer to generate a new 4-week plan with updated preferences.