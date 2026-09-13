CREATE TABLE IF NOT EXISTS friend_requests (
  id bigserial PRIMARY KEY,
  requester_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  target_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  content text NOT NULL DEFAULT '',
  created_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (requester_id, target_id)
);

CREATE INDEX IF NOT EXISTS idx_friend_requests_target_id ON friend_requests (target_id);
