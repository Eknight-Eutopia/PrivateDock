CREATE TABLE IF NOT EXISTS commander_offer_claims (
  commander_id BIGINT NOT NULL,
  offer_id INT NOT NULL,
  period TEXT NOT NULL,
  claimed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (commander_id, offer_id, period)
);
