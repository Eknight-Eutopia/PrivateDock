CREATE TABLE IF NOT EXISTS resources (
  id bigint PRIMARY KEY,
  item_id bigint NOT NULL DEFAULT 0,
  name text NOT NULL
);
