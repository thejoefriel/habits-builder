# Habits: Phone Call Reminder Feature

## Overview

This spec extends the Habits voice agent with outbound phone call reminders. When a user has a fitness session approaching, the system calls them on their phone for a brief voice conversation where they can confirm, reschedule, or skip the session.

This feature depends on the core Habits agent being functional first. Read `habits-spec.md` for the full base spec.

---

## User Stories

- As a user, I want to receive a phone call before my workout so that I'm reminded and can confirm I'm ready
- As a user, I want to reschedule a session during the reminder call so that I don't have to open the app
- As a user, I want to skip a session without guilt so that I can adapt to my day without feeling bad

---

## Architecture

Three new components:

1. **Reminder scheduler** - a background process that watches for upcoming sessions and triggers calls
2. **LiveKit SIP trunk** - the bridge between LiveKit and the phone network via Twilio
3. **Reminder agent** - a lightweight version of the main voice agent with a narrow, reminder-focused prompt

### Call flow

1. Scheduler checks `planned_sessions` every 5 minutes
2. Finds a session starting within the next 15 minutes where `reminder_sent` is `false`
3. Before calling, verifies the `gcal_event_id` still exists in Google Calendar (if deleted, skip and update status)
4. Checks there is no active LiveKit session for this user (don't call if they're already talking to the app)
5. Initiates an outbound SIP call to the user's phone number via LiveKit
6. LiveKit connects the call through the Twilio SIP trunk
7. User picks up. The reminder agent runs a short conversation:
   - "Ready" -> agent encourages, ends call
   - "Reschedule" -> agent checks availability, moves the event, confirms
   - "Skip" -> agent marks as skipped, no guilt, optionally suggests alternative
   - No answer -> timeout after 30 seconds of ringing, mark as `no_answer`
   - Voicemail -> leave a short message or hang up, mark as `voicemail`
8. Session record updated with `reminder_sent: true` and `reminder_outcome`

---

## Infrastructure Setup

### Twilio

- A Twilio account with a phone number (the number the call comes from)
- Elastic SIP Trunking configured
- Termination URI pointed at the LiveKit SIP endpoint
- Answering Machine Detection (AMD) enabled for voicemail handling

### LiveKit

- SIP trunk registered in the LiveKit project (via LiveKit CLI or API)
- SIP participant configuration that allows outbound calls
- Agent dispatched automatically when the SIP call connects

### Environment Variables

Add to `.env`:

```
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=+44...
LIVEKIT_SIP_TRUNK_ID=...
```

---

## Data Model Changes

### User (additions)

```json
{
  "phone_number": "+447xxxxxxxxx"
}
```

Collect this during onboarding. Add to the `onboarding_goal` flow: after confirming the goal, ask the user for their phone number so the agent can call them before sessions.

### Planned Session (additions)

```json
{
  "reminder_sent": false,
  "reminder_outcome": null
}
```

`reminder_outcome` is one of: `confirmed`, `rescheduled`, `skipped`, `no_answer`, `voicemail`, or `null` (not yet attempted).

---

## Reminder Agent

### System Prompt

```
You are Habits, calling to give a friendly workout reminder.

## Context
- User: {user.name}
- Session: {session.title} at {session.scheduled_start}
- Session type: {session.session_type}
- Duration: {session.duration_minutes} minutes

## Your behaviour
- Keep it brief. This is a quick reminder call, not a coaching session.
- Tell the user what's coming up and when.
- Ask if they're ready or if they need to change anything.
- If they want to reschedule: check calendar availability and move the event.
- If they want to skip: mark it as skipped, no guilt. Optionally suggest an alternative time.
- If they're ready: wish them well and end the call.
- Keep the whole call under 2 minutes unless the user wants to reschedule.
- Don't do a full check-in. That's for when they open the app.
```

### Available Tools

The reminder agent has access to a limited set of tools (not the full main agent toolset):

| Tool | Purpose |
|---|---|
| `get_all_availability(start_date, end_date)` | Check free slots when rescheduling |
| `update_calendar_event(calendar_id, event_id, updates)` | Move a session |
| `delete_calendar_event(calendar_id, event_id)` | Remove a skipped session |
| `save_state(state_updates)` | Update session record with outcome |

The reminder agent does NOT have access to: `create_calendar_event` (no new sessions from a reminder call), full state read (it only gets the specific session context).

---

## Reminder Scheduler

Runs as a separate background process alongside the main agent.

