CREATE TABLE IF NOT EXISTS submarine_expedition_states (
  commander_id bigint PRIMARY KEY REFERENCES commanders(commander_id) ON DELETE CASCADE,
  last_refresh_time bigint NOT NULL DEFAULT 0,
  weekly_refresh_count bigint NOT NULL DEFAULT 0,
  active_chapter_id bigint NOT NULL DEFAULT 0,
  overall_progress bigint NOT NULL DEFAULT 0
);
