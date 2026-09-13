-- commander_likes
CREATE TABLE IF NOT EXISTS commander_likes (
  commander_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  group_id bigint NOT NULL,
  like_id bigint NOT NULL DEFAULT 0,
  timestamp bigint NOT NULL DEFAULT 0,
  PRIMARY KEY (commander_id, group_id, like_id)
);
