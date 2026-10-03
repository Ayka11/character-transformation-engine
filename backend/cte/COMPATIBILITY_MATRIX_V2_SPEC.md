# Compatibility Matrix V2 — implementation specification

**Version:** 2.0  
**Status:** implementation baseline; heuristic rules are not empirically validated.

## Purpose

Provide an explainable, versioned pairwise compatibility layer without reducing a
person or relationship to a single authoritative score. This additive module leaves
the existing V1/V2/V3 compatibility APIs unchanged.

## Canonical domains

| Domain | Scope | Guardrail |
|---|---|---|
| P1 | State and resources | State-dependent observations are not stable personality traits. |
| P2 | Stable traits | Use documented instruments/scales; do not infer missing values. |
| P3 | Self-regulation and cognition | Distinguish self-reports from observed behavior. |
| P4 | Values and priorities | Priority gaps are hypotheses for discussion, not verdicts. |
| P5 | Behavior and social roles | Role labels are context-specific and may change. |

## Row contract

Every row includes kind, pair, status, rule_id, evidence_class, explanation, and
contexts. Numeric trait rows include observed values and an absolute gap where both
measurements exist. Role/value heuristics require human review. Unregistered pairs
remain UNKNOWN; missing values are never imputed.

## Status semantics

- OBSERVED_ALIGNMENT: both measurements exist; only a descriptive gap is asserted.
- CONDITIONAL: a registered heuristic may be relevant; context and human review required.
- UNKNOWN: no rule or adequate data is available.
- PARTIAL: aggregate result includes unknown rows.
- ESTIMATED: all produced rows have a current descriptive/heuristic interpretation;
  this does not mean scientifically validated.

BLOCKED is intentionally not emitted by V2. Hard blocks require a separately approved
safety policy with explicit authority, evidence and review requirements.

## Canonical Master Matrix adapter

compatibility_matrix_adapter.py accepts canonical P4 IDs such as P4.value_autonomy,
not arbitrary labels. It checks that each ID is registered in Master Matrix V1.0,
belongs to P4, and has a finite numeric value within the declared 0–10 scale. It
translates IDs to the evaluator's registered labels only after validation. Unknown
IDs, other domains, non-finite values, booleans and out-of-range values fail closed.
Missing values remain unknown; no values are imputed.

This adapter currently covers P4 value profiles only. It does not yet normalize P1,
P2, P3 or P5 into compatibility inputs, and it does not change the existing
POST /compatibility contract.

## Current rule coverage

- Value tension heuristics: Order/Autonomy, Security/Freedom, Achievement/Compassion.
- Role heuristics: Leader/Strategist, Organizer/Mediator, Strategist/Organizer,
  Leader/Mediator, plus same-role competition for Leader, Organizer, Strategist and Mediator.
- Other pairs remain UNKNOWN unless measured descriptively or a rule is registered.

These rules preserve existing CTE heuristic vocabulary. They are not claims that
these combinations reliably predict relationship outcomes.

## Validation and rollout

1. Unit-test missing data, invalid values, rule coverage and uncertainty semantics.
2. Add pairwise fixtures only when each rule has a documented rationale and owner.
3. Validate against pre-registered, consented empirical data before predictive claims.
4. Keep V1/V2/V3 APIs stable while callers migrate deliberately.
5. Do not expose an overall percentage or rank people/relationships from this module.
