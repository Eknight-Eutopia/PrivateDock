CREATE TABLE IF NOT EXISTS owned_ship_equipments (
  owner_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  ship_id bigint NOT NULL REFERENCES owned_ships(id) ON DELETE CASCADE,
  pos bigint NOT NULL,
  equip_id bigint NOT NULL,
  skin_id bigint NOT NULL,
  PRIMARY KEY (owner_id, ship_id, pos)
);
