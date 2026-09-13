CREATE TABLE IF NOT EXISTS player_informs (
  id bigserial PRIMARY KEY,
  reporter_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  target_id bigint NOT NULL,
  info text NOT NULL,
  content text NOT NULL,
  created_at bigint NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_player_informs_reporter_id_created_at ON player_informs(reporter_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_player_informs_target_id_created_at ON player_informs(target_id, created_at DESC);
