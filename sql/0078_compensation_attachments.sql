CREATE TABLE IF NOT EXISTS compensation_attachments (
  id bigserial PRIMARY KEY,
  compensation_id bigint NOT NULL REFERENCES compensations(id) ON DELETE CASCADE,
  type bigint NOT NULL,
  item_id bigint NOT NULL,
  quantity bigint NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_compensation_attachments_compensation_id ON compensation_attachments(compensation_id);
