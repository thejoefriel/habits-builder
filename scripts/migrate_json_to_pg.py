#!/usr/bin/env python3
"""
One-time migration: load existing state.json and insert it into PostgreSQL.

Usage:
    DATABASE_URL=postgresql://habits:habits@localhost:5432/habits \
    python scripts/migrate_json_to_pg.py [path/to/state.json]

Defaults to agent/data/state.json if no path is provided.
"""

import json
import os
import sys
from pathlib import Path

import psycopg2
import psycopg2.extras

DEFAULT_STATE_FILE = Path(__file__).parent.parent / "agent" / "data" / "state.json"


def main():
    state_file = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_STATE_FILE

    if not state_file.exists():
        print(f"No state file found at {state_file}, nothing to migrate.")
        sys.exit(0)

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("Error: DATABASE_URL environment variable is not set.")
        print("Example: DATABASE_URL=postgresql://habits:habits@localhost:5432/habits")
        sys.exit(1)

    # Read the JSON file
    raw = state_file.read_text(encoding="utf-8")
    if not raw.strip():
        print("State file is empty, nothing to migrate.")
        sys.exit(0)

    data = json.loads(raw)
    print(f"Loaded state from {state_file}")

    # Connect and migrate
    conn = psycopg2.connect(database_url)
    conn.autocommit = True

    with conn.cursor() as cur:
        # Create table if needed
        cur.execute("""
            CREATE TABLE IF NOT EXISTS app_state (
                id INTEGER PRIMARY KEY DEFAULT 1,
                data JSONB NOT NULL,
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)

        # Check if data already exists
        cur.execute("SELECT id FROM app_state WHERE id = 1")
        if cur.fetchone():
            print("Warning: app_state row already exists. Overwriting.")

        # Upsert
        cur.execute(
            """
            INSERT INTO app_state (id, data, updated_at)
            VALUES (1, %s, NOW())
            ON CONFLICT (id) DO UPDATE
            SET data = EXCLUDED.data, updated_at = NOW()
            """,
            [psycopg2.extras.Json(data)],
        )

    conn.close()
    print("Migration complete. State is now in PostgreSQL.")


if __name__ == "__main__":
    main()
