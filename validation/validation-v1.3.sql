-- Character Transformation Engine
-- Validation & Analytics Engine V1.3
-- Status: MDL/DRV design specification; not empirically validated.

BEGIN;

CREATE TABLE IF NOT EXISTS ct_validation_specs (
    validation_spec_id TEXT PRIMARY KEY,
    outcome_type TEXT NOT NULL,
    method_family TEXT NOT NULL,
    estimator TEXT NOT NULL,
    assumptions_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    missing_data_policy TEXT NOT NULL,
    effect_size_family TEXT,
    ci_method TEXT,
    alpha NUMERIC(8,6) NOT NULL DEFAULT 0.05,
    multiplicity_method TEXT,
    version TEXT NOT NULL,
    provenance_record_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ct_validation_runs (
    validation_run_id TEXT PRIMARY KEY,
    study_id TEXT NOT NULL,
    experiment_id TEXT,
    analysis_run_id TEXT,
    validation_spec_id TEXT NOT NULL,
    dataset_manifest_id TEXT NOT NULL,
    input_hash TEXT NOT NULL,
    algorithm_version TEXT NOT NULL,
    random_seed BIGINT,
    status TEXT NOT NULL CHECK (status IN ('REGISTERED','RUNNING','QC_FAILED','COMPLETED','FAILED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS ct_outcome_results (
    outcome_result_id TEXT PRIMARY KEY,
    validation_run_id TEXT NOT NULL,
    outcome_id TEXT NOT NULL,
    contrast_id TEXT,
    n_total INTEGER,
    n_analyzed INTEGER,
    estimate NUMERIC,
    standard_error NUMERIC,
    ci_low NUMERIC,
    ci_high NUMERIC,
    p_value NUMERIC,
    adjusted_p_value NUMERIC,
    effect_size NUMERIC,
    effect_size_type TEXT,
    missing_fraction NUMERIC,
    assumptions_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    result_status TEXT NOT NULL CHECK (result_status IN ('VALID','LIMITED','INVALID','NOT_ESTIMABLE')),
    interpretation_code TEXT,
    provenance_record_id TEXT
);

CREATE TABLE IF NOT EXISTS ct_longitudinal_results (
    longitudinal_result_id TEXT PRIMARY KEY,
    validation_run_id TEXT NOT NULL,
    outcome_id TEXT NOT NULL,
    participant_count INTEGER,
    baseline_mean NUMERIC,
    final_mean NUMERIC,
    absolute_change NUMERIC,
    relative_change NUMERIC,
    standardized_change NUMERIC,
    ci_low NUMERIC,
    ci_high NUMERIC,
    p_value NUMERIC,
    missing_fraction NUMERIC,
    model_family TEXT,
    result_status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ct_replication_criteria (
    replication_criterion_id TEXT PRIMARY KEY,
    claim_id TEXT,
    criterion_code TEXT NOT NULL,
    threshold_json JSONB NOT NULL,
    version TEXT NOT NULL,
    provenance_record_id TEXT
);

CREATE TABLE IF NOT EXISTS ct_replication_assessments (
    replication_assessment_id TEXT PRIMARY KEY,
    replication_run_id TEXT NOT NULL,
    criterion_id TEXT NOT NULL,
    observed_json JSONB NOT NULL,
    criterion_met BOOLEAN NOT NULL,
    rationale TEXT,
    provenance_record_id TEXT
);

CREATE TABLE IF NOT EXISTS ct_missing_data_assessments (
    missing_data_assessment_id TEXT PRIMARY KEY,
    validation_run_id TEXT NOT NULL,
    variable_id TEXT NOT NULL,
    missing_count INTEGER NOT NULL,
    observed_count INTEGER NOT NULL,
    missing_fraction NUMERIC NOT NULL,
    pattern_code TEXT,
    handling_code TEXT NOT NULL,
    sensitivity_required BOOLEAN NOT NULL DEFAULT FALSE,
    provenance_record_id TEXT
);

CREATE TABLE IF NOT EXISTS ct_claim_derivations (
    claim_derivation_id TEXT PRIMARY KEY,
    validation_run_id TEXT NOT NULL,
    outcome_result_id TEXT,
    claim_id TEXT NOT NULL,
    derivation_rule_id TEXT NOT NULL,
    source_status TEXT NOT NULL,
    allowed_claim_level TEXT NOT NULL,
    prohibited_inference_codes JSONB NOT NULL DEFAULT '[]'::jsonb,
    provenance_record_id TEXT
);

CREATE TABLE IF NOT EXISTS ct_analytics_qc (
    analytics_qc_id TEXT PRIMARY KEY,
    validation_run_id TEXT NOT NULL,
    check_code TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('INFO','WARNING','ERROR')),
    passed BOOLEAN NOT NULL,
    observed_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ct_analysis_sensitivity (
    sensitivity_id TEXT PRIMARY KEY,
    validation_run_id TEXT NOT NULL,
    scenario_code TEXT NOT NULL,
    parameter_json JSONB NOT NULL,
    estimate NUMERIC,
    ci_low NUMERIC,
    ci_high NUMERIC,
    p_value NUMERIC,
    effect_size NUMERIC,
    interpretation_delta TEXT,
    provenance_record_id TEXT
);

CREATE VIEW ct_validation_result_summary AS
SELECT vr.validation_run_id, vr.study_id, vr.experiment_id, vr.status,
       COUNT(orx.outcome_result_id) AS outcome_count,
       COUNT(*) FILTER (WHERE orx.result_status = 'VALID') AS valid_count,
       COUNT(*) FILTER (WHERE orx.result_status = 'LIMITED') AS limited_count,
       COUNT(*) FILTER (WHERE orx.result_status = 'INVALID') AS invalid_count
FROM ct_validation_runs vr
LEFT JOIN ct_outcome_results orx ON orx.validation_run_id = vr.validation_run_id
GROUP BY vr.validation_run_id, vr.study_id, vr.experiment_id, vr.status;

COMMIT;
