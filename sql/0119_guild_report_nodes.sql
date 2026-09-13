CREATE TABLE IF NOT EXISTS guild_report_nodes (
  guild_id bigint NOT NULL REFERENCES guilds(id) ON DELETE CASCADE,
  report_id bigint NOT NULL REFERENCES guild_reports(id) ON DELETE CASCADE,
  node_id bigint NOT NULL,
  status bigint NOT NULL,
  PRIMARY KEY (guild_id, report_id, node_id)
);
