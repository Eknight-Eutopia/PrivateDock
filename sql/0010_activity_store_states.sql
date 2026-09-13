CREATE TABLE IF NOT EXISTS activity_store_states (
  commander_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  activity_id bigint NOT NULL,
  data1 bigint NOT NULL DEFAULT 0,
  data2 bigint NOT NULL DEFAULT 0,
  data3 bigint NOT NULL DEFAULT 0,
  data1_list text NOT NULL DEFAULT '[]',
  str_data1 text NOT NULL DEFAULT '',
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (commander_id, activity_id)
);
