-- =============================================================================
-- DARA Cloud Knowledge Base — Supabase SQL Setup  (fully idempotent)
-- Safe to run multiple times. Copy all and paste into SQL Editor → New Query.
-- =============================================================================

-- Step 1: Enable the pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Step 2: Create the failure_logs table (skipped if already exists)
CREATE TABLE IF NOT EXISTS failure_logs (
    id                    BIGSERIAL PRIMARY KEY,
    case_id               TEXT UNIQUE,          -- mirrors local SQLite case_id
    session_id            TEXT,                 -- mirrors local SQLite session_id
    defect_type           TEXT NOT NULL,        -- e.g. 'too_little', 'missing_dot'
    defect_label          TEXT,                 -- e.g. 'UNDER DISPENSE'
    dispensing_problem    TEXT,                 -- free-text problem description
    root_cause            TEXT,                 -- confirmed cause
    resolution_action     TEXT,                 -- confirmed fix
    possible_causes       TEXT,                 -- JSON array
    recommended_solutions TEXT,                 -- JSON array
    measured_size_um      FLOAT,                -- optional telemetry
    pressure_bar          FLOAT,                -- optional telemetry
    viscosity_cps         FLOAT,                -- optional telemetry
    embedding             VECTOR(384),          -- all-MiniLM-L6-v2 (384 dims)
    created_at            TIMESTAMPTZ DEFAULT NOW()
);

-- Step 2b: Upgrade existing tables — add any columns that may be missing
--           (safe no-ops if columns already exist)
ALTER TABLE failure_logs ADD COLUMN IF NOT EXISTS case_id               TEXT UNIQUE;
ALTER TABLE failure_logs ADD COLUMN IF NOT EXISTS session_id            TEXT;
ALTER TABLE failure_logs ADD COLUMN IF NOT EXISTS defect_label          TEXT;
ALTER TABLE failure_logs ADD COLUMN IF NOT EXISTS dispensing_problem    TEXT;
ALTER TABLE failure_logs ADD COLUMN IF NOT EXISTS root_cause            TEXT;
ALTER TABLE failure_logs ADD COLUMN IF NOT EXISTS resolution_action     TEXT;
ALTER TABLE failure_logs ADD COLUMN IF NOT EXISTS possible_causes       TEXT;
ALTER TABLE failure_logs ADD COLUMN IF NOT EXISTS recommended_solutions TEXT;
ALTER TABLE failure_logs ADD COLUMN IF NOT EXISTS measured_size_um      FLOAT;
ALTER TABLE failure_logs ADD COLUMN IF NOT EXISTS pressure_bar          FLOAT;
ALTER TABLE failure_logs ADD COLUMN IF NOT EXISTS viscosity_cps         FLOAT;
ALTER TABLE failure_logs ADD COLUMN IF NOT EXISTS embedding             VECTOR(384);
ALTER TABLE failure_logs ADD COLUMN IF NOT EXISTS created_at            TIMESTAMPTZ DEFAULT NOW();

-- Step 3: Create vector index (skip if already exists)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE tablename = 'failure_logs'
          AND indexname = 'failure_logs_embedding_idx'
    ) THEN
        CREATE INDEX failure_logs_embedding_idx
            ON failure_logs
            USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 50);
    END IF;
END
$$;

-- Step 4: Drop any old version of the search function, then recreate cleanly
DROP FUNCTION IF EXISTS match_failure_logs(vector, integer);
DROP FUNCTION IF EXISTS match_failure_logs(vector(384), integer);
DROP FUNCTION IF EXISTS public.match_failure_logs(vector, integer);

CREATE FUNCTION match_failure_logs(
    query_embedding VECTOR(384),
    match_count     INT DEFAULT 5
)
RETURNS TABLE (
    id                 BIGINT,
    case_id            TEXT,
    defect_type        TEXT,
    defect_label       TEXT,
    dispensing_problem TEXT,
    root_cause         TEXT,
    resolution_action  TEXT,
    pressure_bar       FLOAT,
    viscosity_cps      FLOAT,
    measured_size_um   FLOAT,
    similarity         FLOAT
)
LANGUAGE sql
STABLE
AS $$
    SELECT
        fl.id,
        fl.case_id,
        fl.defect_type,
        fl.defect_label,
        fl.dispensing_problem,
        fl.root_cause,
        fl.resolution_action,
        fl.pressure_bar,
        fl.viscosity_cps,
        fl.measured_size_um,
        1 - (fl.embedding <=> query_embedding) AS similarity
    FROM failure_logs fl
    WHERE fl.embedding IS NOT NULL
      AND fl.root_cause IS NOT NULL
      AND fl.root_cause <> ''
    ORDER BY fl.embedding <=> query_embedding
    LIMIT match_count;
$$;

-- Step 5: Row Level Security
ALTER TABLE failure_logs ENABLE ROW LEVEL SECURITY;

-- Drop policies first so re-runs don't fail
DROP POLICY IF EXISTS service_role_all ON failure_logs;
DROP POLICY IF EXISTS anon_read        ON failure_logs;

-- Service role (backend) can read and write
CREATE POLICY service_role_all
    ON failure_logs
    FOR ALL
    TO service_role
    USING (TRUE)
    WITH CHECK (TRUE);

-- Anon / authenticated users can only read
CREATE POLICY anon_read
    ON failure_logs
    FOR SELECT
    TO anon, authenticated
    USING (TRUE);

-- =============================================================================
-- Done! Check: Supabase Dashboard → Table Editor → failure_logs
-- =============================================================================
