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
- [ ] V1.9 negative tests executed
- [ ] Provenance tests executed
- [ ] Safety precedence tests executed
- [ ] Evidence guardrail tests executed
- [ ] E2E synthetic fixture executed
- [ ] Blocking failures = 0

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
- V1.9 synthetic E2E contract coverage has been added as tests, but those tests have not been executed in this environment.
- Persistent database/event storage, authentication, production observability and empirical validation remain open release gates.

**Important:** a checked architecture item does not imply that the corresponding implementation, executed test status, or scientific validation exists.
