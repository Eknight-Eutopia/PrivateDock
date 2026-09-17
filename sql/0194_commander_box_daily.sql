CREATE TABLE IF NOT EXISTS commander_box_daily (
  commander_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  usage_count bigint NOT NULL DEFAULT 0,
  reset_day bigint NOT NULL DEFAULT 0,
  last_reset_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (commander_id)
);
