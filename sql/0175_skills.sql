CREATE TABLE IF NOT EXISTS skills (
  id bigint PRIMARY KEY,
  name text NOT NULL,
  "desc" text,
  cd bigint NOT NULL,
  painting jsonb,
  picture text,
  ani_effect jsonb,
  ui_effect text,
  effect_list jsonb
);
