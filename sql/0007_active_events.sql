CREATE TABLE IF NOT EXISTS active_events (
  commander_id bigint       NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  event_id     bigint       NOT NULL,
  ship_id      bigint       NOT NULL DEFAULT 0,
  created_at   timestamptz,
  PRIMARY KEY (commander_id, event_id)
);

CREATE INDEX IF NOT EXISTS idx_active_events_commander ON active_events(commander_id);
