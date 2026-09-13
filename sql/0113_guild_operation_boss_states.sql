CREATE TABLE IF NOT EXISTS guild_operation_boss_states (
  guild_id bigint NOT NULL REFERENCES guilds(id) ON DELETE CASCADE,
  operation_id bigint NOT NULL,
  boss_id bigint NOT NULL,
  damage bigint NOT NULL DEFAULT 0,
  hp bigint NOT NULL DEFAULT 0,
  updated_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (guild_id, operation_id)
);
