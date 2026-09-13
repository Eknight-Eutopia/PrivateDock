CREATE TABLE IF NOT EXISTS builds (
  id bigserial PRIMARY KEY,
  builder_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  ship_id bigint NOT NULL REFERENCES ships(template_id) ON DELETE CASCADE,
  pool_id bigint NOT NULL,
  finishes_at timestamptz NOT NULL,
  state integer NOT NULL DEFAULT 1
);
