# Protocol Selection Engine V1.0

## Scope

The selector returns explainable protocol candidates from a caller-supplied registry.
It does not create clinical recommendations, prove efficacy, execute interventions,
or rank people or protocols. The current scientific status remains
`IMPLEMENTATION_BASELINE`.

## Inputs

- Registry entries with a stable `protocol_id`, version, lifecycle status,
  canonical Master Matrix measurement requirements, state preconditions, goal/context
  tags, contraindication tags, optional minimum capacity, and evidence class.
- Canonical profile values and a separate current-state object.
- Explicit goals, contexts, active constraints, capacity, and safety-gate status.

## Candidate statuses

- `ELIGIBLE_FOR_REVIEW`: declared requirements are present and pass; not authorization.
- `CONDITIONAL`: safety status is unknown, so human review is required.
- `INSUFFICIENT_DATA`: required measurements, state, or capacity are missing.
- `NOT_MATCHED`: no requested goal or context tag matches the protocol.
- `INELIGIBLE`: protocol is not active, a safety block/contraindication applies,
  required state does not match, or capacity is below the declared minimum.

The implementation preserves registry order. It emits no score, probability, rank, or
winner. Missing data are never imputed. Safety `BLOCK` excludes all candidates;
safety `UNKNOWN` cannot yield an eligible result. Every returned candidate is marked
`selection_authorized=false` and `requires_human_review=true`.

## Limitations and next integration stage

This module is an implementation baseline, not empirically validated predictive logic.
Registry definitions and their contraindications must be governed and reviewed.
The next stage is a versioned API adapter that binds an approved, auditable protocol
registry to the selector and records provenance. Do not enable autonomous execution
from candidate output.
