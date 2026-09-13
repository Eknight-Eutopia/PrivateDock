CREATE TABLE IF NOT EXISTS remaster_progresses (
  id bigserial PRIMARY KEY,
  commander_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  chapter_id bigint NOT NULL,
  pos bigint NOT NULL,
  count bigint NOT NULL DEFAULT 0,
  received boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (commander_id, chapter_id, pos)
);
