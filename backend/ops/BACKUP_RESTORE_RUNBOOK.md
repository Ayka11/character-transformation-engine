# CTE Backup / Restore Runbook

## Create a backup

Set the appropriate runtime configuration and run:

`python backend/scripts/runtime_backup.py create backups/cte-runtime.json`

The output includes a `manifest_hash`. Store the backup and hash outside the application host according to the deployment retention policy.

## Validate a backup

`python backend/scripts/runtime_backup.py validate backups/cte-runtime.json`

Validation checks the backup version, manifest hash, snapshot hashes and required event fields.

## Restore drill

1. Restore into an isolated runtime database.
2. Run the validation and integrity suite.
3. Confirm the restored evidence/provenance graph is internally consistent.
4. Confirm `/health` reports the expected persistence backend.
5. Record the restore drill timestamp, backup manifest hash and result.

Production restore through `/ops/backup/restore` defaults to dry-run. A non-dry-run operation requires `CTE_OPS_API_KEY` and should be executed during a maintenance window.

## Retention

Operational audit purge requires an archive manifest hash. Apply retention only after the backup has been validated.

## Rollback relation

Schema rollback must follow `backend/migrations/MIGRATION_ROLLBACK_PLAN.md`. The guarded down migration refuses to drop populated runtime tables.