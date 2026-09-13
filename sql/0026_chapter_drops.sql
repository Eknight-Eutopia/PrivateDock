CREATE TABLE IF NOT EXISTS chapter_drops (
  commander_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  chapter_id bigint NOT NULL,
  ship_id bigint NOT NULL,
  PRIMARY KEY (commander_id, chapter_id, ship_id)
);
