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

## Coverage and provenance

Results include each input's canonical ID, domain, measurement kind, scale, direction,
and provenance tag. This metadata describes the catalog contract; it does not
independently verify the source or quality of a value.

The all-domain adapter also returns `catalog_coverage`, grouped by P1–P5. Each
domain reports the catalog item count, supplied items for each profile, shared items,
and items missing from either or both profiles. `complete_for_both_profiles` is true
only when both profiles supply every currently registered catalog item. This is a
coverage declaration, not a quality threshold: partial profiles remain valid inputs.

## Interpretation

Same-item gaps are descriptive only. Registered P4 and role interactions remain
heuristic and require human review. Unregistered pairs and missing measurements remain
UNKNOWN. Missing catalog values are not evidence of compatibility or incompatibility.
No authoritative scalar, compatibility percentage, ranking, or empirical prediction
is introduced.

## API rollout

The helper is additive and does not change the existing POST /compatibility route.
The canonical endpoint exposes the explicit coverage object. This is an implementation
baseline, not an empirically validated predictive service.


## Result semantics and context boundary

The response adds `result_semantics` so clients can distinguish:
- `DESCRIPTIVE_ONLY`: observed same-item gaps, without a compatibility verdict;
- `DESCRIPTIVE_WITH_GAPS`: descriptive observations plus unknown rows;
- `CONDITIONAL_HEURISTICS`: conditional rules requiring human review;
- `MIXED_DESCRIPTIVE_AND_CONDITIONAL`: both evidence classes are present;
- `UNKNOWN_ONLY`: no descriptive or registered heuristic finding is available.

Counts are provided separately for descriptive, heuristic, and unknown rows. The legacy
top-level `status` remains for compatibility and must not be interpreted as a validated
compatibility estimate.

Context labels are currently annotations only. They are returned for traceability but do
not alter rule outcomes; context-specific calibration is not implemented. This explicit
boundary prevents consumers from mistaking context metadata for context-aware inference.


## Heuristic rule catalog

Responses expose `rule_catalog` keyed by stable rule IDs. Each entry states its rule kind,
domain, evidence class, validation status, whether human review is required, whether
context-specific behavior is implemented, and intended use. Every current heuristic is
marked `UNVALIDATED_HEURISTIC`, requires human review, is not context-sensitive, and is
intended only as a prompt for review—not as a recommendation or prediction. Rows with no
registered rule remain `UNKNOWN` and have no fabricated rule ID.

The catalog makes implementation status auditable; it is not empirical evidence and does
not turn heuristics into validated findings.
