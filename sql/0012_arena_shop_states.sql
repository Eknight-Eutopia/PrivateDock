CREATE TABLE IF NOT EXISTS arena_shop_states (
  commander_id bigint PRIMARY KEY REFERENCES commanders(commander_id) ON DELETE CASCADE,
  flash_count bigint NOT NULL,
  last_refresh_time bigint NOT NULL,
  next_flash_time bigint NOT NULL
);
