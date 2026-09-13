CREATE TABLE IF NOT EXISTS backyard_theme_likes (
  commander_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  theme_id text NOT NULL,
  upload_time bigint NOT NULL,
  PRIMARY KEY (commander_id, theme_id, upload_time)
);
