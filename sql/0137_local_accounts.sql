CREATE TABLE IF NOT EXISTS local_accounts (
  arg2 bigint PRIMARY KEY,
  account text NOT NULL UNIQUE,
  password text NOT NULL,
  mail_box text NOT NULL DEFAULT '',
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
