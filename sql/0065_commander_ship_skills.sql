CREATE TABLE IF NOT EXISTS commander_ship_skills (
  commander_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  ship_id bigint NOT NULL REFERENCES owned_ships(id) ON DELETE CASCADE,
  skill_pos bigint NOT NULL,
  skill_id bigint NOT NULL,
  level bigint NOT NULL DEFAULT 1,
  exp bigint NOT NULL DEFAULT 0,
  PRIMARY KEY (commander_id, ship_id, skill_pos)
);
