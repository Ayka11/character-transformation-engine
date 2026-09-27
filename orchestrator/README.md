# Integrated Platform Orchestrator V1.8

Status: MDL/DRV architecture specification — not empirically validated.

V1.8 integrates V1.0–V1.7 into one execution architecture.

## Canonical lifecycle

INTAKE
→ PROFILE
→ ASSESSMENT
→ STATE_ESTIMATION
→ CAPACITY
→ RULE_ELIGIBILITY
→ SAFETY_GATE
→ INTERVENTION
→ MEASUREMENT
→ QC
→ ANALYSIS
→ CLAIM
→ REPLICATION
→ GENERALIZATION
→ REPORT
→ ADAPTATION
→ AUDIT

Not every runtime cycle executes every research stage. The orchestrator records which stages ran and why.

## Integration principles

- One execution ID can span multiple modules.
- Every event carries schema version, source module, input hash and provenance reference.
- Module outputs are immutable facts/results; later modules reference them.
- V1.4 claim-state restrictions remain authoritative.
- V1.5 replication/generalization restrictions remain authoritative.
- V1.6 reporting language restrictions remain authoritative.
- V1.7 safety and intervention restrictions remain authoritative.
- Unknown values remain explicit.
- A module failure cannot be represented as a successful downstream stage.
