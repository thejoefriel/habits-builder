"""JSON file-based state management for Habits agent."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from models.schemas import AppState

logger = logging.getLogger(__name__)

STATE_FILE = Path(__file__).parent.parent / "data" / "state.json"


def load_state() -> AppState:
    """Load application state from JSON file. Returns default state if file doesn't exist."""
    if not STATE_FILE.exists():
        logger.info("No state file found, returning default state")
        return AppState()

    try:
        raw = STATE_FILE.read_text(encoding="utf-8")
        if not raw.strip():
            logger.info("State file is empty, returning default state")
            return AppState()
        data = json.loads(raw)
        return AppState.model_validate(data)
    except (json.JSONDecodeError, Exception) as e:
        logger.error("Failed to load state file: %s", e)
        return AppState()


def save_state(state: AppState) -> None:
    """Persist application state to JSON file."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(
        state.model_dump_json(indent=2),
        encoding="utf-8",
    )
    logger.info("State saved to %s", STATE_FILE)


def reset_state() -> AppState:
    """Reset state to defaults (useful for development)."""
    state = AppState()
    save_state(state)
    return state
