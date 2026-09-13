CREATE TABLE IF NOT EXISTS guild_assault_recommendations (
  guild_id bigint NOT NULL REFERENCES guilds(id) ON DELETE CASCADE,
  commander_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  ship_id bigint NOT NULL,
  created_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (guild_id, commander_id, ship_id)
);

CREATE INDEX IF NOT EXISTS idx_guild_assault_recommendations_guild
    ON guild_assault_recommendations (guild_id, commander_id, ship_id);
