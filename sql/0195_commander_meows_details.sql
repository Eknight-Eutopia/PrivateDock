ALTER TABLE commander_meows ADD COLUMN IF NOT EXISTS skills text NOT NULL DEFAULT '[]';
ALTER TABLE commander_meows ADD COLUMN IF NOT EXISTS ability text NOT NULL DEFAULT '[]';
ALTER TABLE commander_meows ADD COLUMN IF NOT EXISTS ability_origin text NOT NULL DEFAULT '[]';
ALTER TABLE commander_meows ADD COLUMN IF NOT EXISTS name text NOT NULL DEFAULT '';
ALTER TABLE commander_meows ADD COLUMN IF NOT EXISTS rename_time bigint NOT NULL DEFAULT 0;
