---
title: Character Transformation & Social Compatibility Engine
emoji: 🧬
colorFrom: indigo
colorTo: purple
sdk: static
app_file: index.html
pinned: false
---

# CPE — Interactive Scientific Computing Demonstrator

A browser-native demonstrator of the Character Transformation & Social Compatibility Engine (CPE). The public Static Space exposes the architecture as an executable synthetic research environment rather than a static mockup.

## Demonstrator modules

- Command Center — end-to-end CPE pipeline and runtime health.
- Master Matrix — P1–P5 ontology, traits, metrics, evidence requirements and state interaction.
- Character Model — trait/state separation, capacity, confidence and UNKNOWN handling.
- Transformation Engine — root-cause navigation, intervention protocol and 21-day synthetic trajectory.
- Compatibility Lab — three compatibility vectors plus context stress scenarios.
- Science Lab — hypothesis, factorial scenarios, trial-level data, QC, descriptive statistics, replication and generalization status.
- Evidence & Claims — evidence lineage and claim gates.
- Provenance Inspector — algorithm version, input/output hashes and event lineage.
- Scientific Report — reproducible implementation report and JSON export.
- Development — visible evolution of the CPE architecture.

## Full demonstration

Use Run Full CPE Demonstration to execute:

Question → Hypothesis → Character Model → Transformation → Compatibility → Experiment → Trials → QC → Analysis → Replication → Claims → Provenance → Report.

All generated data is deterministic/synthetic and stored locally in browser localStorage.

## Scientific status

**IMPLEMENTATION_BASELINE**

The Static Space demonstrates software/model execution. It does not establish empirical validity, clinical evidence, causal efficacy, or real-world compatibility prediction.

The demonstrator explicitly preserves these CPE invariants:

1. TRAIT and daily STATE are separate.
2. Missing measurements remain UNKNOWN rather than becoming default/perfect scores.
3. Derived outputs carry algorithm and input/output hashes.
4. Safety degradation has priority over promotion.
5. Compatibility is represented through multiple vectors and context/data-quality metadata, not one authoritative percentage.
6. QC precedes interpretation.
7. Replication is represented separately from the original execution.
8. Generalization records target context and transport-error status.
9. Claims distinguish implementation evidence from empirical evidence.

## Architecture relationship

The public Static Space is the browser execution/presentation layer of the full repository:

https://github.com/Ayka11/character-transformation-engine

The repository's Python/FastAPI implementation remains the deeper executable backend and contract source. The Static branch intentionally avoids Python, FastAPI, PostgreSQL and external API dependencies so it can run as a free Hugging Face Static Space.

## Branch

hf-static-space

## Local execution

Open index.html in a modern browser or serve the repository directory with any static HTTP server.

## License

Apache-2.0.
