-- Character Transformation Engine
-- Scientific Report & Decision Engine V1.6
-- Status: MDL/DRV design specification; not empirically validated.

BEGIN;

CREATE TABLE IF NOT EXISTS ct_report_specs_v16 (
    report_spec_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    section_order_json JSONB NOT NULL,
    rendering_rules_json JSONB NOT NULL,
    claim_language_rules_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ct_report_runs_v16 (
    report_run_id TEXT PRIMARY KEY,
    report_spec_id TEXT NOT NULL,
    study_id TEXT NOT NULL,
    analysis_run_id TEXT,
    replication_run_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    generalization_run_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    claim_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    source_manifest_hash TEXT NOT NULL,
    report_input_hash TEXT NOT NULL,
    report_output_hash TEXT,
    status TEXT NOT NULL CHECK (status IN (
        'REGISTERED','BUILDING','QC_PENDING','QC_PASSED','QC_FAILED','PUBLISHED','SUPERSEDED'
    )),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    published_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS ct_report_sections_v16 (
    report_section_id TEXT PRIMARY KEY,
    report_run_id TEXT NOT NULL,
    section_code TEXT NOT NULL,
    ordinal INTEGER NOT NULL,
    content_json JSONB NOT NULL,
    source_artifacts_json JSONB NOT NULL,
    derivation_rule_id TEXT,
    derivation_rule_version TEXT,
    evidence_status TEXT NOT NULL CHECK (evidence_status IN (
        'OBSERVATION','MEASUREMENT','DESCRIPTIVE_RESULT','ASSOCIATIONAL_RESULT',
        'INTERVENTION_RESULT','REPLICATED_RESULT','GENERALIZED_RESULT',
        'EVIDENCE_SUPPORTED','LIMITED','INDETERMINATE'
    )),
    limitations_json JSONB NOT NULL DEFAULT '[]'::jsonb
);

CREATE TABLE IF NOT EXISTS ct_report_claim_bindings_v16 (
    binding_id TEXT PRIMARY KEY,
    report_run_id TEXT NOT NULL,
    claim_id TEXT NOT NULL,
    claim_status TEXT NOT NULL,
    supporting_nodes_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    limiting_nodes_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    contradiction_nodes_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    allowed_language_rule_id TEXT NOT NULL,
    generated_statement TEXT,
    provenance_record_id TEXT
);

CREATE TABLE IF NOT EXISTS ct_report_decisions_v16 (
    decision_id TEXT PRIMARY KEY,
    report_run_id TEXT NOT NULL,
    decision_type TEXT NOT NULL CHECK (decision_type IN (
        'CLAIM_LANGUAGE','REPORT_STATUS','PUBLICATION_READINESS','LIMITATION_REQUIRED'
    )),
    decision TEXT NOT NULL,
    rule_id TEXT NOT NULL,
    inputs_json JSONB NOT NULL,
    rationale TEXT NOT NULL,
    provenance_record_id TEXT
);

CREATE TABLE IF NOT EXISTS ct_report_qc_v16 (
    report_qc_id TEXT PRIMARY KEY,
    report_run_id TEXT NOT NULL,
    check_code TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('PASS','FAIL','WARNING','NOT_APPLICABLE')),
    observed_json JSONB NOT NULL,
    expected_json JSONB,
    message TEXT,
    checked_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ct_report_provenance_v16 (
    report_provenance_id TEXT PRIMARY KEY,
    report_run_id TEXT NOT NULL,
    artifact_type TEXT NOT NULL,
    artifact_id TEXT NOT NULL,
    artifact_hash TEXT,
    relationship TEXT NOT NULL CHECK (relationship IN (
        'SOURCE','DERIVED_FROM','LIMITS','SUPPORTS','CONTRADICTS','QUALIFIES'
    )),
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE VIEW ct_report_status_v16 AS
SELECT
    r.report_run_id,
    r.study_id,
    r.status,
    COUNT(DISTINCT s.report_section_id) AS section_count,
    COUNT(DISTINCT q.report_qc_id) FILTER (WHERE q.status='PASS') AS qc_passes,
    COUNT(DISTINCT q.report_qc_id) FILTER (WHERE q.status='FAIL') AS qc_failures,
    COUNT(DISTINCT b.binding_id) AS claim_bindings
FROM ct_report_runs_v16 r
LEFT JOIN ct_report_sections_v16 s ON s.report_run_id=r.report_run_id
LEFT JOIN ct_report_qc_v16 q ON q.report_run_id=r.report_run_id
LEFT JOIN ct_report_claim_bindings_v16 b ON b.report_run_id=r.report_run_id
GROUP BY r.report_run_id,r.study_id,r.status;

COMMIT;
