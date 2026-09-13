CREATE TABLE IF NOT EXISTS guild_shop_states (
  commander_id bigint PRIMARY KEY REFERENCES commanders(commander_id) ON DELETE CASCADE,
  refresh_count bigint NOT NULL,
  next_refresh_time bigint NOT NULL
);
