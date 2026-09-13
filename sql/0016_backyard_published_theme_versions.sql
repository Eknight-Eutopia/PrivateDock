CREATE TABLE IF NOT EXISTS backyard_published_theme_versions (
  theme_id text NOT NULL,
  upload_time bigint NOT NULL,
  owner_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  pos bigint NOT NULL,
  name text NOT NULL,
  furniture_put_list jsonb NOT NULL DEFAULT '[]'::jsonb,
  icon_image_md5 text NOT NULL DEFAULT '',
  image_md5 text NOT NULL DEFAULT '',
  like_count bigint NOT NULL DEFAULT 0,
  fav_count bigint NOT NULL DEFAULT 0,
  PRIMARY KEY (theme_id, upload_time)
);

CREATE INDEX IF NOT EXISTS idx_backyard_published_theme_versions_theme_id ON backyard_published_theme_versions(theme_id);
