CREATE TABLE IF NOT EXISTS guild_assault_fleet_slots (
  guild_id bigint NOT NULL REFERENCES guilds(id) ON DELETE CASCADE,
  commander_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  pos bigint NOT NULL,
  ship_id bigint NOT NULL,
  last_time bigint NOT NULL DEFAULT 0,
  created_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (guild_id, commander_id, pos)
);

CREATE INDEX IF NOT EXISTS idx_guild_assault_fleet_slots_guild_commander
    ON guild_assault_fleet_slots (guild_id, commander_id, pos);
