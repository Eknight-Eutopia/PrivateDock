CREATE TABLE IF NOT EXISTS juustagram_ship_group_templates (
  ship_group bigint PRIMARY KEY,
  name text NOT NULL,
  background text NOT NULL,
  sculpture text NOT NULL,
  sculpture_ii text NOT NULL,
  nationality bigint NOT NULL,
  type bigint NOT NULL
);
