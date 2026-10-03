# Canonical Master Matrix adapter — P1–P5 rollout

**Status:** implementation baseline. No empirical predictive validity is claimed.

## Input contract

The adapter accepts registered Master Matrix V1.0 item IDs only. Each value must be
finite numeric data (booleans and strings are rejected) and lie within the scale
declared by that item. Missing values are never imputed.

- P1 state/resource measurements keep canonical IDs.
- P2 trait measurements keep canonical IDs.
- P3 modeled self-regulation/cognition measurements keep canonical IDs.
- P4 value measurements map to registered display names only after canonical ID
  validation, so existing V2 value-tension rules remain usable.
- P5 behavior measurements keep canonical IDs.

## Provenance

Results include each input's canonical ID, domain, measurement kind, scale, direction,
and provenance tag. This metadata describes the catalog contract; it does not
independently verify the source or quality of a value.

## Interpretation

Same-item gaps are descriptive only. Registered P4 and role interactions remain
heuristic and require human review. Unregistered pairs and missing measurements remain
UNKNOWN. No authoritative scalar, compatibility percentage, ranking, or empirical
prediction is introduced.

## API rollout

The helper is additive and does not change the existing POST /compatibility route.
API integration should follow separately after adapter tests and CI pass.