```python
# reminder_scheduler.py

import asyncio
from datetime import datetime, timedelta
from tools.state import get_state, save_state
from tools.calendar import event_exists
from tools.sip import initiate_reminder_call, has_active_session

REMINDER_LEAD_TIME_MINUTES = 15
CHECK_INTERVAL_SECONDS = 300  # 5 minutes

async def check_for_reminders():
    while True:
        state = get_state()
        user = state["user"]
        tz = user["timezone"]  # e.g. "Europe/London"
        now = datetime.now(tz=tz)
        reminder_window = now + timedelta(minutes=REMINDER_LEAD_TIME_MINUTES)

        sessions_to_remind = []

        for session in state["planned_sessions"]:
            if session["status"] != "upcoming":
                continue
            if session["reminder_sent"]:
                continue

            session_start = parse_datetime(
                session["scheduled_date"],
                session["scheduled_start"],
                tz
            )

            if now <= session_start <= reminder_window:
                sessions_to_remind.append(session)

        if not sessions_to_remind:
            await asyncio.sleep(CHECK_INTERVAL_SECONDS)
            continue

        # Pre-call checks
        # 1. Don't call if user is already in an active session
        if has_active_session(user["user_id"]):
            await asyncio.sleep(CHECK_INTERVAL_SECONDS)
            continue

        # 2. Verify calendar events still exist
        valid_sessions = []
        for session in sessions_to_remind:
            if await event_exists(user["write_calendar_id"], session["gcal_event_id"]):
                valid_sessions.append(session)
            else:
                session["status"] = "deleted_by_user"
                session["reminder_sent"] = True
                save_state(state)

        if not valid_sessions:
            await asyncio.sleep(CHECK_INTERVAL_SECONDS)
            continue

        # 3. Handle multiple sessions in one call
        # Pass all valid sessions to the call - agent handles them together
        await initiate_reminder_call(
            phone_number=user["phone_number"],
            sessions=valid_sessions
        )

        for session in valid_sessions:
            session["reminder_sent"] = True
        save_state(state)

        await asyncio.sleep(CHECK_INTERVAL_SECONDS)
```

---

## SIP Helper

```python
# tools/sip.py

from livekit import api

async def initiate_reminder_call(phone_number: str, sessions: list):
    """
    Initiate an outbound SIP call via LiveKit.

    Creates a SIP participant in a new LiveKit room, which triggers
    the reminder agent to be dispatched to that room.

    The session data is passed to the agent via room metadata.
    """
    # Create a LiveKit room for this call
    room_name = f"reminder-{sessions[0]['session_id']}"

    # Create SIP participant (outbound call)
    # This triggers Twilio to call the user's phone
    # When they pick up, the audio is bridged to the LiveKit room
    # The reminder agent is dispatched to the room and begins the conversation

    # Implementation depends on LiveKit SIP API version
    # See: https://docs.livekit.io/sip/
    pass


def has_active_session(user_id: str) -> bool:
    """
    Check if the user is currently in an active LiveKit room
    with the main Habits agent.
    """
    # Query LiveKit API for active rooms/participants
    pass
```

---

## Edge Cases

| Scenario | Behaviour |
|---|---|
| User doesn't pick up | Timeout after 30 seconds of ringing. Set `reminder_outcome: "no_answer"`. Do not retry. |
| Voicemail detected | Use Twilio AMD to detect. Leave a short message: "Hi {name}, just a reminder you have {title} in 15 minutes." Set `reminder_outcome: "voicemail"`. |
| User already in main agent session | Skip the call entirely. The user is already engaged with the app. |
| Calendar event was deleted | Skip the call. Update session status to `deleted_by_user`. |
| Multiple sessions within reminder window | Handle in a single call. Agent says: "You've got two sessions coming up..." |
| User asks to reschedule during call | Agent checks availability, moves the event, confirms. Same logic as plan feedback flow. |
| User wants a full check-in during call | Agent politely redirects: "Let's save that for when you open the app. For now, are you good for this session?" |
| Call fails (network/Twilio error) | Log the error. Set `reminder_outcome: "error"`. Do not retry. |

---

## File Structure (additions to base project)

```
habits/
├── ...existing files from habits-spec.md...
├── reminder_scheduler.py          # Background process for checking upcoming sessions
├── reminder_agent.py              # Lightweight reminder calls
├── prompts/
│   ├── system_prompt.py           # Main agent prompt (existing)
│   └── reminder_prompt.py         # Reminder call prompt builder
├── tools/
│   ├── ...existing tools...
│   └── sip.py                     # LiveKit SIP outbound call helper
```

---

## Implementation Order

This should be built after the core Habits agent is working (steps 1-7 in `habits-spec.md`).

1. **Data model updates**: Add `phone_number` to user, `reminder_sent` and `reminder_outcome` to planned sessions
2. **Twilio setup**: Account, phone number, Elastic SIP Trunking configured
3. **LiveKit SIP setup**: Register SIP trunk, configure outbound calling
4. **`sip.py` helper**: Implement `initiate_reminder_call` and `has_active_session` using LiveKit API
5. **`reminder_prompt.py`**: Build the reminder-specific system prompt with session context injection
6. **`reminder_agent.py`**: Lightweight agent with limited tools (reschedule, skip, confirm only)
7. **`reminder_scheduler.py`**: 5-minute check loop and all pre-call validations
8. **End-to-end test**: Trigger a real phone call, confirm two-way voice works, test reschedule flow

---

## Dependencies

- `livekit` - LiveKit server SDK for room/participant management
- `livekit-agents` - LiveKit agents framework (already used by main agent)
- `twilio` - Twilio Python SDK (for SIP trunk management if needed, though most config is in Twilio console)

---

## Onboarding Change

Update the `onboarding_goal` conversation flow to collect the user's phone number:

After confirming the fitness goal, the agent should ask:
> "One more thing - I can call you before each session as a reminder. If you'd like that, what's the best phone number to reach you on?"

If the user declines, set `phone_number` to `null` and skip all reminder logic. The scheduler should check for a valid phone number before attempting any calls.
