---
title: Character Transformation & Social Compatibility Engine
emoji: 🧭
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
---

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
- Current RC verification baseline: GitHub Actions run #397 passed with 251 tests, 12 skipped, PostgreSQL integration, and migration up/down rehearsal.

## V2.4 Operations

- Portable logical backup/restore with checksum validation and restore preflight.
- Audit retention policy requiring an archive manifest before purge.
- Configurable request rate limiting.
- Protected operational API for backup, restore and retention.
- Guarded PostgreSQL rollback migration and documented rollback procedure.

## V2.6 Production Hardening / RC

The v2.6 release candidate gate is maintained in
`v2-release/V2.6_PRODUCTION_READINESS.md`.

Current release policy:
- historical CI success does not substitute for current RC verification;
- immutable persistence requires race-safe/idempotent writes and conflict detection;
- transformation contracts enforce declared preconditions and postconditions;
- crash recovery must preserve the distinction between execution, validation,
  certification and completion;
- backup/restore and evidence lineage must survive adversarial integrity checks;
- v2.6.0-rc1 is not tagged until the exact RC commit has a green CI gate.

Scientific status remains IMPLEMENTATION_BASELINE; software execution alone is
not empirical validation.

## Deployment

The Hugging Face Space is built as a Docker app on port 7860. GitHub Actions deploys the tested `main` commit after the **Backend Tests** workflow succeeds. Configure the repository secret `HF_TOKEN` with write access to the target Space; never commit the token to source control.
