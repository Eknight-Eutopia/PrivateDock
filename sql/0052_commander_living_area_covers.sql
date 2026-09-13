CREATE TABLE IF NOT EXISTS commander_living_area_covers (
  commander_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  cover_id bigint NOT NULL,
  unlocked_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  is_new boolean NOT NULL DEFAULT false,
  PRIMARY KEY (commander_id, cover_id)
);
