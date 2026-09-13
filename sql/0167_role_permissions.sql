CREATE TABLE IF NOT EXISTS role_permissions (
  role_id text NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
  permission_id text NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
  can_read_self boolean NOT NULL DEFAULT false,
  can_read_any boolean NOT NULL DEFAULT false,
  can_write_self boolean NOT NULL DEFAULT false,
  can_write_any boolean NOT NULL DEFAULT false,
  updated_at timestamptz NOT NULL,
  PRIMARY KEY (role_id, permission_id)
);
