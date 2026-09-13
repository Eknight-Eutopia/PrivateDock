-- 0243: Research Academy catch-up bonus counters (Series 3+ catch-up system).
-- Mirrors the client's TECHNOLOGYCATCHUP pursuings: a shared non-UR ("ssr")
-- count per series version and a per-UR-ship count per series version.
-- Shape: {"ssr": {"<version>": <count>}, "dr": {"<version>": {"<ship_id>": <count>}}}
ALTER TABLE technology_research_states ADD COLUMN IF NOT EXISTS catchup_counters JSONB NOT NULL DEFAULT '{}'::jsonb;
