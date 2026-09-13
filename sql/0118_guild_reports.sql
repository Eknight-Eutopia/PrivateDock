CREATE TABLE IF NOT EXISTS guild_reports (
  guild_id bigint NOT NULL REFERENCES guilds(id) ON DELETE CASCADE,
  id bigserial PRIMARY KEY,
  event_id bigint NOT NULL,
  event_type bigint NOT NULL,
  score bigint NOT NULL,
  status bigint NOT NULL,
  claimed boolean NOT NULL DEFAULT false,
  drop_type bigint NOT NULL DEFAULT 1,
  drop_id bigint NOT NULL DEFAULT 1,
  drop_count bigint NOT NULL DEFAULT 0,
  created_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_guild_reports_guild_id_id ON guild_reports (guild_id, id);
