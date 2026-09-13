CREATE TABLE IF NOT EXISTS likes (
  group_id bigint NOT NULL,
  liker_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  PRIMARY KEY (group_id, liker_id)
);
