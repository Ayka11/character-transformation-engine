# Evidence & Claim Graph Engine V1.4

Status: MDL/DRV architecture specification — not empirically validated.

V1.4 turns the V1.2 research layer and V1.3 analytics layer into a traceable graph.

## Core lineage

OBSERVATION → MEASUREMENT → DATASET → ANALYSIS → RESULT → REPLICATION → GENERALIZATION → CLAIM

Each edge records provenance, transformation type, algorithm/version context where applicable, and audit metadata.

## Core rules

1. A claim cannot outrank the provenance-supported status of its sources.
2. Statistical significance is not equivalent to evidence status.
3. Replication and generalization are distinct graph relationships.
4. Contradictory results remain visible; they are not silently overwritten.
5. Every claim-status transition is immutable/auditable.
6. Unsupported inference is represented explicitly as a blocked edge/rule.
7. Evidence strength is a structured record, not a single authoritative score.
