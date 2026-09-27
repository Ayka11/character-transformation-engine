# Migration Rollback Plan

## Runtime persistence

The PostgreSQL runtime migration is `002_runtime_postgres.sql`.

## Before deployment
1. Run a logical runtime backup with `runtime_backup.build_backup`.
2. Record the backup `manifest_hash`.
3. Validate the backup with `runtime_backup.validate_backup`.
4. Verify restore into an isolated PostgreSQL database.
5. Only then apply schema changes.

## Rollback

`002_runtime_postgres.down.sql` is a guarded destructive rollback. It refuses to drop runtime tables when snapshot/event data exists.

For a populated production database:
1. Enter maintenance mode.
2. Preserve the current logical backup and manifest hash.
3. Deploy the previous application/schema version.
4. Migrate or restore data into the previous schema using a version-specific recovery procedure.
5. Re-run integrity and provenance tests.
6. Exit maintenance mode only after health, persistence and audit checks pass.

Never use the down migration as a data-deleting shortcut.

## Recovery invariant

A rollback is not complete until the restored system can reproduce the recorded backup manifest and the evidence/provenance graph remains internally consistent.