CREATE TABLE IF NOT EXISTS exercise_fleets (
  commander_id bigint PRIMARY KEY REFERENCES commanders(commander_id) ON DELETE CASCADE,
  vanguard_ship_ids jsonb NOT NULL DEFAULT '[]'::jsonb,
  main_ship_ids jsonb NOT NULL DEFAULT '[]'::jsonb
);
