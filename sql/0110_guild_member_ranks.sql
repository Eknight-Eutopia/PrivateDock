CREATE TABLE IF NOT EXISTS guild_member_ranks (
  guild_id bigint NOT NULL REFERENCES guilds(id) ON DELETE CASCADE,
  rank_type bigint NOT NULL,
  period bigint NOT NULL,
  user_id bigint NOT NULL,
  count bigint NOT NULL DEFAULT 0,
  PRIMARY KEY (guild_id, rank_type, period, user_id)
);

CREATE INDEX IF NOT EXISTS idx_guild_member_ranks_query
ON guild_member_ranks (guild_id, rank_type, period, count DESC, user_id ASC);
