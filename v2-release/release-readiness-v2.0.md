# V2.0 Release Readiness

## Gate A — Architecture
- [ ] V1.0–V1.9 contracts present
- [ ] Canonical IDs defined
- [ ] Module boundaries defined
- [ ] Lifecycle defined

## Gate B — Implementation
- [ ] Backend modules implemented
- [ ] Database migrations applied
- [ ] API contracts implemented
- [ ] Event/provenance persistence implemented

## Gate C — Integrity
- [x] V1.9 negative tests executed
- [x] Provenance tests executed
- [x] Safety precedence tests executed
- [x] Evidence guardrail tests executed
- [x] E2E synthetic fixture executed
- [x] Blocking failures = 0

## Gate D — Research
- [ ] Registered measurement specifications
- [ ] Immutable dataset manifests
- [ ] QC before final interpretation
- [ ] Registered replication criteria
- [ ] Declared generalization targets
- [ ] Contradictions preserved

## Gate E — Scientific Status
- [ ] Claims retain evidence status
- [ ] Model-derived rules remain MDL
- [ ] Hypothesis rules remain HYP
- [ ] Runtime observations do not become evidence automatically
- [ ] Report language follows claim status

## Gate F — Production
- [ ] Authentication/authorization
- [ ] Audit retention
- [ ] Backup/recovery
- [ ] Rate limits
- [ ] Observability
- [ ] Migration rollback plan

## Current implementation snapshot

As of the current V2.1 backend baseline:
- V1.3 validation primitives have executable in-memory implementations.
- V1.4 Evidence/Claim Graph, claim-state guards, contradiction handling and inference blocks have executable in-memory implementations.
- V1.5 replication/generalization runtime has executable in-memory implementations.
- V1.6 scientific reporting has executable snapshot/QC/publish runtime.
- V1.7 decision/intervention has executable safety-first runtime.
- V1.8 orchestration has executable lifecycle/event runtime.
- V1.9 synthetic E2E contract coverage and the V2.2 Research E2E coordinator are executed successfully in GitHub Actions run #86.
- Durable SQLite runtime adapters are implemented for graph, orchestration, reporting, intervention and Research/Science Lab state; a PostgreSQL production adapter and runtime migration are implemented, and live snapshot/event integration is CI-tested against postgres:16 in run #124.
- Production deployment/rollback operations, authentication/authorization, observability, backup/recovery, rate limits and empirical validation remain open release gates.
- GitHub CI workflow is registered and the latest current-main run (#86) completed successfully with 136 backend tests passing.

**Important:** a checked architecture item does not imply that the corresponding implementation, executed test status, or scientific validation exists.
