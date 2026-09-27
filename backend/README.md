# Backend V2.1 Implementation Baseline

This backend contains executable runtime implementations for selected V2.0/V1.3-V1.6 contracts. Runtime state is currently in-memory unless explicitly stated otherwise.

Implemented runtime layers:
- provenance tags and immutable content hashing
- canonical Master Matrix V1.0 catalog (30 items, P1-P5)
- assessment profile and daily-state derivation
- C_cap calculation with UNKNOWN handling, A-E capacity levels and safety precedence
- trait-graph traversal and intervention planning
- 21-day sprint state machine
- outcome evaluation and runtime lineage events
- descriptive and longitudinal validation primitives
- registered paired analysis with immutable dataset manifest hashing
- canonical RESULT graph boundary
- Evidence Graph V1.4 registry, lineage validation and immutable audit events
- Claim V1.4 state machine, claim-bound evidence criteria, contradiction handling and inference blocks
- Replication V1.5 comparison runtime
- Generalization/transport V1.5 runtime
- Scientific Reporting V1.6 snapshot, QC, publication and supersession runtime
- Decision & Intervention V1.7 safety-first runtime and research bridge
- Integrated Platform Orchestrator V1.8 execution state machine and immutable event lineage
- V1.9 synthetic end-to-end contract fixture and executable integrity runner
- shared SQLite durable runtime persistence for graph, orchestration, reporting and intervention state
- FastAPI endpoints exposing the executable baseline

Not yet implemented:
- persistent database connection/storage for runtime registries
- authentication/authorization
- durable sprint/intervention persistence
- full orchestrator event bus
- executable V1.9 integration test runner
- empirical validation of the model or its derived rules

Important status boundary:
- SPECIFIED contracts are not automatically IMPLEMENTED.
- Runtime acceptance is not TESTED or VALIDATED.
- Model-derived rules remain model-derived unless separately supported by empirical evidence.

Platform status: IMPLEMENTATION_BASELINE.

Additional executable layers now include V1.6 Scientific Reporting and V1.7 Decision/Intervention runtime; both remain in-memory and are not empirically validated.
