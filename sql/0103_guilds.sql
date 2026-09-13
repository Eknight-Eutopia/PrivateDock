CREATE TABLE IF NOT EXISTS guilds (
  id bigserial PRIMARY KEY,
  policy bigint NOT NULL,
  faction bigint NOT NULL,
  name varchar(64) NOT NULL,
  level bigint NOT NULL DEFAULT 1,
  announce text NOT NULL DEFAULT '',
  manifesto text NOT NULL DEFAULT '',
  exp bigint NOT NULL DEFAULT 0,
  member_count bigint NOT NULL DEFAULT 0,
  change_faction_cd bigint NOT NULL DEFAULT 0,
  kick_leader_cd bigint NOT NULL DEFAULT 0,
  capital bigint NOT NULL DEFAULT 0,
  tech_id bigint NOT NULL DEFAULT 1000,
  created_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted_at timestamp,
  benefit_finish_time bigint NOT NULL DEFAULT 0,
  last_benefit_finish_time bigint NOT NULL DEFAULT 0,
  tech_cancel_cnt bigint NOT NULL DEFAULT 0
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_guilds_name_lower_active
ON guilds (LOWER(name))
WHERE deleted_at IS NULL;
