---
title: Character Transformation & Social Compatibility Engine
emoji: 🧬
colorFrom: indigo
colorTo: purple
sdk: static
app_file: index.html
pinned: false
---

# Character Transformation & Social Compatibility Engine — Static Science Lab

A browser-native static version of the Character Transformation & Social Compatibility Engine (CPE).

## What this Space does

Experiment Matrix → Scenario Design → Scenario Runs → Statistics → Replication → Generalization → Claim Validation → Provenance Report

This Space provides a self-contained Science Lab without a Python server. It implements a deterministic synthetic execution layer in JavaScript and stores the current laboratory state in browser localStorage.

## Scientific status

**IMPLEMENTATION_BASELINE**

This Space is a browser demonstration and synthetic research sandbox. Numerical output generated here is not empirical validation of MDL/HYP elements, clinical evidence, or real-world compatibility.

The implementation preserves the CPE invariants:

1. TRAIT and daily STATE remain separate.
2. Missing measurements are UNKNOWN, not perfect/default values.
3. Derived decisions carry algorithm and input/output hashes.
4. Safety degradation has priority over promotion.
5. Compatibility is represented through vectors and data-quality metadata rather than one authoritative percentage.
6. QC precedes final interpretation.
7. Replication is a separate run/study concept.
8. Generalization records target population/context and transport-error status.
9. Claims distinguish implementation evidence from empirical evidence.

## Relationship to the full CPE

This is the static presentation/execution branch of:

https://github.com/Ayka11/character-transformation-engine

The full repository remains the source for the Python/FastAPI executable backend and deeper runtime contracts. This branch intentionally avoids requiring Python, FastAPI, PostgreSQL, or an external API so it can run in a free Hugging Face Static Space.

## Branch

hf-static-space

## License

Apache-2.0.
