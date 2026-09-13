CREATE TABLE IF NOT EXISTS messages (
  id bigserial PRIMARY KEY,
  sender_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  room_id bigint NOT NULL,
  sent_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  content varchar(512) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_messages_room_id_sent_at ON messages (room_id, sent_at DESC);
