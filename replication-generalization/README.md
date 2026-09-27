# Replication & Generalization Engine V1.5

Status: MDL/DRV architecture specification — not empirically validated.

V1.5 operationalizes the two downstream transitions in V1.4:
1. Does an independent run replicate the registered result?
2. Under what population, context, task, measurement, and time conditions can the result be generalized?

## Replication

Replication is evaluated against pre-registered criteria rather than a single p-value.

Dimensions may include:
- protocol fidelity
- measurement fidelity
- direction compatibility
- effect-size compatibility
- interval/equivalence rule
- outcome definition fidelity
- sample/data-quality adequacy

## Generalization

Generalization is explicit about the transport target:
- population
- context/site
- task configuration
- measurement instrument
- intervention delivery
- time period

The engine records transport differences and uncertainty instead of silently treating them as irrelevant.

## Core rule

Replication is not generalization, and generalization is not replication.
Both require their own provenance-linked analysis.
