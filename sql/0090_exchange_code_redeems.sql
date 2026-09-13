CREATE TABLE IF NOT EXISTS exchange_code_redeems (
  exchange_code_id bigint NOT NULL REFERENCES exchange_codes(id) ON DELETE CASCADE,
  commander_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  redeemed_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (exchange_code_id, commander_id)
);

CREATE INDEX IF NOT EXISTS idx_exchange_code_redeems_exchange_code_id_redeemed_at ON exchange_code_redeems(exchange_code_id, redeemed_at DESC);
