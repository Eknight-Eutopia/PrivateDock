CREATE TABLE IF NOT EXISTS web_authn_credentials (
  id text PRIMARY KEY,
  user_id text NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
  credential_id text NOT NULL UNIQUE,
  public_key bytea NOT NULL,
  sign_count bigint NOT NULL DEFAULT 0,
  transports jsonb NOT NULL DEFAULT '[]'::jsonb,
  aaguid text NOT NULL DEFAULT '',
  attestation_fmt text NOT NULL DEFAULT '',
  resident_key text NOT NULL DEFAULT '',
  backup_eligible boolean,
  backup_state boolean,
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_used_at timestamptz,
  label text,
  rp_id text NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_web_authn_credentials_user_id ON web_authn_credentials(user_id);
