CREATE TABLE IF NOT EXISTS activity_permanent_states (
  commander_id bigint PRIMARY KEY,
  current_activity_id bigint NOT NULL DEFAULT 0,
  finished_activity_ids jsonb NOT NULL DEFAULT '[]'::jsonb,
  FOREIGN KEY (commander_id) REFERENCES commanders(commander_id) ON DELETE CASCADE
);
