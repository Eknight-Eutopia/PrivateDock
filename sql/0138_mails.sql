CREATE TABLE IF NOT EXISTS mails (
  id bigserial PRIMARY KEY,
  receiver_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  read boolean NOT NULL DEFAULT false,
  date timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  title text NOT NULL,
  body text NOT NULL,
  attachments_collected boolean NOT NULL DEFAULT false,
  is_important boolean NOT NULL DEFAULT false,
  custom_sender text,
  is_archived boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
