CREATE TABLE IF NOT EXISTS event_collections (
  id            bigserial PRIMARY KEY,
  commander_id  bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  commission_id bigint NOT NULL,
  type          smallint NOT NULL DEFAULT 1,   -- 1=daily, 2=urgent,
  state         smallint NOT NULL DEFAULT 0,   -- 0=available, 1=started, 2=ready,
  ship_ids      jsonb NOT NULL DEFAULT '[]'::jsonb,
  start_time    bigint NOT NULL DEFAULT 0,
  finish_time   bigint NOT NULL DEFAULT 0,
  spawn_time    bigint NOT NULL DEFAULT 0,
  expires_at    bigint NOT NULL DEFAULT 0,
  created_at    bigint NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_event_collections_commander ON event_collections(commander_id);

CREATE INDEX IF NOT EXISTS idx_event_collections_expiry ON event_collections(commander_id, state, expires_at);
