CREATE TABLE IF NOT EXISTS guild_operation_perfs (
  guild_id bigint NOT NULL REFERENCES guilds(id) ON DELETE CASCADE,
  event_tid bigint NOT NULL,
  perf_index bigint NOT NULL,
  PRIMARY KEY (guild_id, event_tid)
);
