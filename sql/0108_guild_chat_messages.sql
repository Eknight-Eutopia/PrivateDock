CREATE TABLE IF NOT EXISTS guild_chat_messages (
  id bigserial PRIMARY KEY,
  guild_id bigint NOT NULL,
  sender_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  sent_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  content text NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_guild_chat_time ON guild_chat_messages(guild_id, sent_at DESC);
