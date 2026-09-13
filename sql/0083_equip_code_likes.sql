CREATE TABLE IF NOT EXISTS equip_code_likes (
  id bigserial PRIMARY KEY,
  commander_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  ship_group_id bigint NOT NULL,
  share_id bigint NOT NULL,
  like_day bigint NOT NULL,
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (commander_id, ship_group_id, share_id, like_day)
);

CREATE INDEX IF NOT EXISTS idx_equip_code_likes_share_id ON equip_code_likes(share_id);
