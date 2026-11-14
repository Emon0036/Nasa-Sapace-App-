CREATE TABLE IF NOT EXISTS saved_mission_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_hash CHAR(64) NOT NULL,
    name VARCHAR(100) NOT NULL,
    site_id VARCHAR(80) NOT NULL,
    site_name VARCHAR(120) NOT NULL,
    launch_utc TIMESTAMPTZ NOT NULL,
    transit_days DOUBLE PRECISION NOT NULL CHECK (transit_days BETWEEN 1 AND 7),
    surface_days DOUBLE PRECISION NOT NULL CHECK (surface_days BETWEEN 1 AND 10),
    step_minutes DOUBLE PRECISION NOT NULL CHECK (step_minutes BETWEEN 5 AND 60),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS saved_mission_profiles_owner_created_idx
    ON saved_mission_profiles (owner_hash, created_at DESC);
