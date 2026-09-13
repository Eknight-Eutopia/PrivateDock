CREATE TABLE IF NOT EXISTS legacy_educate_states (
  id BIGSERIAL PRIMARY KEY,
  commander_id bigint NOT NULL,
  favor_lv bigint NOT NULL DEFAULT 0,
  favor_exp bigint NOT NULL DEFAULT 0,
  target_id bigint NOT NULL DEFAULT 0,
  call_name text NOT NULL DEFAULT '',
  endings jsonb NOT NULL DEFAULT '[]',
  qualifieds jsonb NOT NULL DEFAULT '[]',
  attrs jsonb NOT NULL DEFAULT '{}',
  resources jsonb NOT NULL DEFAULT '{}',
  task_progress jsonb NOT NULL DEFAULT '{}',
  option_records jsonb NOT NULL DEFAULT '{}',
  had_adjustment boolean NOT NULL DEFAULT false,
  child_display bigint NOT NULL DEFAULT 0
);

CREATE UNIQUE INDEX IF NOT EXISTS legacy_educate_states_commander_id_idx
  ON legacy_educate_states (commander_id);
