# Replication & Generalization Runtime Status

V1.5 executable baseline is now implemented on top of the in-memory Evidence Graph Registry.

## Replication

Implemented:
- preregistered replication specifications;
- independent replication run registration;
- outcome comparison for direction, effect compatibility, interval overlap, protocol fidelity, measurement fidelity, outcome definition and data quality;
- explicit REPLICATED, PARTIAL, NOT_REPLICATED, and NOT_ESTIMABLE statuses;
- immutable graph assessment nodes linked to the source RESULT.

Unknown inputs are not silently treated as matches. Replication is not reduced to a p-value decision.

## Generalization

Implemented:
- source/target transport specification registration;
- generalization run registration;
- transport error and heterogeneity fields;
- explicit transport-dimension statuses;
- GENERALIZABLE, LIMITED_GENERALIZABILITY, NOT_GENERALIZABLE, and NOT_ESTIMABLE outcomes;
- immutable graph assessment nodes linked to the source RESULT.

## Claim integration

REPLICATED_RESULT requires a graph-linked replication assessment with independent=true, criteria_registered=true, and assessment_status=REPLICATED.

GENERALIZED_RESULT requires a graph-linked generalization assessment with run_status=COMPLETED, result_status=GENERALIZABLE, and declared target population/context.

These are implementation gates, not empirical validation claims. The repository's V1.5 SQL/API specifications remain the persistence and contract references.
