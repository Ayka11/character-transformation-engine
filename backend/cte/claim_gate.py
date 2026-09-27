"""Executable claim-state gate for Evidence Graph V1.4."""
from __future__ import annotations
from .claim_state_machine import validate_transition

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
    if target_level not in CLAIM_LEVELS:
        raise ValueError("unsupported claim level")
    requirements=set(upstream_types)
    state_gate=validate_transition(current_state,target_level,requirements)
    if target_level=="EVIDENCE_SUPPORTED" and provenance_class!="EVD":
        raise ValueError("EVIDENCE_SUPPORTED requires EVD provenance")
    legacy_required=REQUIRED_UPSTREAM.get(target_level,set())
    missing=legacy_required-requirements
    if missing:
        raise ValueError("claim gate missing upstream: "+",".join(sorted(missing)))
    return {**state_gate,"claim_level":target_level,"from_state":current_state,"provenance_class":provenance_class}
