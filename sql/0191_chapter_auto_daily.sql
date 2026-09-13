-- chapter_auto_daily (daily operational handover time tracking)
CREATE TABLE IF NOT EXISTS chapter_auto_daily (
  commander_id bigint PRIMARY KEY REFERENCES commanders(commander_id) ON DELETE CASCADE,
  time_acc integer NOT NULL DEFAULT 0,
  extra_time_max integer NOT NULL DEFAULT 0,
  oil_bank integer NOT NULL DEFAULT 0,
  last_daily_reset_at timestamptz NOT NULL DEFAULT '1970-01-01 00:00:00+00',
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
