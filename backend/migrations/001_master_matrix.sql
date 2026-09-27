-- Master Matrix V1.0 persistence contract.
-- PostgreSQL-oriented schema. This file defines persistence; it does not imply
-- that a database connection is configured in the current executable baseline.

CREATE TABLE IF NOT EXISTS matrix_versions (
    version TEXT PRIMARY KEY,
    status TEXT NOT NULL CHECK (status IN ('DRAFT','ACTIVE','RETIRED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS matrix_items (
    item_id TEXT PRIMARY KEY,
    matrix_version TEXT NOT NULL REFERENCES matrix_versions(version),
    domain_code TEXT NOT NULL CHECK (domain_code IN ('P1','P2','P3','P4','P5')),
    name TEXT NOT NULL,
    measurement_kind TEXT NOT NULL CHECK (
        measurement_kind IN ('state','trait','modeled','value','behavior')
    ),
    scale TEXT NOT NULL,
    direction TEXT NOT NULL,
    provenance_tag TEXT NOT NULL CHECK (
        provenance_tag IN ('EVD','MDL','HYP','RPT','DRV','OBS','EXT','EXP')
    ),
    notes TEXT NOT NULL DEFAULT '',
    UNIQUE(matrix_version, domain_code, name)
);

CREATE TABLE IF NOT EXISTS matrix_adaptive_levels (
    level_code TEXT PRIMARY KEY CHECK (level_code IN ('A','B','C','D','E')),
    level_name TEXT NOT NULL,
    promotion_gate TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sprint_templates (
    template_id TEXT PRIMARY KEY,
    matrix_version TEXT NOT NULL REFERENCES matrix_versions(version),
    duration_days INTEGER NOT NULL CHECK (duration_days > 0),
    safety_precedes_promotion BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS sprint_requirements (
    template_id TEXT NOT NULL REFERENCES sprint_templates(template_id),
    requirement_code TEXT NOT NULL,
    PRIMARY KEY(template_id, requirement_code)
);

CREATE INDEX IF NOT EXISTS idx_matrix_items_domain
    ON matrix_items(matrix_version, domain_code);
