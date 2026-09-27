-- Character Transformation Engine
-- Evidence & Claim Graph Engine V1.4
-- Status: MDL/DRV design specification; not empirically validated.

BEGIN;

CREATE TABLE IF NOT EXISTS ct_graph_nodes (
    node_id TEXT PRIMARY KEY,
    node_type TEXT NOT NULL CHECK (node_type IN (
        'OBSERVATION','MEASUREMENT','DATASET','ANALYSIS','RESULT',
        'REPLICATION','GENERALIZATION','CLAIM','PROTOCOL','REPORT','SOURCE'
    )),
    entity_id TEXT NOT NULL,
    provenance_class TEXT NOT NULL CHECK (provenance_class IN ('OBS','EXT','EXP','EVD','MDL','HYP','RPT','DRV')),
    version TEXT,
    immutable_hash TEXT,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ct_graph_edges (
    edge_id TEXT PRIMARY KEY,
    from_node_id TEXT NOT NULL,
    to_node_id TEXT NOT NULL,
    edge_type TEXT NOT NULL CHECK (edge_type IN (
        'MEASURED_FROM','DERIVED_FROM','ANALYZED_FROM','RESULTS_IN',
        'REPLICATES','GENERALIZES','SUPPORTS','CONTRADICTS','QUALIFIES',
        'LIMITS','BLOCKS','DOCUMENTS','USES_PROTOCOL','CITES_SOURCE'
    )),
    relation_status TEXT NOT NULL DEFAULT 'ACTIVE'
        CHECK (relation_status IN ('ACTIVE','QUALIFIED','BLOCKED','RETRACTED')),
    transformation_rule_id TEXT,
    algorithm_version TEXT,
    input_hash TEXT,
    provenance_record_id TEXT,
    rationale TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ct_claim_status_history (
    claim_status_event_id TEXT PRIMARY KEY,
    claim_id TEXT NOT NULL,
    previous_status TEXT,
    new_status TEXT NOT NULL,
    trigger_type TEXT NOT NULL,
    supporting_node_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    blocking_node_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    rule_id TEXT NOT NULL,
    actor_type TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ct_claim_assessments (
    claim_assessment_id TEXT PRIMARY KEY,
    claim_id TEXT NOT NULL,
    assessment_version TEXT NOT NULL,
    claim_level TEXT NOT NULL CHECK (claim_level IN (
        'HYPOTHESIS','REGISTERED','DESCRIPTIVE_RESULT','ASSOCIATIONAL_RESULT',
        'INTERVENTION_RESULT','REPLICATED_RESULT','GENERALIZED_RESULT',
        'EVIDENCE_SUPPORTED','UNSUPPORTED','CONTRADICTED','INDETERMINATE'
    )),
    evidence_node_count INTEGER NOT NULL DEFAULT 0,
    replication_node_count INTEGER NOT NULL DEFAULT 0,
    contradiction_node_count INTEGER NOT NULL DEFAULT 0,
    generalization_node_count INTEGER NOT NULL DEFAULT 0,
    provenance_completeness NUMERIC,
    assessment_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    provenance_record_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ct_contradiction_sets (
    contradiction_set_id TEXT PRIMARY KEY,
    claim_id TEXT NOT NULL,
    node_ids JSONB NOT NULL,
    contradiction_type TEXT NOT NULL,
    resolution_status TEXT NOT NULL CHECK (resolution_status IN (
        'OPEN','EXPLAINED','UNRESOLVED','RESOLVED_BY_NEW_EVIDENCE'
    )),
    resolution_note TEXT,
    provenance_record_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ct_evidence_qualifiers (
    qualifier_id TEXT PRIMARY KEY,
    node_id TEXT NOT NULL,
    qualifier_code TEXT NOT NULL,
    value_json JSONB NOT NULL,
    rule_id TEXT,
    provenance_record_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ct_inference_blocks (
    inference_block_id TEXT PRIMARY KEY,
    from_node_type TEXT NOT NULL,
    to_claim_level TEXT NOT NULL,
    blocked_inference TEXT NOT NULL,
    reason_code TEXT NOT NULL,
    rule_id TEXT NOT NULL,
    provenance_record_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ct_graph_audit_events (
    graph_audit_event_id TEXT PRIMARY KEY,
    operation TEXT NOT NULL,
    node_id TEXT,
    edge_id TEXT,
    claim_id TEXT,
    payload_hash TEXT,
    actor_type TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE VIEW ct_claim_graph_summary AS
SELECT
    c.claim_id,
    COUNT(DISTINCT e.edge_id) AS edge_count,
    COUNT(DISTINCT CASE WHEN e.edge_type='SUPPORTS' AND e.relation_status <> 'BLOCKED' THEN e.edge_id END) AS support_edges,
    COUNT(DISTINCT CASE WHEN e.edge_type='CONTRADICTS' THEN e.edge_id END) AS contradiction_edges,
    COUNT(DISTINCT CASE WHEN e.edge_type='REPLICATES' THEN e.edge_id END) AS replication_edges,
    COUNT(DISTINCT CASE WHEN e.edge_type='GENERALIZES' THEN e.edge_id END) AS generalization_edges
FROM ct_claim_assessments c
LEFT JOIN ct_graph_edges e
  ON e.to_node_id = c.claim_id OR e.from_node_id = c.claim_id
GROUP BY c.claim_id;

COMMIT;
