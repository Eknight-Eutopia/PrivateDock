CREATE TABLE IF NOT EXISTS fleets (
  id bigserial PRIMARY KEY,
  game_id bigint NOT NULL,
  commander_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  name text NOT NULL,
  ship_list jsonb NOT NULL DEFAULT '[]'::jsonb,
  meowfficer_list jsonb NOT NULL DEFAULT '[]'::jsonb
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_fleets_commander_id_game_id_unique
  ON fleets (commander_id, game_id);
