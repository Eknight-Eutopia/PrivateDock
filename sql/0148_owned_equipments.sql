CREATE TABLE IF NOT EXISTS owned_equipments (
  commander_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  equipment_id bigint NOT NULL,
  count bigint NOT NULL DEFAULT 0,
  PRIMARY KEY (commander_id, equipment_id)
);
