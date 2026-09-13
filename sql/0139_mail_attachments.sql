CREATE TABLE IF NOT EXISTS mail_attachments (
  id bigserial PRIMARY KEY,
  mail_id bigint NOT NULL REFERENCES mails(id) ON DELETE CASCADE,
  type bigint NOT NULL,
  item_id bigint NOT NULL,
  quantity bigint NOT NULL
);
