CREATE TABLE IF NOT EXISTS commander_homes (
  commander_id bigint PRIMARY KEY REFERENCES commanders(commander_id) ON DELETE CASCADE,
  level bigint NOT NULL DEFAULT 1,
  exp bigint NOT NULL DEFAULT 0,
  clean bigint NOT NULL DEFAULT 0,
  scene_open boolean NOT NULL DEFAULT false
);
