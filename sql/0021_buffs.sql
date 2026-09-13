CREATE TABLE IF NOT EXISTS buffs (
  id bigint PRIMARY KEY,
  name text NOT NULL,
  description text NOT NULL,
  max_time integer NOT NULL DEFAULT 0,
  benefit_type text NOT NULL
);
