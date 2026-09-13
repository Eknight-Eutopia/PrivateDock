CREATE TABLE IF NOT EXISTS commander_surveys (
  commander_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  survey_id bigint NOT NULL,
  completed_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (commander_id, survey_id)
);
