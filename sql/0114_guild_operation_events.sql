CREATE TABLE IF NOT EXISTS guild_operation_events (
  guild_id bigint NOT NULL REFERENCES guilds(id) ON DELETE CASCADE,
  event_tid bigint NOT NULL,
  position bigint NOT NULL DEFAULT 1,
  start_time bigint NOT NULL DEFAULT 0,
  complete_time bigint NOT NULL DEFAULT 0,
  efficiency bigint NOT NULL DEFAULT 0,
  completed boolean NOT NULL DEFAULT false,
  shipinevent jsonb NOT NULL DEFAULT '[]'::jsonb,
  attr_acc_list jsonb NOT NULL DEFAULT '[]'::jsonb,
  attr_count_list jsonb NOT NULL DEFAULT '[]'::jsonb,
  eventnodes jsonb NOT NULL DEFAULT '[]'::jsonb,
  personship jsonb NOT NULL DEFAULT '[]'::jsonb,
  formation_time bigint NOT NULL DEFAULT 0,
  PRIMARY KEY (guild_id, event_tid)
);
