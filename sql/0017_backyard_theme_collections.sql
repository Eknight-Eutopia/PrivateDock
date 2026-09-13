CREATE TABLE IF NOT EXISTS backyard_theme_collections (
  commander_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  theme_id text NOT NULL,
  upload_time bigint NOT NULL,
  PRIMARY KEY (commander_id, theme_id, upload_time)
);

CREATE INDEX IF NOT EXISTS idx_backyard_theme_collections_commander_upload ON backyard_theme_collections(commander_id, upload_time DESC);
