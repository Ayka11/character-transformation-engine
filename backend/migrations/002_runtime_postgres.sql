BEGIN;

CREATE TABLE IF NOT EXISTS runtime_snapshots (
    namespace TEXT NOT NULL,
    key TEXT NOT NULL,
    version TEXT NOT NULL,
    payload_json JSONB NOT NULL,
    payload_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (namespace, key)
);

CREATE TABLE IF NOT EXISTS runtime_events (
    event_id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload_json JSONB NOT NULL,
    input_hash TEXT,
    output_hash TEXT,
    provenance_record_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_runtime_events_namespace_created
    ON runtime_events(namespace, created_at, event_id);

COMMIT;
