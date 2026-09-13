CREATE TABLE IF NOT EXISTS battle_sessions (
  commander_id bigint PRIMARY KEY REFERENCES commanders(commander_id) ON DELETE CASCADE,
  system bigint NOT NULL,
  stage_id bigint NOT NULL,
  key bigint NOT NULL,
  ship_ids jsonb NOT NULL DEFAULT '[]'::jsonb,
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
