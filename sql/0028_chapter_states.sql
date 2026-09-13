CREATE TABLE IF NOT EXISTS chapter_states (
  commander_id bigint PRIMARY KEY REFERENCES commanders(commander_id) ON DELETE CASCADE,
  chapter_id bigint NOT NULL,
  state bytea NOT NULL,
  updated_at bigint NOT NULL DEFAULT 0
);
