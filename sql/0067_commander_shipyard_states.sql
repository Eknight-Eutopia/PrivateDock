CREATE TABLE IF NOT EXISTS commander_shipyard_states (
  commander_id bigint PRIMARY KEY REFERENCES commanders(commander_id) ON DELETE CASCADE,
  cold_time bigint NOT NULL DEFAULT 0,
  daily_catchup_strengthen bigint NOT NULL DEFAULT 0,
  daily_catchup_strengthen_ur bigint NOT NULL DEFAULT 0
);
