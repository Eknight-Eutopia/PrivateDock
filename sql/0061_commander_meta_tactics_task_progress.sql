CREATE TABLE IF NOT EXISTS commander_meta_tactics_task_progress (
  commander_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  ship_id bigint NOT NULL REFERENCES owned_ships(id) ON DELETE CASCADE,
  skill_id bigint NOT NULL,
  task_id bigint NOT NULL,
  finish_cnt bigint NOT NULL DEFAULT 0,
  updated_at timestamptz NOT NULL DEFAULT NOW(),
  PRIMARY KEY (commander_id, ship_id, skill_id, task_id)
);
