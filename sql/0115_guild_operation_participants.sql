CREATE TABLE IF NOT EXISTS guild_operation_participants (
  guild_id bigint NOT NULL REFERENCES guilds(id) ON DELETE CASCADE,
  commander_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  join_times bigint NOT NULL DEFAULT 0,
  is_participant bigint NOT NULL DEFAULT 0,
  PRIMARY KEY (guild_id, commander_id)
);
