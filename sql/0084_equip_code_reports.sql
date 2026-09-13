CREATE TABLE IF NOT EXISTS equip_code_reports (
  id bigserial PRIMARY KEY,
  commander_id bigint NOT NULL REFERENCES commanders(commander_id) ON DELETE CASCADE,
  share_id bigint NOT NULL,
  report_day bigint NOT NULL,
  ship_group_id bigint NOT NULL,
  report_type bigint NOT NULL,
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (commander_id, share_id, report_day)
);

CREATE INDEX IF NOT EXISTS idx_equip_code_reports_share_id ON equip_code_reports(share_id);
