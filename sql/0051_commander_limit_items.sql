CREATE TABLE IF NOT EXISTS commander_limit_items (
  commander_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  item_id bigint NOT NULL,
  month_bucket bigint NOT NULL,
  count bigint NOT NULL DEFAULT 0,
  updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (commander_id, item_id, month_bucket)
);
