CREATE TABLE IF NOT EXISTS account_permission_overrides (
  account_id text NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
  permission_id text NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
  mode text NOT NULL,
  can_read_self boolean NOT NULL DEFAULT false,
  can_read_any boolean NOT NULL DEFAULT false,
  can_write_self boolean NOT NULL DEFAULT false,
  can_write_any boolean NOT NULL DEFAULT false,
  updated_at timestamptz NOT NULL,
  PRIMARY KEY (account_id, permission_id)
);
