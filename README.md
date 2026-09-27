# Character Transformation & Social Compatibility Engine

A provenance-aware architecture for measurement, adaptive behavioral intervention, compatibility analysis, reproducible research execution, and a browser-accessible Science Lab.

## Architecture

- **Master Matrix V1.0** — canonical ontology, domains P1–P5, traits/subtraits, metrics, questions, behavioral tests, load levels, sprint templates, compatibility vectors, claims and validation protocols.
- **Runtime V1.1** — user profiles, immutable trait snapshots, daily state, capacity engine, root-cause navigation, sprint runtime, behavioral events, adaptation decisions, compatibility runtime, provenance and claim graph.
- **Research Execution V1.2** — study/protocol/experiment/arm/participant/trial execution, QC, immutable dataset manifests and descriptive analysis.

## Scientific status

This repository is an implementation architecture and model specification. `MDL` and `HYP` elements are not treated as empirically established merely because the software produces numerical outputs.

## Core invariants

1. TRAIT and daily STATE remain separate.
2. Missing measurements are `UNKNOWN`, never a perfect/default score.
3. Every derived decision records its rule/algorithm version and input/output hashes.
4. Safety degradation has priority over promotion.
5. Compatibility is represented as V1/V2/V3 vectors plus data-quality metadata, not as one authoritative percentage.
6. QC precedes final statistical interpretation.
7. Replication is a separate study/run, not a renamed re-analysis of the same dataset.
8. Generalization records target population/context and transport error.
9. Claims require explicit evidence and replication provenance before evidence-supported status.

## Pipeline

```text
Question → Hypothesis → Study → Protocol → Experiment
→ Participant → Trial Data → QC → Dataset Manifest
→ Analysis → Result → Claim → Replication → Generalization → Report
```

## Versioning

- V1.0 — canonical Master Matrix seed
- V1.1 — executable Runtime layer
- V1.2 — Research Execution layer


## V2.2–V2.3

- **V2.2 Research E2E** composes profile, assessment, state, capacity, safety, research execution, QC, analysis, claim and audit under one execution ID.
- **Science Lab V2.3** adds Experiment Matrix, scenario definitions/runs, descriptive statistics, replication/generalization assessment, claim validation, provenance report bundle and a static browser UI at `/science-lab/ui`.
- Current CI baseline: GitHub Actions run #106, 140 backend tests passing.


## V2.4 Operations

- Portable logical backup/restore with checksum validation and restore preflight.
- Audit retention policy requiring an archive manifest before purge.
- Configurable request rate limiting.
- Protected operational API for backup, restore and retention.
- Guarded PostgreSQL rollback migration and documented rollback procedure.
