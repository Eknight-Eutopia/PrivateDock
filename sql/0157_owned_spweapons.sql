CREATE TABLE IF NOT EXISTS owned_spweapons (
  owner_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  id bigserial PRIMARY KEY,
  template_id bigint NOT NULL,
  attr_1 bigint NOT NULL DEFAULT 0,
  attr_2 bigint NOT NULL DEFAULT 0,
  attr_temp_1 bigint NOT NULL DEFAULT 0,
  attr_temp_2 bigint NOT NULL DEFAULT 0,
  effect bigint NOT NULL DEFAULT 0,
  pt bigint NOT NULL DEFAULT 0,
  equipped_ship_id bigint NOT NULL DEFAULT 0
);
