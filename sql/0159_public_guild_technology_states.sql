CREATE TABLE IF NOT EXISTS public_guild_technology_states (
  group_id    bigint PRIMARY KEY,
  head_tech_id bigint NOT NULL,
  state       int NOT NULL DEFAULT 0,
  progress    int NOT NULL DEFAULT 0,
  fake_tech_id bigint
);
