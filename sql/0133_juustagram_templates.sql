CREATE TABLE IF NOT EXISTS juustagram_templates (
  id bigint PRIMARY KEY,
  group_id bigint NOT NULL,
  ship_group bigint NOT NULL,
  name text NOT NULL,
  sculpture text NOT NULL,
  picture_persist text NOT NULL,
  message_persist text NOT NULL,
  is_active bigint NOT NULL DEFAULT 0,
  npc_discuss_persist text NOT NULL DEFAULT '[]',
  time text NOT NULL DEFAULT '[]',
  time_persist text NOT NULL DEFAULT '[]',
  title text NOT NULL DEFAULT '',
  oalist_pic_persist text NOT NULL DEFAULT ''
);
