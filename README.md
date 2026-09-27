# Character Transformation & Social Compatibility Engine

A provenance-aware architecture for measurement, adaptive behavioral intervention, compatibility analysis, and reproducible research execution.

## Architecture

- **Master Matrix V1.0** — canonical ontology, domains P1–P5, traits/subtraits, metrics, questions, behavioral tests, load levels, sprint templates, compatibility vectors, claims and validation protocols.
- **Runtime V1.1** — user profiles, immutable trait snapshots, daily state, capacity engine, root-cause navigation, sprint runtime, behavioral events, adaptation decisions, compatibility runtime, provenance and claim graph.
- **Research Execution V1.2** — study registration, experiments, arms, participants, trial-level data, QC, dataset manifests, statistical analyses, results, replication, generalization and automated report specification.

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
