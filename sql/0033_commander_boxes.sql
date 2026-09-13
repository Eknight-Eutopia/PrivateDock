CREATE TABLE IF NOT EXISTS commander_boxes (
  commander_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  box_id bigint NOT NULL,
  pool_id bigint NOT NULL DEFAULT 0,
  begin_time bigint NOT NULL DEFAULT 0,
  finish_time bigint NOT NULL DEFAULT 0,
  PRIMARY KEY (commander_id, box_id)
);
