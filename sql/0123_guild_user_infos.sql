CREATE TABLE IF NOT EXISTS guild_user_infos (
  commander_id bigint PRIMARY KEY REFERENCES commanders(commander_id) ON DELETE CASCADE,
  guild_id bigint NOT NULL DEFAULT 0,
  donate_count bigint NOT NULL DEFAULT 0,
  benefit_time bigint NOT NULL DEFAULT 0,
  weekly_task_flag bigint NOT NULL DEFAULT 0,
  extra_donate bigint NOT NULL DEFAULT 0,
  extra_operation bigint NOT NULL DEFAULT 0,
  donate_tasks jsonb NOT NULL DEFAULT '[]'::jsonb,
  donate_day bigint NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_guild_user_infos_guild_id ON guild_user_infos (guild_id);
