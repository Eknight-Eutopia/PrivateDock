CREATE TABLE IF NOT EXISTS commander_appreciation_states (
  commander_id bigint PRIMARY KEY REFERENCES commanders(commander_id) ON DELETE CASCADE,
  music_no bigint NOT NULL DEFAULT 0,
  music_mode bigint NOT NULL DEFAULT 0,
  cartoon_read_mark text NOT NULL DEFAULT '[]',
  cartoon_collect_mark text NOT NULL DEFAULT '[]',
  gallery_unlocks text NOT NULL DEFAULT '[]',
  gallery_favor_ids text NOT NULL DEFAULT '[]',
  music_favor_ids text NOT NULL DEFAULT '[]'
);
