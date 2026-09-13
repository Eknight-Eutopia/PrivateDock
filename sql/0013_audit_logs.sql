CREATE TABLE IF NOT EXISTS audit_logs (
  id text PRIMARY KEY,
  actor_account_id text REFERENCES accounts(id) ON DELETE SET NULL,
  actor_commander_id bigint,
  method text NOT NULL,
  path text NOT NULL,
  status_code integer NOT NULL,
  permission_key text,
  permission_op text,
  action text,
  metadata jsonb,
  created_at timestamptz NOT NULL
);
