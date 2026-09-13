CREATE TABLE IF NOT EXISTS guild_capital_logs (
  id bigserial PRIMARY KEY,
  guild_id bigint NOT NULL REFERENCES guilds(id) ON DELETE CASCADE,
  category bigint NOT NULL,
  member_id bigint NOT NULL,
  name varchar(64) NOT NULL DEFAULT '',
  event_type bigint NOT NULL,
  event_target jsonb NOT NULL DEFAULT '[]'::jsonb,
  event_time bigint NOT NULL,
  created_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_guild_capital_logs_guild_category_time
ON guild_capital_logs (guild_id, category, event_time DESC, id DESC);
