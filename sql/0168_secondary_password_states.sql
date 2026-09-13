CREATE TABLE IF NOT EXISTS secondary_password_states (
  commander_id bigint PRIMARY KEY REFERENCES commanders(commander_id) ON DELETE CASCADE,
  password_hash text NOT NULL DEFAULT '',
  notice text NOT NULL DEFAULT '',
  system_list jsonb NOT NULL DEFAULT '[]'::jsonb,
  state bigint NOT NULL DEFAULT 0,
  fail_count bigint NOT NULL DEFAULT 0,
  fail_cd bigint NOT NULL DEFAULT 0
);
