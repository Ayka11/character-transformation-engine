"""Executable claim-state gate for Evidence Graph V1.4."""
from __future__ import annotations

CLAIM_LEVELS=("DESCRIPTIVE_RESULT","ASSOCIATIONAL_RESULT","INTERVENTION_RESULT","REPLICATED_RESULT","GENERALIZED_RESULT","EVIDENCE_SUPPORTED")
REQUIRED_UPSTREAM={
"DESCRIPTIVE_RESULT":{"RESULT"},
"ASSOCIATIONAL_RESULT":{"RESULT"},
"INTERVENTION_RESULT":{"RESULT","PROTOCOL"},
"REPLICATED_RESULT":{"RESULT","REPLICATION"},
"GENERALIZED_RESULT":{"RESULT","REPLICATION","GENERALIZATION"},
"EVIDENCE_SUPPORTED":{"RESULT","REPLICATION","GENERALIZATION"},
}
def validate_claim_transition(current_state:str,target_level:str,upstream_types:set[str],provenance_class:str="DRV")->dict:
    if target_level not in CLAIM_LEVELS: raise ValueError("unsupported claim level")
    if target_level=="EVIDENCE_SUPPORTED" and provenance_class!="EVD":
        raise ValueError("EVIDENCE_SUPPORTED requires EVD provenance")
    missing=REQUIRED_UPSTREAM[target_level]-set(upstream_types)
    if missing:
        raise ValueError("claim gate missing upstream: "+",".join(sorted(missing)))
    return {"allowed":True,"claim_level":target_level,"from_state":current_state,"provenance_class":provenance_class}
