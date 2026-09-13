CREATE TABLE IF NOT EXISTS items (
  id bigint PRIMARY KEY,
  name text NOT NULL,
  rarity integer NOT NULL,
  shop_id integer NOT NULL DEFAULT -2,
  type integer NOT NULL,
  virtual_type integer NOT NULL
);
