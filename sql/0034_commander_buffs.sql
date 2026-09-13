CREATE TABLE IF NOT EXISTS commander_buffs (
  commander_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  buff_id bigint NOT NULL,
  expires_at timestamptz NOT NULL,
  PRIMARY KEY (commander_id, buff_id)
);

CREATE INDEX IF NOT EXISTS idx_commander_buffs_expires_at ON commander_buffs (expires_at);
