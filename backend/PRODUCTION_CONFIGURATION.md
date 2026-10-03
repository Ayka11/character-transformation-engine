# V2.6.0-rc1 Production Configuration

## Runtime database

`CTE_DATABASE_URL` selects PostgreSQL. When it is absent, the application falls back to `CTE_RUNTIME_DB` / SQLite for local development.

Example:
`CTE_DATABASE_URL=postgresql://<user>:<password>@<host>:5432/<database>`

Do not commit credentials, DSNs containing passwords, or API keys to the repository.

## API authentication

- `CTE_API_KEY` — one key for both read/write access.
- `CTE_READ_API_KEY` — read access.
- `CTE_WRITE_API_KEY` — mutating API access.
- `CTE_OPS_API_KEY` — separate key for backup/restore/retention operations.

When any normal API key is configured, GET/HEAD/OPTIONS require a read or write key and mutating requests require the write key.

## Rate limiting

`CTE_RATE_LIMIT_PER_MINUTE` enables the in-process sliding-window limiter. `0` or an absent variable disables the limiter.

This limiter is appropriate for a single application instance. Multi-instance production deployments require a shared/distributed limiter decision.

## Observability

- `X-Request-ID` is accepted and propagated when valid.
- `X-Process-Time-Ms` reports request processing time.
- `/metrics` exposes Prometheus-compatible counters and duration sum.
- Operational HTTP requests are written to the configured runtime event store.
- `CTE_LOG_LEVEL` controls application logging verbosity.

## Backup / recovery

Use `/ops/backup` with `CTE_OPS_API_KEY` to create a logical backup and retain its manifest hash. Validate and rehearse restore before destructive maintenance.

Audit retention requires an archive manifest hash before purge.

## Deployment requirements still external to this repository

- secret manager and key rotation;
- TLS/ingress configuration;
- production IAM/SSO integration;
- encrypted off-site backup storage;
- scheduled backups and restore drills;
- distributed rate limiting for horizontally scaled deployments;
- monitoring, alerting and on-call ownership;
- production migration/rollback execution approval.

## Scientific boundary

Software verification and operational hardening do not constitute empirical validation of the underlying behavioral/scientific model. Model-derived and hypothesis-derived rules retain their provenance classification until supported by appropriate evidence.