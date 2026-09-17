CREATE TABLE IF NOT EXISTS commander_prefab_fleets (
  owner_commander_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  prefab_id bigint NOT NULL,
  name text NOT NULL DEFAULT '',
  rename_cooldown_at timestamptz NOT NULL DEFAULT '1970-01-01 00:00:00+00',
  commander_slots jsonb NOT NULL DEFAULT '[]'::jsonb,
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (owner_commander_id, prefab_id)
);
