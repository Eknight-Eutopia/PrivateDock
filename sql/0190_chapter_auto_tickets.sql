-- chapter_auto_tickets (handover permits with expiration timestamps)
CREATE TABLE IF NOT EXISTS chapter_auto_tickets (
  commander_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  ticket_type integer NOT NULL DEFAULT 1,
  expire_time bigint NOT NULL,
  count integer NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (commander_id, ticket_type, expire_time)
);
