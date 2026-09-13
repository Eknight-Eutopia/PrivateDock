CREATE TABLE IF NOT EXISTS server_activities (
  activity_id  bigint PRIMARY KEY,
  enabled      boolean NOT NULL DEFAULT TRUE,
  is_permanent boolean NOT NULL DEFAULT FALSE,
  start_time   bigint  NOT NULL DEFAULT 0,
  end_time     bigint  NOT NULL DEFAULT 0,
  sort_order   integer NOT NULL DEFAULT 0,
  note         text    NOT NULL DEFAULT '',
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now()
);
