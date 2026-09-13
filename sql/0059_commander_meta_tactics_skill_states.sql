CREATE TABLE IF NOT EXISTS commander_meta_tactics_skill_states (
  commander_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  ship_id bigint NOT NULL REFERENCES owned_ships(id) ON DELETE CASCADE,
  skill_id bigint NOT NULL,
  skill_pos bigint NOT NULL,
  level bigint NOT NULL DEFAULT 0,
  exp bigint NOT NULL DEFAULT 0,
  updated_at timestamptz NOT NULL DEFAULT NOW(),
  PRIMARY KEY (commander_id, ship_id, skill_id),
  CONSTRAINT commander_meta_tactics_skill_states_unique_pos UNIQUE (commander_id, ship_id, skill_pos)
);
