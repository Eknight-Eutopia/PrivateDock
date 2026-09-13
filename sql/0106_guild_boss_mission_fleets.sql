CREATE TABLE IF NOT EXISTS guild_boss_mission_fleets (
  guild_id bigint NOT NULL REFERENCES guilds(id) ON DELETE CASCADE,
  operation_id bigint NOT NULL,
  fleet_id bigint NOT NULL,
  ships jsonb NOT NULL DEFAULT '[]'::jsonb,
  commanders jsonb NOT NULL DEFAULT '[]'::jsonb,
  updated_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (guild_id, operation_id, fleet_id)
);

CREATE INDEX IF NOT EXISTS idx_guild_boss_mission_fleets_guild_operation
    ON guild_boss_mission_fleets (guild_id, operation_id, fleet_id);
