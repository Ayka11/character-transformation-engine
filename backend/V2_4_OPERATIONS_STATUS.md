# V2.4 Operations Status

Status: **IMPLEMENTED / CI-TESTED / NOT FULLY PRODUCTION-HARDENED**

## Recovery
- Portable logical runtime backup covers all snapshot namespaces and event namespaces.
- Backup packages carry a manifest hash and per-snapshot content hashes.
- Restore validates the complete package before writing.
- Immutable snapshot/event conflicts are rejected during restore preflight.
- Dry-run restore is supported.

## Audit retention
- Operational API audit events use namespace `api`.
- Retention policy requires an archive backup manifest hash before purge.
- Retention purge can target a namespace and records the policy/rule provenance.

## Rate limiting
- Configurable sliding-window limiter via `CTE_RATE_LIMIT_PER_MINUTE`.
- HTTP 429 and `Retry-After` are returned on limit exhaustion.
- The limiter is intentionally in-process; a distributed limiter remains a production scaling concern.

## Rollback
- `backend/migrations/002_runtime_postgres.down.sql` is a guarded destructive rollback.
- The down migration refuses to drop runtime tables when data exists.
- `backend/migrations/MIGRATION_ROLLBACK_PLAN.md` defines backup, maintenance and post-rollback integrity checks.

## Operational API
- `/ops/backup` creates a logical backup.
- `/ops/backup/validate` verifies a backup manifest.
- `/ops/backup/restore` supports dry-run and controlled restore.
- `/ops/audit-retention` applies the registered retention policy.
- All Ops routes require `CTE_OPS_API_KEY`.

## CI
- GitHub Actions run #168 completed successfully.
- The main backend pytest job passed.
- The live PostgreSQL integration job passed.

## Remaining production gates
- production deployment and migration execution;
- distributed rate limiting;
- backup storage encryption and off-site retention;
- automated scheduled backups and restore drills;
- external identity/IAM integration;
- observability export/metrics/alerting;
- empirical scientific validation.