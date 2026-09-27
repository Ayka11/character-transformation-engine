# Durable Runtime Persistence Status

A stdlib SQLite runtime adapter is now available through CTE_RUNTIME_DB (default data/cte-runtime.sqlite3 in the executable API).

Durable coverage currently includes:
- Evidence Graph nodes and edges;
- graph audit events, contradiction sets and inference blocks;
- Orchestrator executions, events, module registry, schema registry and rule registry;
- Scientific Reporting specs and report snapshots;
- Decision/Intervention rules and assignments;
- graph-backed replication and generalization research state.

The adapter uses immutable content-hash snapshots and append-only event records. It is a runtime persistence layer, not a production PostgreSQL deployment. The repository PostgreSQL schemas remain the normative durable-storage contracts.

Authentication, multi-process transaction strategy, migrations/rollback, backup/recovery, observability and production hardening remain open.
