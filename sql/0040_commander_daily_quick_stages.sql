CREATE TABLE IF NOT EXISTS commander_daily_quick_stages (
  commander_id bigint NOT NULL,
  stage_id bigint NOT NULL,
  updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (commander_id, stage_id)
);
