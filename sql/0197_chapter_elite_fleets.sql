CREATE TABLE IF NOT EXISTS chapter_elite_fleets (
  commander_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  formation_id bigint NOT NULL,
  main_team jsonb NOT NULL DEFAULT '[]'::jsonb,
  submarine_team jsonb NOT NULL DEFAULT '[]'::jsonb,
  support_team jsonb NOT NULL DEFAULT '[]'::jsonb,
  updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (commander_id, formation_id)
);
