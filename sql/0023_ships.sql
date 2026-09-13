CREATE TABLE IF NOT EXISTS ships (
  template_id bigint PRIMARY KEY,
  name text NOT NULL,
  english_name text NOT NULL,
  rarity_id bigint NOT NULL,
  star bigint NOT NULL,
  type bigint NOT NULL,
  nationality bigint NOT NULL,
  build_time bigint NOT NULL
);
