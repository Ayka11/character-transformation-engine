# Claim Gate Runtime Status

The executable Claim Gate is now present in `backend/cte/claim_gate.py` and exposed as `POST /graph/claim-gate`.

Rules enforced:
- DESCRIPTIVE_RESULT and ASSOCIATIONAL_RESULT require RESULT.
- INTERVENTION_RESULT requires RESULT + PROTOCOL.
- REPLICATED_RESULT requires RESULT + REPLICATION.
- GENERALIZED_RESULT requires RESULT + REPLICATION + GENERALIZATION.
- EVIDENCE_SUPPORTED requires RESULT + REPLICATION + GENERALIZATION and EVD provenance.

Missing upstream evidence blocks the transition. The gate does not invent lineage or promote model-derived provenance to empirical evidence.

This is an executable contract boundary; empirical validation and persistent graph storage are separate layers.
