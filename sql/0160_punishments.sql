CREATE TABLE IF NOT EXISTS punishments (
  id bigserial PRIMARY KEY,
  punished_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  lift_timestamp timestamptz,
  is_permanent boolean NOT NULL DEFAULT false
);

CREATE INDEX IF NOT EXISTS idx_punishments_punished_id ON punishments (punished_id);
