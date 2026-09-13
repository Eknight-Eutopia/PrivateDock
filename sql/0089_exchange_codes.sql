CREATE TABLE IF NOT EXISTS exchange_codes (
  id bigserial PRIMARY KEY,
  code text NOT NULL UNIQUE,
  platform text NOT NULL DEFAULT '',
  quota bigint NOT NULL DEFAULT -1,
  rewards jsonb NOT NULL DEFAULT '[]'::jsonb,
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
