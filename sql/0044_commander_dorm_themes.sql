CREATE TABLE IF NOT EXISTS commander_dorm_themes (
  commander_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  theme_slot_id bigint NOT NULL,
  name text NOT NULL DEFAULT '',
  furniture_put_list jsonb NOT NULL,
  PRIMARY KEY (commander_id, theme_slot_id)
);
