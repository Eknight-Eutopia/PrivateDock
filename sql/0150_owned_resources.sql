CREATE TABLE IF NOT EXISTS owned_resources (
  commander_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  resource_id bigint NOT NULL REFERENCES resources(id) ON DELETE CASCADE,
  amount bigint NOT NULL DEFAULT 0,
  PRIMARY KEY (commander_id, resource_id)
);
