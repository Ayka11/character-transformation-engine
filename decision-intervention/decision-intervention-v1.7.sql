-- Character Transformation Engine
-- Integrated Decision & Intervention Engine V1.7
-- Status: MDL/DRV design specification; not empirically validated.

BEGIN;

CREATE TABLE IF NOT EXISTS ct_intervention_rules_v17 (
    rule_id TEXT PRIMARY KEY,
    rule_name TEXT NOT NULL,
    provenance_class TEXT NOT NULL CHECK (provenance_class IN ('EVD','MDL','HYP','RPT','DRV')),
    rule_version TEXT NOT NULL,
    eligible_domains_json JSONB NOT NULL,
    contraindications_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    required_inputs_json JSONB NOT NULL,
    decision_logic_json JSONB NOT NULL,
    evidence_scope_json JSONB NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('DRAFT','REGISTERED','ACTIVE','SUSPENDED','RETIRED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ct_intervention_assignments_v17 (
    assignment_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    rule_id TEXT NOT NULL,
    rule_version TEXT NOT NULL,
    source_assessment_id TEXT,
    source_claim_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    selected_level TEXT NOT NULL CHECK (selected_level IN ('A','B','C','D','E')),
    selection_reason_json JSONB NOT NULL,
    safety_gate_status TEXT NOT NULL CHECK (safety_gate_status IN ('PASS','HOLD','BLOCK')),
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ct_intervention_sessions_v17 (
    session_id TEXT PRIMARY KEY,
    assignment_id TEXT NOT NULL,
    planned_load_json JSONB NOT NULL,
    executed_load_json JSONB,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    completion_status TEXT NOT NULL CHECK (completion_status IN (
        'PLANNED','STARTED','COMPLETED','PARTIAL','CANCELLED','STOPPED'
    )),
    stop_reason TEXT
);

CREATE TABLE IF NOT EXISTS ct_intervention_measurements_v17 (
    measurement_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    metric_id TEXT NOT NULL,
    value_numeric NUMERIC,
    value_text TEXT,
    missing_reason TEXT,
    observed_at TIMESTAMPTZ NOT NULL,
    provenance_record_id TEXT,
    CHECK (value_numeric IS NOT NULL OR value_text IS NOT NULL OR missing_reason IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS ct_intervention_responses_v17 (
    response_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    response_dimension TEXT NOT NULL CHECK (response_dimension IN (
        'TARGET_TRAIT','SUPPORTING_STATE','BEHAVIOR','SAFETY','ADHERENCE','CAPACITY'
    )),
    baseline_value NUMERIC,
    post_value NUMERIC,
    change_value NUMERIC,
    uncertainty_json JSONB,
    response_status TEXT NOT NULL CHECK (response_status IN (
        'IMPROVED','STABLE','DEGRADED','UNKNOWN','NOT_ESTIMABLE'
    )),
    provenance_record_id TEXT
);

CREATE TABLE IF NOT EXISTS ct_adaptation_decisions_v17 (
    adaptation_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    assignment_id TEXT NOT NULL,
    prior_level TEXT NOT NULL,
    next_level TEXT NOT NULL,
    decision TEXT NOT NULL CHECK (decision IN (
        'CONTINUE','ADJUST','HOLD','DEESCALATE','STOP','INSUFFICIENT_DATA'
    )),
    rule_id TEXT NOT NULL,
    input_snapshot_hash TEXT NOT NULL,
    explanation TEXT NOT NULL,
    safety_status TEXT NOT NULL CHECK (safety_status IN ('SAFE','CAUTION','BLOCKED','UNKNOWN')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ct_intervention_outcome_links_v17 (
    link_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    research_result_node_id TEXT,
    claim_id TEXT,
    relation TEXT NOT NULL CHECK (relation IN (
        'GENERATES_OBSERVATION',
        'CONTRIBUTES_TO_ANALYSIS',
        'SUPPORTS_CLAIM',
        'LIMITS_CLAIM',
        'CONTRADICTS_CLAIM'
    )),
    provenance_record_id TEXT
);

CREATE TABLE IF NOT EXISTS ct_intervention_audit_v17 (
    audit_id TEXT PRIMARY KEY,
    user_id TEXT,
    assignment_id TEXT,
    event_type TEXT NOT NULL,
    rule_version TEXT,
    input_hash TEXT,
    output_hash TEXT,
    actor_type TEXT NOT NULL CHECK (actor_type IN ('USER','SYSTEM','RESEARCHER')),
    event_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE VIEW ct_intervention_runtime_summary_v17 AS
SELECT
    a.assignment_id,
    a.user_id,
    a.rule_id,
    a.selected_level,
    a.safety_gate_status,
    COUNT(s.session_id) AS session_count,
    COUNT(*) FILTER (WHERE s.completion_status='COMPLETED') AS completed_sessions,
    COUNT(*) FILTER (WHERE s.completion_status='STOPPED') AS stopped_sessions
FROM ct_intervention_assignments_v17 a
LEFT JOIN ct_intervention_sessions_v17 s ON s.assignment_id=a.assignment_id
GROUP BY a.assignment_id,a.user_id,a.rule_id,a.selected_level,a.safety_gate_status;

COMMIT;
