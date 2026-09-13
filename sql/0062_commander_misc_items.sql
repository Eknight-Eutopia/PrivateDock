CREATE TABLE IF NOT EXISTS commander_misc_items (
  commander_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  item_id bigint NOT NULL REFERENCES items(id) ON DELETE CASCADE,
  data bigint NOT NULL DEFAULT 0,
  PRIMARY KEY (commander_id, item_id, data)
);
