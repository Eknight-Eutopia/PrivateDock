CREATE TABLE IF NOT EXISTS mini_game_shop_states (
  commander_id bigint PRIMARY KEY REFERENCES commanders(commander_id) ON DELETE CASCADE,
  next_refresh_time bigint NOT NULL
);
