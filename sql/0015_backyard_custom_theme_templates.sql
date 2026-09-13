CREATE TABLE IF NOT EXISTS backyard_custom_theme_templates (
  commander_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  pos bigint NOT NULL,
  name text NOT NULL,
  furniture_put_list jsonb NOT NULL DEFAULT '[]'::jsonb,
  icon_image_md5 text NOT NULL DEFAULT '',
  image_md5 text NOT NULL DEFAULT '',
  upload_time bigint NOT NULL DEFAULT 0,
  PRIMARY KEY (commander_id, pos)
);
