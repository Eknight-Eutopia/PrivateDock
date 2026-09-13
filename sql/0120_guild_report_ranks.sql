CREATE TABLE IF NOT EXISTS guild_report_ranks (
  guild_id bigint NOT NULL REFERENCES guilds(id) ON DELETE CASCADE,
  report_id bigint NOT NULL REFERENCES guild_reports(id) ON DELETE CASCADE,
  user_id bigint NOT NULL,
  damage bigint NOT NULL,
  PRIMARY KEY (guild_id, report_id, user_id)
);
