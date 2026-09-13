CREATE TABLE IF NOT EXISTS commander_medal_displays (
  commander_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  position bigint NOT NULL,
  medal_id bigint NOT NULL,
  PRIMARY KEY (commander_id, position)
);
