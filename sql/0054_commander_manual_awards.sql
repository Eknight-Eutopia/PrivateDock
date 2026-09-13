CREATE TABLE IF NOT EXISTS commander_manual_awards (
  commander_id BIGINT NOT NULL,
  page_id BIGINT NOT NULL,
  claimed INT NOT NULL DEFAULT 0,
  PRIMARY KEY (commander_id, page_id)
);
