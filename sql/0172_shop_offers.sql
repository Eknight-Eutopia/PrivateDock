CREATE TABLE IF NOT EXISTS shop_offers (
  id bigint PRIMARY KEY,
  effects jsonb NOT NULL,
  effect_args jsonb,
  number integer NOT NULL,
  resource_number integer NOT NULL,
  resource_id bigint NOT NULL,
  type bigint NOT NULL,
  genre text NOT NULL,
  discount integer NOT NULL
);
