-- commander_equip_skins (equipment skin ownership; drop type 9 / SC_14101)
CREATE TABLE IF NOT EXISTS commander_equip_skins (
  commander_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  skin_id bigint NOT NULL,
  count bigint NOT NULL DEFAULT 0,
  PRIMARY KEY (commander_id, skin_id)
);
