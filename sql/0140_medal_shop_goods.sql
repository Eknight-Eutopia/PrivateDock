CREATE TABLE IF NOT EXISTS medal_shop_goods (
  commander_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  index bigint NOT NULL,
  goods_id bigint NOT NULL,
  count bigint NOT NULL,
  PRIMARY KEY (commander_id, index)
);
