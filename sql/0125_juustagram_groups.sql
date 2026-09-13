CREATE TABLE IF NOT EXISTS juustagram_groups (
  id bigserial PRIMARY KEY,
  commander_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  group_id bigint NOT NULL,
  skin_id bigint NOT NULL DEFAULT 0,
  favorite bigint NOT NULL DEFAULT 0,
  cur_chat_group bigint NOT NULL DEFAULT 0,
  UNIQUE (commander_id, group_id)
);

CREATE INDEX IF NOT EXISTS idx_juus_group_commander ON juustagram_groups(commander_id);
