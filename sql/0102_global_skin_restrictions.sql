CREATE TABLE IF NOT EXISTS global_skin_restrictions (
  skin_id bigint PRIMARY KEY REFERENCES skins(id) ON DELETE CASCADE,
  type bigint NOT NULL
);
