CREATE TABLE IF NOT EXISTS commander_daily_level_states (
  commander_id bigint NOT NULL,
  daily_level_id bigint NOT NULL,
  count bigint NOT NULL DEFAULT 0,
  reset_key text NOT NULL DEFAULT '',
  updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (commander_id, daily_level_id)
);
