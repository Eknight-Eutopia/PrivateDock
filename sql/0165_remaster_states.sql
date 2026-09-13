CREATE TABLE IF NOT EXISTS remaster_states (
  commander_id bigint PRIMARY KEY REFERENCES commanders(commander_id) ON DELETE CASCADE,
  ticket_count bigint NOT NULL DEFAULT 0,
  active_chapter_id bigint NOT NULL DEFAULT 0,
  daily_count bigint NOT NULL DEFAULT 0,
  last_daily_reset_at timestamptz NOT NULL DEFAULT '1970-01-01 00:00:00+00',
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
