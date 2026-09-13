CREATE TABLE IF NOT EXISTS commander_guild_states (
  commander_id bigint PRIMARY KEY REFERENCES commanders(commander_id) ON DELETE CASCADE,
  guild_wait_time bigint NOT NULL DEFAULT 0
);
