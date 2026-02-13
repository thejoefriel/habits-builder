"""Exercise dataset loader and filter.

Loads a curated exercise library from data/exercises.json and provides
filtering by session type, available equipment, and user constraints.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

EXERCISES_FILE = Path(__file__).parent.parent / "data" / "exercises.json"

# Load once at import time
_exercises: list[dict] = []
try:
    _exercises = json.loads(EXERCISES_FILE.read_text(encoding="utf-8"))
    logger.info("Loaded %d exercises from %s", len(_exercises), EXERCISES_FILE)
except Exception as e:
    logger.error("Failed to load exercises: %s", e)


# Mapping from user-described constraints to tags that should be avoided
CONSTRAINT_TO_AVOID_TAG = {
    "wrist injury": "wrist_caution",
    "wrist pain": "wrist_caution",
    "bad wrist": "wrist_caution",
    "wrist": "wrist_caution",
    "knee injury": "knee_caution",
    "knee pain": "knee_caution",
    "bad knee": "knee_caution",
    "knee": "knee_caution",
}

# Mapping from user-described constraints to tags that should be preferred
CONSTRAINT_TO_PREFER_TAG = {
    "wrist injury": "wrist_friendly",
    "wrist pain": "wrist_friendly",
    "bad wrist": "wrist_friendly",
    "wrist": "wrist_friendly",
    "knee injury": "knee_friendly",
    "knee pain": "knee_friendly",
    "bad knee": "knee_friendly",
    "knee": "knee_friendly",
}


def get_exercises(
    session_type: str | None = None,
    equipment: list[str] | None = None,
    constraints: list[str] | None = None,
    difficulty: str | None = None,
    muscle_focus: str | None = None,
) -> list[dict]:
    """Filter exercises based on session parameters.

    Args:
        session_type: Filter by type (strength, cardio, flexibility, mixed).
        equipment: User's available equipment. Exercises requiring equipment
                   not in this list are excluded (bodyweight exercises always included).
        constraints: User's constraints (e.g. ["wrist injury", "bad knee"]).
                     Exercises with caution tags for these constraints are excluded.
        difficulty: Filter by max difficulty (beginner, intermediate, advanced).
        muscle_focus: Filter to exercises targeting this muscle group.

    Returns:
        Filtered list of exercise dicts.
    """
    results = list(_exercises)

    # Filter by session type
    if session_type and session_type.strip():
        results = [e for e in results if e["type"] == session_type.strip().lower()]

    # Filter by difficulty
    if difficulty:
        difficulty_order = {"beginner": 0, "intermediate": 1, "advanced": 2}
        max_level = difficulty_order.get(difficulty.lower(), 2)
        results = [
            e for e in results
            if difficulty_order.get(e["difficulty"], 0) <= max_level
        ]

    # Filter by equipment — keep exercises that need no equipment or only
    # equipment the user has
    if equipment is not None:
        equipment_lower = {e.lower() for e in equipment}
        filtered = []
        for ex in results:
            required = ex.get("equipment", [])
            if not required:
                # Bodyweight — always available
                filtered.append(ex)
            elif any(req.lower() in equipment_lower for req in required):
                # User has at least one piece of required equipment
                filtered.append(ex)
        results = filtered

    # Filter by constraints — exclude exercises with caution tags
    if constraints:
        avoid_tags = set()
        for constraint in constraints:
            constraint_lower = constraint.lower()
            for key, tag in CONSTRAINT_TO_AVOID_TAG.items():
                if key in constraint_lower:
                    avoid_tags.add(tag)

        if avoid_tags:
            results = [
                e for e in results
                if not any(tag in e.get("tags", []) for tag in avoid_tags)
            ]

    # Filter by muscle focus
    if muscle_focus:
        focus_lower = muscle_focus.lower()
        results = [
            e for e in results
            if any(focus_lower in mg.lower() for mg in e.get("muscle_groups", []))
        ]

    return results


def format_exercise_list(exercises: list[dict], max_count: int = 15) -> str:
    """Format a list of exercises as a readable string for the agent.

    Args:
        exercises: List of exercise dicts.
        max_count: Maximum number to include.

    Returns:
        Formatted string with exercise names and notes.
    """
    if not exercises:
        return "No matching exercises found."

    lines = []
    for ex in exercises[:max_count]:
        equipment_str = f" (needs: {', '.join(ex['equipment'])})" if ex["equipment"] else ""
        lines.append(f"- {ex['name']}{equipment_str}: {ex.get('notes', '')}")

    return f"{len(exercises)} exercises available (showing {min(len(exercises), max_count)}):\n" + "\n".join(lines)
