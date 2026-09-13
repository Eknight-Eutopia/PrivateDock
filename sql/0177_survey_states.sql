CREATE TABLE IF NOT EXISTS survey_states (
  commander_id bigint PRIMARY KEY REFERENCES commanders(commander_id) ON DELETE CASCADE,
  survey_id bigint NOT NULL DEFAULT 0,
  completed_at timestamptz NOT NULL DEFAULT '1970-01-01 00:00:00+00',
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
