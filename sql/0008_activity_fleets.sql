CREATE TABLE IF NOT EXISTS activity_fleets (
  commander_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  activity_id bigint NOT NULL,
  group_list jsonb NOT NULL DEFAULT '[]'::jsonb,
  PRIMARY KEY (commander_id, activity_id)
);
