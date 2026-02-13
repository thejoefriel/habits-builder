"""LiveKit SIP helper for outbound phone reminder calls.

Uses LiveKit's CreateSIPParticipant API to initiate outbound calls
through the configured SIP trunk (Twilio). No direct Twilio SDK needed.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Optional

from livekit import api

logger = logging.getLogger(__name__)


def is_sip_configured() -> bool:
    """Check if all required SIP/LiveKit environment variables are present."""
    required_vars = [
        "LIVEKIT_SIP_TRUNK_ID",
        "LIVEKIT_API_KEY",
        "LIVEKIT_API_SECRET",
        "LIVEKIT_URL",
    ]
    return all(os.environ.get(var) for var in required_vars)


async def initiate_reminder_call(
    phone_number: str,
    sessions: list[dict],
    user_id: str,
    user_name: str,
    timezone: str,
) -> Optional[str]:
    """Initiate a reminder call via LiveKit outbound SIP.

    Flow:
    1. LiveKit creates a SIP participant in a new room
    2. LiveKit calls the user's phone through the SIP trunk (Twilio)
    3. When answered, phone audio is bridged into the LiveKit room
    4. The agent server detects the new room and dispatches the reminder agent

    Args:
        phone_number: User's phone number in E.164 format (e.g. +447xxxxxxxxx).
        sessions: List of session dicts to remind about.
        user_id: User ID for room naming.
        user_name: User's name for the conversation.
        timezone: User's timezone.

    Returns:
        The room name if successful, None if failed.
    """
    if not is_sip_configured():
        logger.error("SIP not configured — set LIVEKIT_SIP_TRUNK_ID, LIVEKIT_API_KEY, LIVEKIT_API_SECRET, LIVEKIT_URL")
        return None

    trunk_id = os.environ["LIVEKIT_SIP_TRUNK_ID"]
    livekit_url = os.environ["LIVEKIT_URL"]
    api_key = os.environ["LIVEKIT_API_KEY"]
    api_secret = os.environ["LIVEKIT_API_SECRET"]

    # Room name prefixed with "reminder_" to match dispatch rule
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    room_name = f"reminder_{user_id}_{timestamp}"

    # Metadata for the room — the agent reads this to know what sessions to remind about
    participant_metadata = json.dumps({
        "type": "reminder_call",
        "user_id": user_id,
        "user_name": user_name,
        "timezone": timezone,
        "sessions": sessions,
    })

    try:
        lk = api.LiveKitAPI(livekit_url, api_key, api_secret)

        # 1. Create the room first with metadata so the agent can read it on dispatch
        await lk.room.create_room(
            api.CreateRoomRequest(
                name=room_name,
                metadata=participant_metadata,
                empty_timeout=300,  # 5 min timeout
            )
        )
        logger.info("Created reminder room: %s", room_name)

        # 2. Create the outbound SIP participant — LiveKit calls the phone via the trunk
        sip_participant = await lk.sip.create_sip_participant(
            api.CreateSIPParticipantRequest(
                sip_trunk_id=trunk_id,
                sip_call_to=phone_number,
                room_name=room_name,
                participant_identity=f"phone_{user_id}",
                participant_name=user_name,
                participant_metadata=participant_metadata,
                play_dialtone=False,
                krisp_enabled=True,
            )
        )

        logger.info(
            "Outbound SIP call initiated — room: %s, trunk: %s, to: %s, sip_call_id: %s",
            room_name,
            trunk_id,
            phone_number,
            getattr(sip_participant, "sip_call_id", "unknown"),
        )

        await lk.aclose()
        return room_name

    except Exception as e:
        logger.error("Failed to initiate SIP call: %s", e, exc_info=True)
        return None


async def has_active_session(user_id: str) -> bool:
    """Check if the user is currently in an active LiveKit room.

    Prevents calling a user who is already in a voice conversation.

    Args:
        user_id: The user ID to check.

    Returns:
        True if user is in an active room, False otherwise.
    """
    required = ["LIVEKIT_API_KEY", "LIVEKIT_API_SECRET", "LIVEKIT_URL"]
    if not all(os.environ.get(var) for var in required):
        return False

    livekit_url = os.environ["LIVEKIT_URL"]
    api_key = os.environ["LIVEKIT_API_KEY"]
    api_secret = os.environ["LIVEKIT_API_SECRET"]

    try:
        lk = api.LiveKitAPI(livekit_url, api_key, api_secret)

        rooms_response = await lk.room.list_rooms(api.ListRoomsRequest())

        for room in rooms_response.rooms:
            # Skip reminder rooms — we only care about main agent sessions
            if room.name.startswith("reminder_"):
                continue
            if room.num_participants > 0:
                await lk.aclose()
                return True

        await lk.aclose()
        return False

    except Exception as e:
        logger.error("Error checking active session: %s", e)
        return False
