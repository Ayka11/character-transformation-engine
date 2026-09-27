# Evidence Graph Result Boundary

Validation results now have a canonical graph-ready representation.

A RESULT node contains:
- result_id
- analysis_id
- manifest_id
- analysis_spec_id
- QC status
- sample count
- estimate
- confidence interval when estimable
- immutable provenance hash

The node is explicitly `DRV`. It is not automatically EVD and it is not a CLAIM.

This enforces the graph contract:

DATASET -> ANALYSIS -> RESULT -> (future registered Claim derivation)

The missing transition remains deliberate: a result cannot skip replication/generalization/evidence criteria merely because an estimate or confidence interval exists.
