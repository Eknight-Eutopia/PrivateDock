CREATE TABLE IF NOT EXISTS commander_meta_tactics_states (
  commander_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  ship_id bigint NOT NULL REFERENCES owned_ships(id) ON DELETE CASCADE,
  current_skill_id bigint NOT NULL DEFAULT 0,
  daily_exp bigint NOT NULL DEFAULT 0,
  double_exp bigint NOT NULL DEFAULT 0,
  switch_cnt bigint NOT NULL DEFAULT 3,
  updated_at timestamptz NOT NULL DEFAULT NOW(),
  PRIMARY KEY (commander_id, ship_id)
);
