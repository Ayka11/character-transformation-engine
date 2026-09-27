# Durable Runtime Persistence Status

SQLite remains the default local/CI runtime store. A PostgreSQL production adapter is now available through `CTE_DATABASE_URL`; without that DSN the application continues to use `CTE_RUNTIME_DB`.

Durable coverage currently includes:
- Evidence Graph nodes and edges;
- graph audit events, contradiction sets and inference blocks;
- Orchestrator executions, events, module registry, schema registry and rule registry;
- Scientific Reporting specs and report snapshots;
- Decision/Intervention rules and assignments;
- Research Execution V1.2 state, trials, manifests, QC, analyses and results;
- Science Lab matrices, scenarios and scenario runs;
- graph-backed replication and generalization research state.

The PostgreSQL adapter implements the same snapshot/event interface as SQLite, JSONB storage, explicit transaction commit/rollback, immutable event checks and mutable runtime namespaces.

Migration artifact: `backend/migrations/002_runtime_postgres.sql`.

CI contract coverage verifies:
- PostgreSQL adapter constructor/DSN guard;
- transaction commit and rollback behavior;
- runtime-store factory selection;
- preservation of SQLite as the default when `CTE_DATABASE_URL` is absent.

A live PostgreSQL snapshot/event integration test now passes in GitHub Actions run #124 with a real postgres:16 service container. Migration/rollback execution as a deployment operation, backup/recovery, authentication/authorization, observability and production operational hardening remain open.
