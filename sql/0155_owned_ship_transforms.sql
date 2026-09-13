CREATE TABLE IF NOT EXISTS owned_ship_transforms (
  owner_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  ship_id bigint NOT NULL REFERENCES owned_ships(id) ON DELETE CASCADE,
  transform_id bigint NOT NULL,
  level bigint NOT NULL DEFAULT 0,
  PRIMARY KEY (owner_id, ship_id, transform_id)
);
