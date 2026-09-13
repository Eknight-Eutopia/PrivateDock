CREATE TABLE IF NOT EXISTS commander_tbs (
  commander_id bigint PRIMARY KEY REFERENCES commanders(commander_id) ON DELETE CASCADE,
  state bytea NOT NULL,
  permanent bytea NOT NULL
);
