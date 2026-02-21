"""PostgreSQL JSONB-based state management for Habits agent."""

from __future__ import annotations

import json
import logging
import os

import psycopg2
import psycopg2.extras

from models.schemas import AppState

logger = logging.getLogger(__name__)

# Module-level connection — one per process
_conn = None
_db_initialised = False


def _get_connection():
    """Get or create the module-level database connection."""
    global _conn
    if _conn is None or _conn.closed:
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            raise RuntimeError(
                "DATABASE_URL environment variable is not set. "
                "Example: postgresql://habits:habits@localhost:5432/habits"
            )
        _conn = psycopg2.connect(database_url)
        _conn.autocommit = True
        logger.info("Connected to database")
    return _conn


def _init_db() -> None:
    """Create the app_state table if it doesn't exist."""
    global _db_initialised
    if _db_initialised:
        return
    conn = _get_connection()
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS app_state (
                id INTEGER PRIMARY KEY DEFAULT 1,
                data JSONB NOT NULL,
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)
    _db_initialised = True
    logger.info("Database initialised")


def load_state() -> AppState:
    """Load application state from PostgreSQL. Returns default state if no row exists."""
    _init_db()
    conn = _get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT data FROM app_state WHERE id = 1")
            row = cur.fetchone()
            if row is None:
                logger.info("No state row found, returning default state")
                return AppState()
            return AppState.model_validate(row["data"])
    except Exception as e:
        logger.error("Failed to load state: %s", e)
        return AppState()


def save_state(state: AppState) -> None:
    """Persist application state to PostgreSQL."""
    _init_db()
    conn = _get_connection()
    data = json.loads(state.model_dump_json())
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO app_state (id, data, updated_at)
            VALUES (1, %s, NOW())
            ON CONFLICT (id) DO UPDATE
            SET data = EXCLUDED.data, updated_at = NOW()
            """,
            [psycopg2.extras.Json(data)],
        )
    logger.info("State saved to database")


def reset_state() -> AppState:
    """Reset state to defaults (useful for development)."""
    _init_db()
    conn = _get_connection()
    with conn.cursor() as cur:
        cur.execute("DELETE FROM app_state WHERE id = 1")
    state = AppState()
    save_state(state)
    return state
