-- Character Transformation Engine
-- Integrated Platform Orchestrator V1.8
-- Status: MDL/DRV design specification; not empirically validated.

BEGIN;

CREATE TABLE IF NOT EXISTS ct_execution_runs_v18 (
    execution_id TEXT PRIMARY KEY,
    user_id TEXT,
    mode TEXT NOT NULL CHECK (mode IN ('RUNTIME','RESEARCH','REPLICATION','GENERALIZATION','REPORT')),
    root_input_hash TEXT NOT NULL,
    orchestrator_version TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN (
        'CREATED','RUNNING','PAUSED','BLOCKED','COMPLETED','FAILED','CANCELLED'
    )),
    current_stage TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS ct_execution_stages_v18 (
    execution_stage_id TEXT PRIMARY KEY,
    execution_id TEXT NOT NULL,
    stage_code TEXT NOT NULL,
    ordinal INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN (
        'PENDING','RUNNING','PASSED','BLOCKED','FAILED','SKIPPED'
    )),
    input_hash TEXT,
    output_hash TEXT,
    module_version TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    failure_code TEXT,
    reason TEXT
);

CREATE TABLE IF NOT EXISTS ct_event_bus_v18 (
    event_id TEXT PRIMARY KEY,
    execution_id TEXT,
    event_type TEXT NOT NULL,
    source_module TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    payload_json JSONB NOT NULL,
    input_hash TEXT,
    output_hash TEXT,
    provenance_record_id TEXT,
    causation_event_id TEXT,
    correlation_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ct_module_registry_v18 (
    module_id TEXT PRIMARY KEY,
    module_name TEXT NOT NULL,
    module_version TEXT NOT NULL,
    contract_version TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('REGISTERED','ACTIVE','DEPRECATED','BLOCKED')),
    capabilities_json JSONB NOT NULL,
    dependencies_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ct_schema_registry_v18 (
    schema_id TEXT PRIMARY KEY,
    schema_name TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    schema_hash TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('ACTIVE','DEPRECATED','BLOCKED')),
    compatibility_policy TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ct_rule_registry_v18 (
    rule_id TEXT PRIMARY KEY,
    rule_version TEXT NOT NULL,
    provenance_class TEXT NOT NULL CHECK (provenance_class IN ('EVD','MDL','HYP','RPT','DRV')),
    source_module TEXT NOT NULL,
    scope_json JSONB NOT NULL,
    rule_hash TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('REGISTERED','ACTIVE','SUSPENDED','RETIRED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ct_execution_artifacts_v18 (
    artifact_id TEXT PRIMARY KEY,
    execution_id TEXT NOT NULL,
    artifact_type TEXT NOT NULL,
    artifact_ref TEXT NOT NULL,
    artifact_hash TEXT,
    role TEXT NOT NULL CHECK (role IN (
        'INPUT','OUTPUT','EVIDENCE','LIMITATION','CONTRADICTION','REPORT'
    )),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ct_orchestrator_decisions_v18 (
    decision_id TEXT PRIMARY KEY,
    execution_id TEXT NOT NULL,
    decision_type TEXT NOT NULL CHECK (decision_type IN (
        'ROUTE','BLOCK','PAUSE','RESUME','COMPLETE','FAIL'
    )),
    decision TEXT NOT NULL,
    rule_id TEXT,
    rule_version TEXT,
    input_snapshot_hash TEXT NOT NULL,
    rationale TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ct_orchestrator_audit_v18 (
    audit_id TEXT PRIMARY KEY,
    execution_id TEXT NOT NULL,
    event_id TEXT,
    actor_type TEXT NOT NULL CHECK (actor_type IN ('SYSTEM','USER','RESEARCHER')),
    action TEXT NOT NULL,
    before_hash TEXT,
    after_hash TEXT,
    metadata_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE VIEW ct_execution_pipeline_status_v18 AS
SELECT
    e.execution_id,
    e.mode,
    e.status,
    e.current_stage,
    COUNT(s.execution_stage_id) AS stages,
    COUNT(*) FILTER (WHERE s.status='PASSED') AS passed_stages,
    COUNT(*) FILTER (WHERE s.status='BLOCKED') AS blocked_stages,
    COUNT(*) FILTER (WHERE s.status='FAILED') AS failed_stages
FROM ct_execution_runs_v18 e
LEFT JOIN ct_execution_stages_v18 s ON s.execution_id=e.execution_id
GROUP BY e.execution_id,e.mode,e.status,e.current_stage;

COMMIT;
