CREATE TABLE IF NOT EXISTS commander_furnitures (
  commander_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  furniture_id bigint NOT NULL,
  count bigint NOT NULL,
  get_time bigint NOT NULL,
  PRIMARY KEY (commander_id, furniture_id)
);
