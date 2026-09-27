# Scientific Report & Decision Engine V1.6

Status: MDL/DRV architecture specification — not empirically validated.

V1.6 converts the registered research lifecycle into a reproducible, provenance-linked report without upgrading the evidentiary status of a claim.

Pipeline:
OBSERVATION → MEASUREMENT → DATASET → ANALYSIS → RESULT → REPLICATION → GENERALIZATION → CLAIM → REPORT

The report is a rendering of registered artifacts, not a new source of evidence.

## Decision principles

- A statistical result does not automatically become an evidence-supported claim.
- Replication and generalization remain separate dimensions.
- Contradictory and limiting evidence is retained.
- Missing or indeterminate inputs remain visible.
- Every report section has source artifact references.
- Every derived narrative statement carries a rule/version reference.
- Reports are immutable snapshots of a registered analysis state.

## Report layers

1. Executive research summary
2. Research question and hypotheses
3. Measurement specification
4. Study design and participants
5. Data quality / QC
6. Statistical analysis
7. Results and uncertainty
8. Replication
9. Generalization / transport
10. Evidence and claim graph
11. Claim status
12. Limitations and boundaries
13. Provenance manifest
14. Reproducibility metadata
