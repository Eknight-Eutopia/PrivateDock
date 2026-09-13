CREATE TABLE IF NOT EXISTS juustagram_replies (
  id bigserial PRIMARY KEY,
  chat_group_record_id bigint NOT NULL REFERENCES juustagram_chat_groups(id) ON DELETE CASCADE,
  sequence bigint NOT NULL,
  key bigint NOT NULL,
  value bigint NOT NULL,
  UNIQUE (chat_group_record_id, sequence)
);

CREATE INDEX IF NOT EXISTS idx_juus_reply_chat_group_record_id ON juustagram_replies(chat_group_record_id);
