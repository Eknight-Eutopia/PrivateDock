CREATE TABLE IF NOT EXISTS commander_skill_classes (
  commander_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  room_id bigint NOT NULL,
  ship_id bigint NOT NULL REFERENCES owned_ships(id) ON DELETE CASCADE,
  skill_pos bigint NOT NULL,
  skill_id bigint NOT NULL,
  start_time bigint NOT NULL,
  finish_time bigint NOT NULL,
  exp bigint NOT NULL,
  PRIMARY KEY (commander_id, room_id),
  CONSTRAINT commander_skill_classes_commander_ship_unique UNIQUE (commander_id, ship_id)
);
