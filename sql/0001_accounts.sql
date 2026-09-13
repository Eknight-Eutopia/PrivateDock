CREATE TABLE IF NOT EXISTS accounts (
  id text PRIMARY KEY,
  username text,
  username_normalized text UNIQUE,
  commander_id bigint UNIQUE,
  password_hash text NOT NULL,
  password_algo text NOT NULL,
  password_updated_at timestamptz NOT NULL,
  is_admin boolean NOT NULL DEFAULT false,
  disabled_at timestamptz,
  last_login_at timestamptz,
  web_authn_user_handle bytea UNIQUE,
  created_at timestamptz NOT NULL,
  updated_at timestamptz NOT NULL
);
