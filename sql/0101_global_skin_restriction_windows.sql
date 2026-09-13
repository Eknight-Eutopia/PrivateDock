CREATE TABLE IF NOT EXISTS global_skin_restriction_windows (
  id bigint PRIMARY KEY,
  skin_id bigint NOT NULL REFERENCES skins(id) ON DELETE CASCADE,
  type bigint NOT NULL,
  start_time bigint NOT NULL,
  stop_time bigint NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_global_skin_restriction_windows_skin_id ON global_skin_restriction_windows(skin_id);
