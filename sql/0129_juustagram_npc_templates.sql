CREATE TABLE IF NOT EXISTS juustagram_npc_templates (
  id bigint PRIMARY KEY,
  ship_group bigint NOT NULL,
  message_persist text NOT NULL,
  npc_reply_persist text NOT NULL DEFAULT '[]',
  time_persist text NOT NULL DEFAULT '[]'
);
