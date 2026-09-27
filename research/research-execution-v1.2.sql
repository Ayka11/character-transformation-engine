
BEGIN;

-- ============================================================
-- RESEARCH EXECUTION LAYER V1.2
-- Study -> Experiment -> Trial -> QC -> Statistics -> Claim
-- ============================================================

CREATE TABLE IF NOT EXISTS ct_studies (
    study_id UUID PRIMARY KEY,
    study_code TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    research_question TEXT NOT NULL,
    hypothesis_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    design_type TEXT NOT NULL,
    protocol_version TEXT NOT NULL,
    preregistration_ref TEXT,
    population_definition JSONB NOT NULL,
    inclusion_criteria JSONB NOT NULL,
    exclusion_criteria JSONB NOT NULL,
    primary_outcomes JSONB NOT NULL,
    secondary_outcomes JSONB NOT NULL DEFAULT '[]'::jsonb,
    status TEXT NOT NULL CHECK (
        status IN ('DRAFT','REGISTERED','RUNNING','CLOSED','ANALYSIS','PUBLISHED')
    ),
    provenance TEXT NOT NULL DEFAULT 'EXP',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ct_experiments (
    experiment_id UUID PRIMARY KEY,
    study_id UUID NOT NULL REFERENCES ct_studies(study_id),
    experiment_code TEXT NOT NULL,
    intervention_spec JSONB NOT NULL,
    comparator_spec JSONB,
    randomization_spec JSONB,
    blinding_spec JSONB,
    duration_days INT,
    measurement_schedule JSONB NOT NULL,
    analysis_plan JSONB NOT NULL,
    seed BIGINT,
    software_version TEXT NOT NULL,
    status TEXT NOT NULL CHECK (
        status IN ('PLANNED','ACTIVE','COMPLETED','TERMINATED')
    ),
    UNIQUE(study_id, experiment_code)
);

CREATE TABLE IF NOT EXISTS ct_experiment_arms (
    arm_id UUID PRIMARY KEY,
    experiment_id UUID NOT NULL REFERENCES ct_experiments(experiment_id),
    arm_code TEXT NOT NULL,
    arm_type TEXT NOT NULL CHECK (
        arm_type IN ('CONTROL','INTERVENTION','COMPARATOR','OTHER')
    ),
    intervention JSONB,
    target_level CHAR(1),
    sample_target INT,
    UNIQUE(experiment_id, arm_code)
);

CREATE TABLE IF NOT EXISTS ct_participants (
    participant_id UUID PRIMARY KEY,
    study_id UUID NOT NULL REFERENCES ct_studies(study_id),
    external_participant_code TEXT NOT NULL,
    eligibility_status TEXT NOT NULL,
    consent_status TEXT NOT NULL,
    enrollment_date DATE,
    withdrawal_date DATE,
    demographic_snapshot JSONB,
    baseline_snapshot_id UUID,
    provenance TEXT NOT NULL DEFAULT 'EXP',
    UNIQUE(study_id, external_participant_code)
);

CREATE TABLE IF NOT EXISTS ct_participant_assignments (
    assignment_id UUID PRIMARY KEY,
    participant_id UUID NOT NULL REFERENCES ct_participants(participant_id),
    arm_id UUID NOT NULL REFERENCES ct_experiment_arms(arm_id),
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    assignment_method TEXT NOT NULL,
    randomization_seed BIGINT,
    status TEXT NOT NULL DEFAULT 'ACTIVE'
);

CREATE TABLE IF NOT EXISTS ct_trials (
    trial_id UUID PRIMARY KEY,
    experiment_id UUID NOT NULL REFERENCES ct_experiments(experiment_id),
    participant_id UUID NOT NULL REFERENCES ct_participants(participant_id),
    arm_id UUID REFERENCES ct_experiment_arms(arm_id),
    trial_number INT NOT NULL,
    trial_time TIMESTAMPTZ NOT NULL,
    task_id TEXT NOT NULL,
    condition JSONB NOT NULL,
    stimulus JSONB,
    response JSONB,
    outcome JSONB,
    duration_ms INT,
    validity_status TEXT NOT NULL DEFAULT 'PENDING',
    raw_payload JSONB,
    trial_hash TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS ct_qc_runs (
    qc_run_id UUID PRIMARY KEY,
    study_id UUID NOT NULL REFERENCES ct_studies(study_id),
    experiment_id UUID REFERENCES ct_experiments(experiment_id),
    executed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    qc_version TEXT NOT NULL,
    checks JSONB NOT NULL,
    exclusions JSONB NOT NULL DEFAULT '[]'::jsonb,
    warnings JSONB NOT NULL DEFAULT '[]'::jsonb,
    passed BOOLEAN NOT NULL,
    input_hash TEXT NOT NULL,
    output_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ct_analysis_runs (
    analysis_run_id UUID PRIMARY KEY,
    study_id UUID NOT NULL REFERENCES ct_studies(study_id),
    experiment_id UUID REFERENCES ct_experiments(experiment_id),
    qc_run_id UUID REFERENCES ct_qc_runs(qc_run_id),
    analysis_version TEXT NOT NULL,
    statistical_plan JSONB NOT NULL,
    dataset_definition JSONB NOT NULL,
    model_specification JSONB NOT NULL,
    random_seed BIGINT,
    executed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    input_hash TEXT NOT NULL,
    output_hash TEXT NOT NULL,
    status TEXT NOT NULL CHECK (
        status IN ('PLANNED','RUNNING','COMPLETED','FAILED')
    )
);

CREATE TABLE IF NOT EXISTS ct_statistical_results (
    result_id UUID PRIMARY KEY,
    analysis_run_id UUID NOT NULL REFERENCES ct_analysis_runs(analysis_run_id),
    outcome_id TEXT NOT NULL,
    estimator TEXT NOT NULL,
    estimate NUMERIC,
    standard_error NUMERIC,
    confidence_interval JSONB,
    p_value NUMERIC,
    effect_size JSONB,
    sample_size INT,
    missing_count INT,
    multiplicity_adjustment TEXT,
    interpretation TEXT,
    result_status TEXT NOT NULL,
    provenance TEXT NOT NULL DEFAULT 'EXP'
);

CREATE TABLE IF NOT EXISTS ct_generalization_runs (
    generalization_id UUID PRIMARY KEY,
    source_analysis_run_id UUID NOT NULL REFERENCES ct_analysis_runs(analysis_run_id),
    target_population JSONB NOT NULL,
    target_context JSONB NOT NULL,
    transport_method TEXT NOT NULL,
    predicted_effect JSONB,
    observed_effect JSONB,
    transport_error JSONB,
    status TEXT NOT NULL,
    provenance TEXT NOT NULL DEFAULT 'EXP'
);

CREATE TABLE IF NOT EXISTS ct_replication_runs (
    replication_id UUID PRIMARY KEY,
    source_claim_id TEXT NOT NULL,
    replication_study_id UUID NOT NULL REFERENCES ct_studies(study_id),
    replication_protocol_version TEXT NOT NULL,
    preregistered BOOLEAN NOT NULL DEFAULT FALSE,
    result_summary JSONB NOT NULL,
    replication_status TEXT NOT NULL,
    deviation_log JSONB NOT NULL DEFAULT '[]'::jsonb,
    provenance TEXT NOT NULL DEFAULT 'EXP'
);

CREATE TABLE IF NOT EXISTS ct_claim_graph_edges (
    edge_id UUID PRIMARY KEY,
    source_entity_type TEXT NOT NULL,
    source_entity_id TEXT NOT NULL,
    relation TEXT NOT NULL,
    target_entity_type TEXT NOT NULL,
    target_entity_id TEXT NOT NULL,
    evidence_strength JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------
-- Canonical research state machine
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS ct_research_state_transitions (
    transition_id BIGSERIAL PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    from_state TEXT,
    to_state TEXT NOT NULL,
    actor TEXT NOT NULL,
    reason TEXT,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata JSONB
);

-- ------------------------------------------------------------
-- Dataset manifests: exact dataset used in every analysis
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS ct_dataset_manifests (
    dataset_manifest_id UUID PRIMARY KEY,
    analysis_run_id UUID REFERENCES ct_analysis_runs(analysis_run_id),
    dataset_version TEXT NOT NULL,
    source_tables JSONB NOT NULL,
    row_count INT NOT NULL,
    variable_schema JSONB NOT NULL,
    inclusion_filter TEXT,
    exclusion_filter TEXT,
    checksum TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------
-- Automated report specification
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS ct_research_reports (
    report_id UUID PRIMARY KEY,
    study_id UUID NOT NULL REFERENCES ct_studies(study_id),
    analysis_run_id UUID REFERENCES ct_analysis_runs(analysis_run_id),
    report_version TEXT NOT NULL,
    report_status TEXT NOT NULL,
    generated_at TIMESTAMPTZ,
    sections JSONB NOT NULL,
    provenance JSONB NOT NULL,
    output_checksum TEXT
);

-- ------------------------------------------------------------
-- Useful views
-- ------------------------------------------------------------

CREATE OR REPLACE VIEW ct_trial_qc_summary AS
SELECT
    experiment_id,
    participant_id,
    COUNT(*) AS total_trials,
    COUNT(*) FILTER (WHERE validity_status = 'VALID') AS valid_trials,
    COUNT(*) FILTER (WHERE validity_status = 'INVALID') AS invalid_trials,
    COUNT(*) FILTER (WHERE validity_status = 'PENDING') AS pending_trials
FROM ct_trials
GROUP BY experiment_id, participant_id;

CREATE OR REPLACE VIEW ct_research_pipeline_status AS
SELECT
    s.study_id,
    s.study_code,
    s.status AS study_status,
    COUNT(DISTINCT e.experiment_id) AS experiments,
    COUNT(DISTINCT p.participant_id) AS participants,
    COUNT(DISTINCT t.trial_id) AS trials,
    COUNT(DISTINCT a.analysis_run_id) AS analyses
FROM ct_studies s
LEFT JOIN ct_experiments e ON e.study_id=s.study_id
LEFT JOIN ct_participants p ON p.study_id=s.study_id
LEFT JOIN ct_trials t ON t.experiment_id=e.experiment_id
LEFT JOIN ct_analysis_runs a ON a.study_id=s.study_id
GROUP BY s.study_id, s.study_code, s.status;

COMMIT;
