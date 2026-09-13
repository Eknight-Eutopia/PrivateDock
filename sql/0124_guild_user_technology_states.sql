CREATE TABLE IF NOT EXISTS guild_user_technology_states (
  commander_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  tech_group bigint NOT NULL,
  tech_id bigint NOT NULL,
  updated_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (commander_id, tech_group)
);
