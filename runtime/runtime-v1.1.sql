-- ============================================================
-- CHARACTER TRANSFORMATION & SOCIAL COMPATIBILITY ENGINE
-- Runtime Layer V1.1
-- Purpose: execute Master Matrix V1.0 without losing provenance.
-- ============================================================

BEGIN;

-- ---------- 1. Stable user identity / profile ----------
CREATE TABLE IF NOT EXISTS ct_users (
    user_id UUID PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    profile_version INT NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS ct_profile_snapshots (
    profile_snapshot_id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES ct_users(user_id),
    measured_at TIMESTAMPTZ NOT NULL,
    valid_from DATE NOT NULL,
    valid_to DATE,
    source TEXT NOT NULL,
    instrument TEXT,
    version TEXT,
    provenance TEXT NOT NULL,
    data JSONB NOT NULL,
    qc_status TEXT NOT NULL DEFAULT 'PENDING',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Trait values are deliberately separated from daily STATE.
CREATE TABLE IF NOT EXISTS ct_trait_scores (
    score_id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES ct_users(user_id),
    node_id TEXT NOT NULL,
    score NUMERIC NOT NULL CHECK (score >= 0 AND score <= 100),
    scale_min NUMERIC NOT NULL DEFAULT 0,
    scale_max NUMERIC NOT NULL DEFAULT 100,
    measured_at TIMESTAMPTZ NOT NULL,
    instrument TEXT,
    provenance TEXT NOT NULL,
    profile_snapshot_id UUID REFERENCES ct_profile_snapshots(profile_snapshot_id),
    confidence NUMERIC CHECK (confidence >= 0 AND confidence <= 1),
    qc_status TEXT NOT NULL DEFAULT 'PENDING'
);

-- ---------- 2. Daily state ----------
CREATE TABLE IF NOT EXISTS ct_daily_state (
    daily_state_id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES ct_users(user_id),
    state_date DATE NOT NULL,
    sleep_hours NUMERIC CHECK (sleep_hours >= 0),
    sleep_quality_pct NUMERIC CHECK (sleep_quality_pct BETWEEN 0 AND 100),
    recovery_index NUMERIC CHECK (recovery_index BETWEEN 0 AND 100),
    physical_activity_minutes NUMERIC CHECK (physical_activity_minutes >= 0),
    metabolic_stability NUMERIC CHECK (metabolic_stability BETWEEN 1 AND 10),
    stress NUMERIC CHECK (stress BETWEEN 1 AND 10),
    energy NUMERIC CHECK (energy BETWEEN 1 AND 10),
    provenance TEXT NOT NULL DEFAULT 'RPT',
    source JSONB,
    qc_status TEXT NOT NULL DEFAULT 'PENDING',
    UNIQUE(user_id, state_date)
);

-- ---------- 3. Capacity engine ----------
CREATE TABLE IF NOT EXISTS ct_capacity_runs (
    capacity_run_id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES ct_users(user_id),
    state_date DATE NOT NULL,
    formula_version TEXT NOT NULL,
    energy NUMERIC NOT NULL,
    stress NUMERIC NOT NULL,
    recovery_norm NUMERIC NOT NULL,
    c_cap NUMERIC NOT NULL,
    recommended_level CHAR(1) NOT NULL CHECK (recommended_level IN ('A','B','C','D','E')),
    safety_trigger BOOLEAN NOT NULL DEFAULT FALSE,
    rule_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    input_hash TEXT NOT NULL,
    output_hash TEXT NOT NULL,
    provenance TEXT NOT NULL DEFAULT 'DRV',
    UNIQUE(user_id, state_date, formula_version)
);

-- Formula is an executable MDL/DRV contract:
-- C_cap = 0.5*E + 0.3*(R/10) - 0.5*S
--
-- Safety:
-- S >= 8 OR C_cap < 3 -> A
--
-- IMPORTANT:
-- The formula itself is not empirical validation.

-- ---------- 4. Sprint runtime ----------
CREATE TABLE IF NOT EXISTS ct_user_sprints (
    user_sprint_id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES ct_users(user_id),
    sprint_template_id TEXT NOT NULL,
    target_node_id TEXT NOT NULL,
    started_on DATE NOT NULL,
    planned_end_on DATE NOT NULL,
    status TEXT NOT NULL CHECK (
        status IN ('PLANNED','ACTIVE','PAUSED','COMPLETED','ABORTED')
    ),
    initial_level CHAR(1) CHECK (initial_level IN ('A','B','C','D','E')),
    current_level CHAR(1) CHECK (current_level IN ('A','B','C','D','E')),
    generator_version TEXT NOT NULL,
    root_cause_node_id TEXT,
    root_cause_status TEXT NOT NULL DEFAULT 'UNKNOWN',
    provenance TEXT NOT NULL DEFAULT 'DRV'
);

CREATE TABLE IF NOT EXISTS ct_sprint_days (
    sprint_day_id UUID PRIMARY KEY,
    user_sprint_id UUID NOT NULL REFERENCES ct_user_sprints(user_sprint_id),
    day_number INT NOT NULL CHECK (day_number BETWEEN 1 AND 21),
    calendar_date DATE NOT NULL,
    assigned_level CHAR(1) NOT NULL CHECK (assigned_level IN ('A','B','C','D','E')),
    opportunities_count INT NOT NULL DEFAULT 0 CHECK (opportunities_count >= 0),
    successful_executions INT NOT NULL DEFAULT 0 CHECK (successful_executions >= 0),
    pause_used_count INT NOT NULL DEFAULT 0 CHECK (pause_used_count >= 0),
    compliance NUMERIC,
    stress_before NUMERIC CHECK (stress_before BETWEEN 1 AND 10),
    stress_after NUMERIC CHECK (stress_after BETWEEN 1 AND 10),
    energy NUMERIC CHECK (energy BETWEEN 1 AND 10),
    reflection_completed BOOLEAN,
    notes JSONB,
    UNIQUE(user_sprint_id, day_number)
);

-- ---------- 5. Event-level behavioral evidence ----------
CREATE TABLE IF NOT EXISTS ct_behavior_events (
    event_id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES ct_users(user_id),
    user_sprint_id UUID REFERENCES ct_user_sprints(user_sprint_id),
    event_time TIMESTAMPTZ NOT NULL,
    node_id TEXT NOT NULL,
    trigger_type TEXT,
    context_type TEXT,
    stimulus_intensity NUMERIC,
    response_latency_seconds NUMERIC,
    intended_response TEXT,
    observed_response TEXT,
    pause_used BOOLEAN,
    outcome_score NUMERIC,
    provenance TEXT NOT NULL DEFAULT 'OBS',
    raw_event JSONB,
    event_hash TEXT NOT NULL UNIQUE
);

-- ---------- 6. Root-cause decisions ----------
CREATE TABLE IF NOT EXISTS ct_root_cause_runs (
    run_id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES ct_users(user_id),
    target_node_id TEXT NOT NULL,
    executed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    threshold NUMERIC NOT NULL DEFAULT 40,
    selected_node_id TEXT,
    selected_score NUMERIC,
    deficit NUMERIC,
    status TEXT NOT NULL CHECK (
        status IN ('SELECTED','NO_BOTTLENECK','UNKNOWN_DATA')
    ),
    candidate_nodes JSONB NOT NULL,
    algorithm_version TEXT NOT NULL,
    provenance TEXT NOT NULL DEFAULT 'DRV'
);

-- Missing score MUST result in UNKNOWN_DATA, never a default score of 10/100.

-- ---------- 7. Adaptation decisions ----------
CREATE TABLE IF NOT EXISTS ct_adaptation_decisions (
    decision_id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES ct_users(user_id),
    user_sprint_id UUID REFERENCES ct_user_sprints(user_sprint_id),
    decision_time TIMESTAMPTZ NOT NULL DEFAULT now(),
    previous_level CHAR(1),
    new_level CHAR(1),
    action TEXT NOT NULL,
    rule_ids JSONB NOT NULL,
    input_snapshot JSONB NOT NULL,
    explanation TEXT NOT NULL,
    provenance TEXT NOT NULL DEFAULT 'DRV',
    decision_hash TEXT NOT NULL UNIQUE
);

-- ---------- 8. Compatibility runtime ----------
CREATE TABLE IF NOT EXISTS ct_compatibility_runs (
    compatibility_run_id UUID PRIMARY KEY,
    user_a_id UUID NOT NULL REFERENCES ct_users(user_id),
    user_b_id UUID NOT NULL REFERENCES ct_users(user_id),
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    algorithm_version TEXT NOT NULL,

    v1_bio_tempo JSONB NOT NULL,
    v2_values_alignment JSONB NOT NULL,
    v3_behavioral_synergy JSONB NOT NULL,

    completeness JSONB NOT NULL,
    provenance JSONB NOT NULL,
    limitations JSONB NOT NULL,

    input_hash TEXT NOT NULL,
    output_hash TEXT NOT NULL
);

-- No single "compatibility percentage" is persisted as the authoritative result.

-- ---------- 9. Claims / evidence / replication ----------
CREATE TABLE IF NOT EXISTS ct_claims (
    claim_id TEXT PRIMARY KEY,
    claim_text TEXT NOT NULL,
    status TEXT NOT NULL CHECK (
        status IN (
            'HYPOTHESIS',
            'REGISTERED',
            'TESTED',
            'SUPPORTED',
            'UNSUPPORTED',
            'REPLICATED',
            'EVIDENCE_SUPPORTED'
        )
    ),
    provenance TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ct_claim_evidence (
    claim_evidence_id UUID PRIMARY KEY,
    claim_id TEXT NOT NULL REFERENCES ct_claims(claim_id),
    evidence_type TEXT NOT NULL,
    source_id TEXT,
    metric_id TEXT,
    effect JSONB,
    qc_status TEXT,
    provenance TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ct_claim_replications (
    replication_id UUID PRIMARY KEY,
    claim_id TEXT NOT NULL REFERENCES ct_claims(claim_id),
    study_id TEXT NOT NULL,
    population JSONB,
    protocol_version TEXT NOT NULL,
    result JSONB NOT NULL,
    replication_status TEXT NOT NULL,
    provenance TEXT NOT NULL DEFAULT 'EXP',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------- 10. Full provenance / audit ----------
CREATE TABLE IF NOT EXISTS ct_provenance_records (
    provenance_id UUID PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    provenance_tag TEXT NOT NULL,
    source TEXT,
    instrument TEXT,
    protocol_version TEXT,
    algorithm_version TEXT,
    input_hash TEXT,
    output_hash TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata JSONB
);

CREATE TABLE IF NOT EXISTS ct_audit_events (
    audit_id BIGSERIAL PRIMARY KEY,
    event_time TIMESTAMPTZ NOT NULL DEFAULT now(),
    actor_type TEXT NOT NULL,
    actor_id TEXT,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT,
    before_state JSONB,
    after_state JSONB,
    reason TEXT,
    provenance TEXT NOT NULL
);

-- ---------- 11. Deterministic runtime views ----------

CREATE OR REPLACE VIEW ct_active_sprints AS
SELECT
    s.user_sprint_id,
    s.user_id,
    s.sprint_template_id,
    s.target_node_id,
    s.current_level,
    s.started_on,
    s.planned_end_on,
    s.status
FROM ct_user_sprints s
WHERE s.status = 'ACTIVE';

CREATE OR REPLACE VIEW ct_sprint_progress AS
SELECT
    s.user_sprint_id,
    s.user_id,
    COUNT(d.sprint_day_id) AS recorded_days,
    COALESCE(SUM(d.opportunities_count),0) AS opportunities,
    COALESCE(SUM(d.successful_executions),0) AS successful_executions,
    CASE
        WHEN COALESCE(SUM(d.opportunities_count),0) = 0 THEN NULL
        ELSE
            SUM(d.successful_executions)::NUMERIC
            / NULLIF(SUM(d.opportunities_count),0)
    END AS compliance
FROM ct_user_sprints s
LEFT JOIN ct_sprint_days d
    ON d.user_sprint_id = s.user_sprint_id
GROUP BY s.user_sprint_id, s.user_id;

COMMIT;
