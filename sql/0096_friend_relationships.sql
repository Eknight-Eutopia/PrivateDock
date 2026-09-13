CREATE TABLE IF NOT EXISTS friend_relationships (
  commander_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  friend_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  created_at bigint NOT NULL,
  PRIMARY KEY (commander_id, friend_id),
  CHECK (commander_id < friend_id)
);

CREATE INDEX IF NOT EXISTS idx_friend_relationships_friend_id ON friend_relationships(friend_id);
