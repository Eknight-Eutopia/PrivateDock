CREATE TABLE IF NOT EXISTS reflux_states (
  commander_id bigint PRIMARY KEY REFERENCES commanders(commander_id) ON DELETE CASCADE,
  active bigint NOT NULL DEFAULT 0,
  return_lv bigint NOT NULL DEFAULT 0,
  return_time bigint NOT NULL DEFAULT 0,
  ship_number bigint NOT NULL DEFAULT 0,
  last_offline_time bigint NOT NULL DEFAULT 0,
  pt bigint NOT NULL DEFAULT 0,
  sign_cnt bigint NOT NULL DEFAULT 0,
  sign_last_time bigint NOT NULL DEFAULT 0,
  pt_stage bigint NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
