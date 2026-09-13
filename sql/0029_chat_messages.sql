CREATE TABLE IF NOT EXISTS chat_messages (
  id BIGSERIAL PRIMARY KEY,
  room_id BIGINT NOT NULL DEFAULT 0,
  sender_id BIGINT NOT NULL DEFAULT 0,
  sender_name TEXT NOT NULL DEFAULT '',
  sender_level INTEGER NOT NULL DEFAULT 0,
  sender_icon INTEGER NOT NULL DEFAULT 0,
  content TEXT NOT NULL DEFAULT '',
  timestamp BIGINT NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS chat_messages_room_id_idx ON chat_messages (room_id);

CREATE INDEX IF NOT EXISTS chat_messages_timestamp_idx ON chat_messages (timestamp);
