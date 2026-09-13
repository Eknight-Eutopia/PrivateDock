CREATE TABLE IF NOT EXISTS guild_operation_states (
  guild_id bigint PRIMARY KEY REFERENCES guilds(id) ON DELETE CASCADE,
  chapter_id bigint NOT NULL,
  start_time bigint NOT NULL,
  end_time bigint NOT NULL,
  created_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP
);
