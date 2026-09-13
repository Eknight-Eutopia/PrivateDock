CREATE TABLE IF NOT EXISTS juustagram_player_discusses (
  id bigserial PRIMARY KEY,
  commander_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  message_id bigint NOT NULL,
  discuss_id bigint NOT NULL,
  option_index bigint NOT NULL,
  npc_reply_id bigint NOT NULL DEFAULT 0,
  comment_time bigint NOT NULL DEFAULT 0,
  UNIQUE (commander_id, message_id, discuss_id)
);

CREATE INDEX IF NOT EXISTS idx_juus_discuss_state_commander_id ON juustagram_player_discusses(commander_id);
