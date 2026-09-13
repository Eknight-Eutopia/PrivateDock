-- chapter_auto_records (stage fastest clear time records for operational handover)
CREATE TABLE IF NOT EXISTS chapter_auto_records (
  commander_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  type integer NOT NULL DEFAULT 1,
  chapter_id integer NOT NULL,
  seconds integer NOT NULL,
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (commander_id, type, chapter_id)
);
