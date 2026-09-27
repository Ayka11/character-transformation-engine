-- Rollback for 002_runtime_postgres.sql.
-- SAFETY: this script is intentionally destructive. It refuses to drop runtime
-- data tables when data is present. Back up and restore data into the prior
-- application schema before performing a production rollback.

BEGIN;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM runtime_snapshots LIMIT 1)
       OR EXISTS (SELECT 1 FROM runtime_events LIMIT 1) THEN
        RAISE EXCEPTION
            'Refusing destructive rollback: runtime data exists. Create and verify a backup first, then perform controlled data migration.';
    END IF;
END $$;

DROP INDEX IF EXISTS idx_runtime_events_namespace_created;
DROP TABLE IF EXISTS runtime_events;
DROP TABLE IF EXISTS runtime_snapshots;

COMMIT;