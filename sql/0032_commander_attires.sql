CREATE TABLE IF NOT EXISTS commander_attires (
  commander_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  type bigint NOT NULL,
  attire_id bigint NOT NULL,
  expires_at timestamptz,
  is_new boolean NOT NULL DEFAULT false,
  PRIMARY KEY (commander_id, type, attire_id)
);
