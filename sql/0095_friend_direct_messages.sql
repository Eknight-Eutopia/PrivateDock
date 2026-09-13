CREATE TABLE IF NOT EXISTS friend_direct_messages (
  id bigserial PRIMARY KEY,
  sender_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  receiver_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  content text NOT NULL,
  created_at bigint NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_friend_direct_messages_sender_receiver_created_at
  ON friend_direct_messages(sender_id, receiver_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_friend_direct_messages_receiver_created_at
  ON friend_direct_messages(receiver_id, created_at DESC);
