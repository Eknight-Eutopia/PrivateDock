CREATE TABLE IF NOT EXISTS guild_members (
  guild_id bigint NOT NULL REFERENCES guilds(id) ON DELETE CASCADE,
  commander_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  duty bigint NOT NULL,
  liveness bigint NOT NULL DEFAULT 0,
  pre_online_time bigint NOT NULL DEFAULT 0,
  join_time bigint NOT NULL DEFAULT 0,
  PRIMARY KEY (guild_id, commander_id),
  UNIQUE (commander_id)
);

CREATE INDEX IF NOT EXISTS idx_guild_members_guild_id ON guild_members (guild_id);
