CREATE TABLE IF NOT EXISTS juustagram_chat_groups (
  id bigserial PRIMARY KEY,
  commander_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  group_record_id bigint NOT NULL REFERENCES juustagram_groups(id) ON DELETE CASCADE,
  chat_group_id bigint NOT NULL,
  op_time bigint NOT NULL DEFAULT 0,
  read_flag bigint NOT NULL DEFAULT 0,
  UNIQUE (commander_id, chat_group_id)
);

CREATE INDEX IF NOT EXISTS idx_juus_chat_group_commander ON juustagram_chat_groups(commander_id);

CREATE INDEX IF NOT EXISTS idx_juus_chat_group_group_record_id ON juustagram_chat_groups(group_record_id);
