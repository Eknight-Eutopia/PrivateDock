CREATE TABLE IF NOT EXISTS commander_dorm_states (
  commander_id bigint PRIMARY KEY REFERENCES commanders(commander_id) ON DELETE CASCADE,
  level bigint NOT NULL DEFAULT 1,
  food bigint NOT NULL DEFAULT 0,
  food_max_increase_count bigint NOT NULL DEFAULT 0,
  food_max_increase bigint NOT NULL DEFAULT 0,
  floor_num bigint NOT NULL DEFAULT 1,
  exp_pos bigint NOT NULL DEFAULT 2,
  next_timestamp bigint NOT NULL DEFAULT 0,
  load_exp bigint NOT NULL DEFAULT 0,
  load_food bigint NOT NULL DEFAULT 0,
  load_time bigint NOT NULL DEFAULT 0,
  updated_at_unix_timestamp bigint NOT NULL DEFAULT 0,
  pop_time_accum bigint NOT NULL DEFAULT 0,
  exp_fraction double precision NOT NULL DEFAULT 0
);
