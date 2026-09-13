CREATE TABLE IF NOT EXISTS commander_trophy_progresses (
  commander_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  trophy_id bigint NOT NULL,
  progress bigint NOT NULL DEFAULT 0,
  timestamp bigint NOT NULL DEFAULT 0,
  PRIMARY KEY (commander_id, trophy_id)
);
