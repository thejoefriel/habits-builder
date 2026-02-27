-- Migration 002: user_profiles table
--
-- NextAuth's pg adapter creates the following tables automatically on first use:
--   users, accounts, sessions, verification_tokens
--
-- This table extends users with app-specific profile data collected during setup.
-- Populated in Phase 2 (profile setup UI).

CREATE TABLE IF NOT EXISTS user_profiles (
  user_id            TEXT        PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  phone_number       TEXT,
  write_calendar_id  TEXT,
  read_calendar_ids  TEXT[]      NOT NULL DEFAULT '{}',
  setup_complete     BOOLEAN     NOT NULL DEFAULT FALSE,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
