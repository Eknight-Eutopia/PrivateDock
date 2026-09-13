CREATE TABLE IF NOT EXISTS feast_states (
  commander_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  act_id bigint NOT NULL,
  refresh_time bigint NOT NULL DEFAULT 0,
  party_roles jsonb NOT NULL DEFAULT '[]'::jsonb,
  special_roles jsonb NOT NULL DEFAULT '[]'::jsonb,
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (commander_id, act_id)
);
