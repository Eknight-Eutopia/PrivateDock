CREATE TABLE IF NOT EXISTS mini_game_shop_goods (
  commander_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  goods_id bigint NOT NULL,
  count bigint NOT NULL,
  PRIMARY KEY (commander_id, goods_id)
);
