CREATE TABLE IF NOT EXISTS account_roles (
  account_id text NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
  role_id text NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL,
  PRIMARY KEY (account_id, role_id)
);
