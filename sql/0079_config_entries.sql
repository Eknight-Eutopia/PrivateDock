CREATE TABLE IF NOT EXISTS config_entries (
  id bigserial PRIMARY KEY,
  category text NOT NULL,
  key text NOT NULL,
  data jsonb NOT NULL,
  UNIQUE (category, key)
);
