CREATE TABLE IF NOT EXISTS auth_challenges (
  id text PRIMARY KEY,
  user_id text REFERENCES accounts(id) ON DELETE CASCADE,
  type text NOT NULL,
  challenge text NOT NULL,
  expires_at timestamptz NOT NULL,
  created_at timestamptz NOT NULL,
  metadata jsonb
);
