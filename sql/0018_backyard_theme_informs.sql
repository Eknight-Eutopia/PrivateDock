CREATE TABLE IF NOT EXISTS backyard_theme_informs (
  id bigserial PRIMARY KEY,
  reporter_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  target_id bigint NOT NULL,
  target_name text NOT NULL,
  theme_id text NOT NULL,
  theme_name text NOT NULL,
  reason bigint NOT NULL,
  created_at bigint NOT NULL
);
