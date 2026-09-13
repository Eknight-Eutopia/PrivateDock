CREATE TABLE IF NOT EXISTS debugs (
  frame_id bigserial PRIMARY KEY,
  packet_size bigint NOT NULL,
  packet_id bigint NOT NULL,
  data bytea NOT NULL,
  logged_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
