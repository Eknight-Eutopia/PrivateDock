CREATE TABLE IF NOT EXISTS owned_skins (
  commander_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  skin_id bigint NOT NULL,
  expires_at timestamptz,
  PRIMARY KEY (commander_id, skin_id)
);
