CREATE TABLE IF NOT EXISTS shopping_street_states (
  commander_id bigint PRIMARY KEY REFERENCES commanders(commander_id) ON DELETE CASCADE,
  level bigint NOT NULL,
  next_flash_time bigint NOT NULL,
  level_up_time bigint NOT NULL,
  flash_count bigint NOT NULL
);
