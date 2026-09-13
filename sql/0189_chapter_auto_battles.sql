-- chapter_auto_battles (active operational handover queue)
CREATE TABLE IF NOT EXISTS chapter_auto_battles (
  commander_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  type integer NOT NULL DEFAULT 1,
  chapter_id integer NOT NULL,
  battle_index integer NOT NULL,
  finish_time bigint NOT NULL,
  ticket_time bigint NOT NULL DEFAULT 0,
  seconds integer NOT NULL,
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (commander_id, battle_index)
);
