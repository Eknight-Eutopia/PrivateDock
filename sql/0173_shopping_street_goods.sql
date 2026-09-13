CREATE TABLE IF NOT EXISTS shopping_street_goods (
  commander_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  goods_id bigint NOT NULL,
  discount bigint NOT NULL,
  buy_count bigint NOT NULL,
  PRIMARY KEY (commander_id, goods_id)
);
