CREATE TABLE IF NOT EXISTS limit_challenge_states (
  commander_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  month_bucket bigint NOT NULL,
  best_times jsonb NOT NULL DEFAULT '{}'::jsonb,
  awarded jsonb NOT NULL DEFAULT '{}'::jsonb,
  pass_ids jsonb NOT NULL DEFAULT '[]'::jsonb,
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (commander_id)
);
