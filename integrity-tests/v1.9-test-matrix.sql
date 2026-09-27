-- V1.9 integrity test matrix
-- These rows describe executable test cases for the implementation test runner.
-- Status: MDL/DRV; synthetic/non-evidence.

BEGIN;

CREATE TABLE IF NOT EXISTS ct_integrity_test_cases_v19 (
    test_id TEXT PRIMARY KEY,
    suite TEXT NOT NULL,
    input_json JSONB NOT NULL,
    expected_json JSONB NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('BLOCKING','MAJOR','MINOR')),
    status TEXT NOT NULL DEFAULT 'REGISTERED' CHECK (
        status IN ('REGISTERED','PASS','FAIL','SKIPPED')
    ),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ct_integrity_test_runs_v19 (
    test_run_id TEXT PRIMARY KEY,
    suite TEXT NOT NULL,
    implementation_version TEXT NOT NULL,
    environment_json JSONB NOT NULL,
    status TEXT NOT NULL CHECK (
        status IN ('RUNNING','PASS','FAIL','INDETERMINATE')
    ),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS ct_integrity_test_results_v19 (
    result_id TEXT PRIMARY KEY,
    test_run_id TEXT NOT NULL,
    test_id TEXT NOT NULL,
    observed_json JSONB NOT NULL,
    expected_json JSONB NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('PASS','FAIL','SKIPPED')),
    failure_code TEXT,
    evidence_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ct_integrity_artifact_checks_v19 (
    check_id TEXT PRIMARY KEY,
    test_run_id TEXT NOT NULL,
    artifact_type TEXT NOT NULL,
    artifact_ref TEXT NOT NULL,
    artifact_hash TEXT,
    check_code TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('PASS','FAIL','WARNING')),
    details_json JSONB NOT NULL
);

CREATE VIEW ct_integrity_run_summary_v19 AS
SELECT
    r.test_run_id,
    r.suite,
    r.status,
    COUNT(t.result_id) AS tests,
    COUNT(*) FILTER (WHERE t.status='PASS') AS passes,
    COUNT(*) FILTER (WHERE t.status='FAIL') AS failures,
    COUNT(*) FILTER (WHERE t.status='SKIPPED') AS skipped
FROM ct_integrity_test_runs_v19 r
LEFT JOIN ct_integrity_test_results_v19 t ON t.test_run_id=r.test_run_id
GROUP BY r.test_run_id,r.suite,r.status;

COMMIT;
