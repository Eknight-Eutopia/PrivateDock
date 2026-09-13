CREATE TABLE IF NOT EXISTS owned_ship_strengths (
  owner_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  ship_id bigint NOT NULL REFERENCES owned_ships(id) ON DELETE CASCADE,
  strength_id bigint NOT NULL,
  exp bigint NOT NULL DEFAULT 0,
  PRIMARY KEY (owner_id, ship_id, strength_id)
);
