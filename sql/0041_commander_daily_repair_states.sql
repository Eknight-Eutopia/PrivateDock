CREATE TABLE IF NOT EXISTS commander_daily_repair_states (
  commander_id bigint NOT NULL PRIMARY KEY,
  count bigint NOT NULL DEFAULT 0,
  reset_key text NOT NULL DEFAULT '',
  updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
