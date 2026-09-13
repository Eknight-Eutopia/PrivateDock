CREATE TABLE IF NOT EXISTS exercise_states (
  commander_id      bigint PRIMARY KEY REFERENCES commanders(commander_id) ON DELETE CASCADE,
  season_id         integer NOT NULL DEFAULT 1,
  season_end        bigint  NOT NULL DEFAULT 0,
  score             integer NOT NULL DEFAULT 0,
  merit             integer NOT NULL DEFAULT 0,
  fight_count       integer NOT NULL DEFAULT 10,
  next_recover_time bigint  NOT NULL DEFAULT 0,
  refreshes_today   integer NOT NULL DEFAULT 5,
  last_refresh_day  bigint  NOT NULL DEFAULT 0,
  created_at        bigint  NOT NULL DEFAULT 0,
  updated_at        bigint  NOT NULL DEFAULT 0,
  rewarded_rank INT NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_exercise_states_commander ON exercise_states(commander_id);
