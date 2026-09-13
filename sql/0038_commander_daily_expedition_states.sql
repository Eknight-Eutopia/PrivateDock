CREATE TABLE IF NOT EXISTS commander_daily_expedition_states (
  commander_id bigint NOT NULL,
  counter_type text NOT NULL,
  entity_id bigint NOT NULL DEFAULT 0,
  count bigint NOT NULL DEFAULT 0,
  reset_key text NOT NULL DEFAULT '',
  updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (commander_id, counter_type, entity_id)
);
