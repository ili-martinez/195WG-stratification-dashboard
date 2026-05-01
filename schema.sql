-- ============================================================
-- schema.sql
-- Run this in Supabase SQL Editor to create all tables.
-- ============================================================

-- Tenants
CREATE TABLE IF NOT EXISTS tenants (
    id         SERIAL PRIMARY KEY,
    name       TEXT NOT NULL UNIQUE,
    short_code TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Users
CREATE TABLE IF NOT EXISTS users (
    id               SERIAL PRIMARY KEY,
    tenant_id        INTEGER REFERENCES tenants(id) ON DELETE CASCADE,
    username         TEXT NOT NULL UNIQUE,
    password         TEXT NOT NULL,
    password_history JSONB DEFAULT '[]',
    role             TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('super_admin','admin','user')),
    title            TEXT DEFAULT '',
    first_name       TEXT DEFAULT '',
    last_name        TEXT DEFAULT '',
    rank             TEXT DEFAULT '',
    flight           TEXT DEFAULT '',
    disabled         BOOLEAN DEFAULT FALSE,
    lockout_until    TIMESTAMPTZ,
    consec_failures  INTEGER DEFAULT 0,
    daily_failures   INTEGER DEFAULT 0,
    daily_fail_date  TEXT DEFAULT '',
    created_at       TIMESTAMPTZ DEFAULT NOW()
);

-- Sessions
CREATE TABLE IF NOT EXISTS sessions (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER REFERENCES users(id) ON DELETE CASCADE,
    token       TEXT NOT NULL UNIQUE,
    ip_address  TEXT DEFAULT 'unknown',
    expires_at  TIMESTAMPTZ NOT NULL,
    last_active TIMESTAMPTZ NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Members (career data)
CREATE TABLE IF NOT EXISTS members (
    id                SERIAL PRIMARY KEY,
    tenant_id         INTEGER REFERENCES tenants(id) ON DELETE CASCADE,
    rank              TEXT DEFAULT '',
    first_name        TEXT DEFAULT '',
    last_name         TEXT DEFAULT '',
    flight            TEXT DEFAULT '',
    last_eval         TEXT DEFAULT '',
    promo_recomm      TEXT DEFAULT '',
    last_aca          TEXT DEFAULT '',
    doe               TEXT DEFAULT '',
    tig               TEXT DEFAULT '',
    dor               TEXT DEFAULT '',
    tis               TEXT DEFAULT '',
    skill_level       TEXT DEFAULT '',
    fitness           TEXT DEFAULT '',
    pme_als           TEXT DEFAULT 'No',
    pme_ncoa          TEXT DEFAULT 'No',
    pme_sncoa         TEXT DEFAULT 'No',
    pme_ejpme1        TEXT DEFAULT 'No',
    pme_ejpme2        TEXT DEFAULT 'No',
    pme_sncoe         TEXT DEFAULT 'No',
    pme_edo           TEXT DEFAULT 'No',
    pme_cmsoc         TEXT DEFAULT 'No',
    pme_clc           TEXT DEFAULT 'No',
    pme_dsca1         TEXT DEFAULT 'No',
    pme_dsca2         TEXT DEFAULT 'No',
    edu_associates    TEXT DEFAULT 'No',
    edu_bachelors     TEXT DEFAULT 'No',
    edu_masters       TEXT DEFAULT 'No',
    edu_doctorate     TEXT DEFAULT 'No',
    assignments       TEXT DEFAULT '',
    assignments_date  TEXT DEFAULT '',
    awards_decs       TEXT DEFAULT '',
    awards_decs_date  TEXT DEFAULT '',
    prof_org_mbr      TEXT DEFAULT '',
    leadership_roles  TEXT DEFAULT '',
    supervisor_notes  TEXT DEFAULT '',
    ratee_notes       TEXT DEFAULT '',
    last_edit         TEXT DEFAULT '',
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

-- Bench layouts (per tenant)
CREATE TABLE IF NOT EXISTS bench_layouts (
    id          SERIAL PRIMARY KEY,
    tenant_id   INTEGER REFERENCES tenants(id) ON DELETE CASCADE,
    member_name TEXT NOT NULL,
    x           INTEGER DEFAULT 0,
    y           INTEGER DEFAULT 0,
    UNIQUE(tenant_id, member_name)
);

-- ── Indexes ──────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_users_tenant    ON users(tenant_id);
CREATE INDEX IF NOT EXISTS idx_users_username  ON users(username);
CREATE INDEX IF NOT EXISTS idx_members_tenant  ON members(tenant_id);
CREATE INDEX IF NOT EXISTS idx_sessions_token  ON sessions(token);
CREATE INDEX IF NOT EXISTS idx_sessions_user   ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_bench_tenant    ON bench_layouts(tenant_id);

-- ── Row Level Security (optional but recommended) ─────────────────────────────
-- Disable RLS for now since we handle tenant isolation in Python.
-- Enable later for additional database-level security.
ALTER TABLE tenants      DISABLE ROW LEVEL SECURITY;
ALTER TABLE users        DISABLE ROW LEVEL SECURITY;
ALTER TABLE sessions     DISABLE ROW LEVEL SECURITY;
ALTER TABLE members      DISABLE ROW LEVEL SECURITY;
ALTER TABLE bench_layouts DISABLE ROW LEVEL SECURITY;

-- ── Initial tenant data ───────────────────────────────────────────────────────
INSERT INTO tenants (name, short_code) VALUES
    ('195 ISRG',   '195ISRG'),
    ('149 IS',     '149IS'),
    ('222 ISS',    '222ISS'),
    ('234 IS',     '234IS'),
    ('195 OG',     '195OG'),
    ('216 EWS',    '216EWS'),
    ('261 COS',    '261COS'),
    ('148 SOPS',   '148SOPS'),
    ('147 CBCS',   '147CBCS'),
    ('195 WG HQ',  '195WGHQ')
ON CONFLICT (name) DO NOTHING;

-- ── Initial super admin account ───────────────────────────────────────────────
-- Password: SuperAdmin@149IS!1 (change immediately after first login)
-- bcrypt hash of the above password:
INSERT INTO users (tenant_id, username, password, role, first_name, last_name)
VALUES (
    NULL,
    'superadmin',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TxIT3JsZqCCEBq0VdPZ7l3pjWb.m',
    'super_admin',
    'Super',
    'Admin'
) ON CONFLICT (username) DO NOTHING;
