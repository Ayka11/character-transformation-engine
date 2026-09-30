---
title: Character Transformation & Social Compatibility Engine
emoji: 🧬
colorFrom: indigo
colorTo: purple
sdk: static
app_file: index.html
pinned: false
---

# CPE — Interactive Scientific Computing Demonstrator · Release A

A browser-native demonstrator of the Character Transformation & Social Compatibility Engine (CPE). The current public branch is being developed incrementally through Release A (Foundation), while the deeper Python/FastAPI implementation remains on the canonical backend branch. The public Static Space exposes the architecture as an executable synthetic research environment rather than a static mockup.

## Demonstrator modules

- Command Center — end-to-end CPE pipeline and runtime health.
- Master Matrix — P1–P5 ontology, traits, metrics, evidence requirements and state interaction.
- Character Model — editable Profile Builder, trait/state separation, capacity, confidence, evidence states and UNKNOWN handling.
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


## Current development release

**Release A — Foundation (CPE-STATIC-2.1)**

Implemented in this branch:
- Command Center baseline and executable pipeline.
- Master Matrix P1–P5 explorer.
- Editable synthetic Profile Builder for P1–P5.
- Trait/state separation with contextual state controls.
- Explicit UNKNOWN/PARTIAL evidence states.
- Capacity calculation with visible context contributors.
- Provenance events for profile changes.
- Science Lab remains available as the underlying research execution layer.

Next planned releases:
- **Release B — Transformation:** root-cause model, intervention controls, 21-day adaptation simulator.
- **Release C — Social:** editable participant profiles, compatibility vectors and stress scenarios.
- **Release D — Scientific Computing:** study/experiment builder, trial dataset, QC and statistics expansion.
- **Release E — Validation Infrastructure:** replication, generalization, evidence graph, claim graph and provenance tracing.
- **Release F — Publication/Demonstration:** scientific report, architecture viewer, development timeline and full end-to-end demo.

The branch remains a **synthetic browser demonstrator**. Implementation status is not empirical validation.
