CREATE TABLE IF NOT EXISTS build_pool_ships (
  pool_id INTEGER NOT NULL,
  template_id BIGINT NOT NULL,
  PRIMARY KEY (pool_id, template_id)
);
