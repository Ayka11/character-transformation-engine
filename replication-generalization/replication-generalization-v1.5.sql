-- Character Transformation Engine
-- Replication & Generalization Engine V1.5
-- Status: MDL/DRV design specification; not empirically validated.

BEGIN;

CREATE TABLE IF NOT EXISTS ct_replication_specs (
    replication_spec_id TEXT PRIMARY KEY,
    source_claim_id TEXT NOT NULL,
    primary_outcome_id TEXT NOT NULL,
    criteria_json JSONB NOT NULL,
    protocol_fidelity_threshold NUMERIC,
    effect_compatibility_rule TEXT,
    direction_rule TEXT,
    data_quality_rule TEXT,
    version TEXT NOT NULL,
    provenance_record_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ct_replication_runs_v15 (
    replication_run_id TEXT PRIMARY KEY,
    replication_spec_id TEXT NOT NULL,
    source_result_node_id TEXT NOT NULL,
    target_result_node_id TEXT,
    independent_study_id TEXT NOT NULL,
    dataset_manifest_id TEXT NOT NULL,
    protocol_hash TEXT NOT NULL,
    input_hash TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN (
        'REGISTERED','RUNNING','QC_FAILED','COMPLETED','INDETERMINATE','FAILED'
    )),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS ct_replication_dimensions (
    replication_dimension_id TEXT PRIMARY KEY,
    replication_run_id TEXT NOT NULL,
    dimension_code TEXT NOT NULL,
    source_value_json JSONB NOT NULL,
    target_value_json JSONB NOT NULL,
    comparison_value NUMERIC,
    comparison_status TEXT NOT NULL CHECK (comparison_status IN (
        'MATCH','COMPATIBLE','DEVIATION','UNKNOWN','NOT_APPLICABLE'
    )),
    rule_id TEXT NOT NULL,
    provenance_record_id TEXT
);

CREATE TABLE IF NOT EXISTS ct_replication_outcomes (
    replication_outcome_id TEXT PRIMARY KEY,
    replication_run_id TEXT NOT NULL,
    outcome_id TEXT NOT NULL,
    source_estimate NUMERIC,
    target_estimate NUMERIC,
    source_effect_size NUMERIC,
    target_effect_size NUMERIC,
    source_ci_low NUMERIC,
    source_ci_high NUMERIC,
    target_ci_low NUMERIC,
    target_ci_high NUMERIC,
    direction_compatible BOOLEAN,
    effect_compatible BOOLEAN,
    interval_rule_met BOOLEAN,
    overall_outcome TEXT NOT NULL CHECK (overall_outcome IN (
        'REPLICATED','PARTIAL','NOT_REPLICATED','NOT_ESTIMABLE'
    )),
    rationale TEXT,
    provenance_record_id TEXT
);

CREATE TABLE IF NOT EXISTS ct_replication_assessments_v15 (
    assessment_id TEXT PRIMARY KEY,
    replication_run_id TEXT NOT NULL,
    criterion_code TEXT NOT NULL,
    observed_json JSONB NOT NULL,
    threshold_json JSONB NOT NULL,
    criterion_met BOOLEAN,
    assessment_status TEXT NOT NULL CHECK (assessment_status IN (
        'MET','NOT_MET','UNKNOWN','NOT_APPLICABLE'
    )),
    rationale TEXT,
    provenance_record_id TEXT
);

CREATE TABLE IF NOT EXISTS ct_generalization_specs (
    generalization_spec_id TEXT PRIMARY KEY,
    source_claim_id TEXT NOT NULL,
    source_population_json JSONB NOT NULL,
    target_population_json JSONB NOT NULL,
    source_context_json JSONB NOT NULL,
    target_context_json JSONB NOT NULL,
    transport_dimensions_json JSONB NOT NULL,
    acceptance_rules_json JSONB NOT NULL,
    version TEXT NOT NULL,
    provenance_record_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ct_generalization_runs_v15 (
    generalization_run_id TEXT PRIMARY KEY,
    generalization_spec_id TEXT NOT NULL,
    source_result_node_id TEXT NOT NULL,
    target_result_node_id TEXT,
    dataset_manifest_id TEXT NOT NULL,
    transport_analysis_version TEXT NOT NULL,
    input_hash TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN (
        'REGISTERED','RUNNING','COMPLETED','LIMITED','INDETERMINATE','FAILED'
    )),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS ct_transport_dimensions (
    transport_dimension_id TEXT PRIMARY KEY,
    generalization_run_id TEXT NOT NULL,
    dimension_code TEXT NOT NULL,
    source_value_json JSONB NOT NULL,
    target_value_json JSONB NOT NULL,
    transport_distance NUMERIC,
    transport_status TEXT NOT NULL CHECK (transport_status IN (
        'LOW','MODERATE','HIGH','UNKNOWN','NOT_APPLICABLE'
    )),
    justification TEXT,
    provenance_record_id TEXT
);

CREATE TABLE IF NOT EXISTS ct_generalization_results (
    generalization_result_id TEXT PRIMARY KEY,
    generalization_run_id TEXT NOT NULL,
    outcome_id TEXT NOT NULL,
    source_estimate NUMERIC,
    transported_estimate NUMERIC,
    transport_error NUMERIC,
    ci_low NUMERIC,
    ci_high NUMERIC,
    heterogeneity_statistic NUMERIC,
    heterogeneity_p_value NUMERIC,
    result_status TEXT NOT NULL CHECK (result_status IN (
        'GENERALIZABLE','LIMITED_GENERALIZABILITY','NOT_GENERALIZABLE','NOT_ESTIMABLE'
    )),
    rationale TEXT,
    provenance_record_id TEXT
);

CREATE TABLE IF NOT EXISTS ct_generalization_boundaries (
    boundary_id TEXT PRIMARY KEY,
    generalization_run_id TEXT NOT NULL,
    boundary_type TEXT NOT NULL CHECK (boundary_type IN (
        'POPULATION','CONTEXT','TASK','MEASUREMENT','INTERVENTION','TIME','DATA_QUALITY'
    )),
    boundary_definition TEXT NOT NULL,
    evidence_json JSONB NOT NULL,
    provenance_record_id TEXT
);

CREATE TABLE IF NOT EXISTS ct_replication_generalization_links (
    link_id TEXT PRIMARY KEY,
    replication_run_id TEXT,
    generalization_run_id TEXT,
    graph_edge_id TEXT,
    relation_code TEXT NOT NULL CHECK (relation_code IN (
        'REPLICATION_SUPPORTS_GENERALIZATION',
        'REPLICATION_LIMITS_GENERALIZATION',
        'GENERALIZATION_QUALIFIES_REPLICATION',
        'INDEPENDENT'
    )),
    rationale TEXT,
    provenance_record_id TEXT
);

CREATE TABLE IF NOT EXISTS ct_v15_decisions (
    decision_id TEXT PRIMARY KEY,
    claim_id TEXT NOT NULL,
    decision_type TEXT NOT NULL CHECK (decision_type IN (
        'REPLICATION_STATUS','GENERALIZATION_STATUS','CLAIM_BOUNDARY'
    )),
    decision_status TEXT NOT NULL,
    rule_id TEXT NOT NULL,
    supporting_run_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    limiting_run_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    explanation TEXT NOT NULL,
    provenance_record_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE VIEW ct_replication_summary_v15 AS
SELECT
    r.replication_run_id,
    r.independent_study_id,
    r.status,
    COUNT(o.replication_outcome_id) AS outcome_count,
    COUNT(*) FILTER (WHERE o.overall_outcome='REPLICATED') AS replicated_outcomes,
    COUNT(*) FILTER (WHERE o.overall_outcome='PARTIAL') AS partial_outcomes,
    COUNT(*) FILTER (WHERE o.overall_outcome='NOT_REPLICATED') AS nonreplicated_outcomes
FROM ct_replication_runs_v15 r
LEFT JOIN ct_replication_outcomes o
 ON o.replication_run_id=r.replication_run_id
GROUP BY r.replication_run_id, r.independent_study_id, r.status;

CREATE VIEW ct_generalization_summary_v15 AS
SELECT
    g.generalization_run_id,
    g.status,
    COUNT(r.generalization_result_id) AS outcome_count,
    COUNT(*) FILTER (WHERE r.result_status='GENERALIZABLE') AS generalizable_outcomes,
    COUNT(*) FILTER (WHERE r.result_status='LIMITED_GENERALIZABILITY') AS limited_outcomes,
    COUNT(*) FILTER (WHERE r.result_status='NOT_GENERALIZABLE') AS nongeneralizable_outcomes
FROM ct_generalization_runs_v15 g
LEFT JOIN ct_generalization_results r
 ON r.generalization_run_id=g.generalization_run_id
GROUP BY g.generalization_run_id, g.status;

COMMIT;
