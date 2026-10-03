# V2.0 Release Readiness

## Gate A — Architecture
- [ ] V1.0–V1.9 contracts present
- [ ] Canonical IDs defined
- [ ] Module boundaries defined
- [ ] Lifecycle defined

## Gate B — Implementation
- [x] Backend modules implemented
- [ ] Database migrations applied in a production database
- [x] API contracts implemented
- [x] Event/provenance persistence implemented

## Gate C — Integrity
- [x] V1.9 negative tests executed
- [x] Provenance tests executed
- [x] Safety precedence tests executed
- [x] Evidence guardrail tests executed
- [x] E2E synthetic fixture executed
- [x] Blocking failures = 0

## Gate D — Research
- [x] Registered measurement specifications
- [x] Immutable dataset manifests
- [x] QC before final interpretation
- [x] Registered replication criteria
- [x] Declared generalization targets
- [x] Contradictions preserved

## Gate E — Scientific Status
- [x] Claims retain evidence status
- [x] Model-derived rules remain non-EVD unless separately supported
- [x] Hypothesis rules remain HYP
- [x] Runtime observations do not become evidence automatically
- [x] Report language follows claim status

## Gate F — Production
- [x] Authentication/authorization (optional environment-based read/write API keys)
- [x] Audit retention (operational API namespace + archive-before-purge rule)
- [x] Backup/recovery (portable logical backup + preflight restore)
- [x] Rate limits (configurable in-process sliding window)
- [x] Observability (request IDs, latency header, operational audit events)
- [x] Migration rollback plan (guarded PostgreSQL down migration + documented procedure)

## Current implementation snapshot

As of the current V2.1 backend baseline:
- V1.3 validation primitives have executable in-memory implementations.
- V1.4 Evidence/Claim Graph, claim-state guards, contradiction handling and inference blocks have executable in-memory implementations.
- V1.5 replication/generalization runtime has executable in-memory implementations.
- V1.6 scientific reporting has executable snapshot/QC/publish runtime.
- V1.7 decision/intervention has executable safety-first runtime.
- V1.8 orchestration has executable lifecycle/event runtime.
- V1.9 synthetic E2E contract coverage, V2.2 Research E2E and Science Lab V2.3 are executed successfully in GitHub Actions run #397.
- Durable SQLite runtime adapters are implemented for graph, orchestration, reporting, intervention and Research/Science Lab state; a PostgreSQL production adapter and runtime migration are implemented, and live snapshot/event integration is CI-tested against postgres:16 in run #124.
- Production deployment/rollback operations, authentication/authorization, observability, backup/recovery, rate limits and empirical validation remain open release gates.
- GitHub CI workflow is registered; run #168 completed successfully with the main backend suite plus live PostgreSQL integration.

**Important:** a checked architecture item does not imply that the corresponding implementation, executed test status, or scientific validation exists.
