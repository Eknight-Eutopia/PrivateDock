CREATE TABLE IF NOT EXISTS permissions (
  id text PRIMARY KEY,
  key text NOT NULL UNIQUE,
  description text NOT NULL,
  created_at timestamptz NOT NULL,
  updated_at timestamptz NOT NULL
);
