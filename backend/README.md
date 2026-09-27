# Backend V2.1 Implementation Baseline

This backend contains executable runtime implementations for the Master Matrix V1.0 and the V1.3-V1.9 execution contracts. Model-derived rules are explicitly marked and are not presented as empirically validated findings.

Implemented runtime layers:
- provenance tags and immutable content hashing
- canonical Master Matrix V1.0 catalog (30 items, P1-P5)
- assessment profile and daily-state derivation
- C_cap calculation with UNKNOWN handling, A-E capacity levels and safety precedence
- trait-graph traversal and root-cause intervention planning
- 21-day sprint state machine with Safety Gate and consecutive-low-recovery Bio Reset pause
- structured Compatibility Engine V1.0 with V1 Bio/Tempo, V2 ranked Values, V3 role-interaction vectors and scenario/intervention mapping
- Level A recovery/digital-stimulus restriction protocol with 5-30 second micro-action window
- explicit CURRENT STATE vs TRAIT isolation invariant
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

Compatibility Engine notes:
- Compatibility never emits an authoritative scalar score.
- V1 expects tempo, energy, reactivity and recovery. Energy/recovery accept Master Matrix aliases `subjective_energy` and `recovery_index`.
- Tempo and reactivity are reported as missing when not explicitly supplied; the engine does not silently infer them from another P1 variable.
- V2 computes Spearman rank correlation, top alignments, value gaps and explicitly labeled heuristic potential conflict zones.
- V3 reports role-pair synergies/complementarity and competition; interaction defaults are model-derived.
- Scenarios are rule-based interventions such as a 24-hour decision buffer for a material tempo gap. These rules are DRV, not empirical evidence.

Recovery / Detox notes:
- Level A is forced when `subjective_stress >= 8` or `C_cap < 3.0`; missing required capacity inputs remain UNKNOWN and safety-blocked.
- Recovery below 4.0/10 for three consecutive supplied days triggers `BIO_RESET_DETOX` and pauses the sprint.
- Compromised daily state is recorded separately from P2-P5 trait values; recovery logic does not rewrite a trait as "low" merely because the current state is compromised.
- Recovery mode can restrict incoming stimuli, keep micro-actions within 5-30 seconds, and exclude cognitively costly behavioral tests. This is an executable model protocol, not a clinical detox claim.

Important status boundary:
- SPECIFIED contracts are not automatically IMPLEMENTED.
- Runtime acceptance is CI-TESTED: GitHub Actions run #68 completed successfully with 131 backend tests passing. This is not scientific/empirical validation.
- Model-derived rules remain model-derived unless separately supported by empirical evidence.
- Production PostgreSQL, authentication/authorization, observability, and empirical validation remain open work.

Platform status: IMPLEMENTATION_BASELINE.
