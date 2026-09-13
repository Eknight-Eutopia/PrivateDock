CREATE TABLE IF NOT EXISTS device_auth_maps (
  device_id text PRIMARY KEY,
  arg2 bigint NOT NULL,
  account_id bigint NOT NULL,
  updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
