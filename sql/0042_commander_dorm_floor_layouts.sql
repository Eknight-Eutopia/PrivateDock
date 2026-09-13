CREATE TABLE IF NOT EXISTS commander_dorm_floor_layouts (
  commander_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  floor bigint NOT NULL,
  furniture_put_list jsonb NOT NULL,
  PRIMARY KEY (commander_id, floor)
);
