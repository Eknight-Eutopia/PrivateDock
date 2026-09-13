-- commander_blacklist
CREATE TABLE IF NOT EXISTS commander_blacklist (
  commander_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  blocked_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (commander_id, blocked_id),
  CHECK (commander_id <> blocked_id)
);

CREATE INDEX IF NOT EXISTS idx_commander_blacklist_blocked_id
  ON commander_blacklist(blocked_id);
