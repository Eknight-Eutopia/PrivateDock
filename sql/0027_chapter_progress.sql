CREATE TABLE IF NOT EXISTS chapter_progress (
  commander_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  chapter_id bigint NOT NULL,
  progress bigint NOT NULL DEFAULT 0,
  kill_boss_count bigint NOT NULL DEFAULT 0,
  kill_enemy_count bigint NOT NULL DEFAULT 0,
  take_box_count bigint NOT NULL DEFAULT 0,
  defeat_count bigint NOT NULL DEFAULT 0,
  today_defeat_count bigint NOT NULL DEFAULT 0,
  pass_count bigint NOT NULL DEFAULT 0,
  updated_at bigint NOT NULL DEFAULT 0,
  star_rewarded bigint NOT NULL DEFAULT 0,
  clear_rewarded bigint NOT NULL DEFAULT 0,
  PRIMARY KEY (commander_id, chapter_id)
);
