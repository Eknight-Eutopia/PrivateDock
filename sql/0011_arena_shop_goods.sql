CREATE TABLE IF NOT EXISTS arena_shop_goods (
  commander_id BIGINT NOT NULL,
  shop_id      BIGINT NOT NULL,
  buy_count    BIGINT NOT NULL DEFAULT 0,
  PRIMARY KEY (commander_id, shop_id)
);
