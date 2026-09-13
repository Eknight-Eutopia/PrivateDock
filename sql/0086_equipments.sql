CREATE TABLE IF NOT EXISTS equipments (
  id bigint PRIMARY KEY,
  base bigint,
  destroy_gold bigint NOT NULL,
  destroy_item jsonb,
  equip_limit integer NOT NULL,
  "group" bigint NOT NULL,
  important bigint NOT NULL,
  level bigint NOT NULL,
  next bigint NOT NULL,
  prev bigint NOT NULL,
  restore_gold bigint NOT NULL,
  restore_item jsonb,
  ship_type_forbidden jsonb,
  trans_use_gold bigint NOT NULL,
  trans_use_item jsonb,
  type bigint NOT NULL,
  upgrade_formula_id jsonb
);
