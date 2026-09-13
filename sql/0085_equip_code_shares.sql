CREATE TABLE IF NOT EXISTS equip_code_shares (
  id bigserial PRIMARY KEY,
  commander_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  ship_group_id bigint NOT NULL,
  share_day bigint NOT NULL,
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (commander_id, ship_group_id, share_day)
);

CREATE INDEX IF NOT EXISTS idx_equip_code_shares_commander_day ON equip_code_shares(commander_id, share_day);
