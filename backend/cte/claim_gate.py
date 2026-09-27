"""Executable claim-state gate for Evidence Graph V1.4.

The graph registry supplies semantic prerequisites while direct legacy callers
may still provide graph node-type names. Both forms are normalized here.
"""
from __future__ import annotations
from .claim_state_machine import validate_transition

CLAIM_LEVELS = (
    "REGISTERED",
    "DESCRIPTIVE_RESULT",
    "ASSOCIATIONAL_RESULT",
    "INTERVENTION_RESULT",
    "REPLICATED_RESULT",
    "GENERALIZED_RESULT",
    "EVIDENCE_SUPPORTED",
    "CONTRADICTED",
    "INDETERMINATE",
)

LEGACY_UPSTREAM = {
    "REGISTERED": set(),
    "DESCRIPTIVE_RESULT": {"RESULT"},
    "ASSOCIATIONAL_RESULT": {"RESULT"},
    "INTERVENTION_RESULT": {"RESULT", "PROTOCOL"},
    "REPLICATED_RESULT": {"RESULT", "REPLICATION"},
    "GENERALIZED_RESULT": {"RESULT", "REPLICATION", "GENERALIZATION"},
    "EVIDENCE_SUPPORTED": {"RESULT", "REPLICATION", "GENERALIZATION"},
    "CONTRADICTED": {"RESULT"},
    "INDETERMINATE": {"RESULT"},
}

SEMANTIC_REQUIREMENTS = {
    "REGISTERED": {"claim_registration"},
    "DESCRIPTIVE_RESULT": {"valid_result"},
    "ASSOCIATIONAL_RESULT": {"valid_result"},
    "INTERVENTION_RESULT": {"valid_result", "registered_intervention"},
    "REPLICATED_RESULT": {"independent_replication", "registered_replication_criteria"},
    "GENERALIZED_RESULT": {"generalization_run", "target_population_context"},
    "EVIDENCE_SUPPORTED": {"registered_evidence_criteria", "complete_provenance"},
    "CONTRADICTED": {"unresolved_material_contradiction"},
    "INDETERMINATE": {"insufficient_or_conflicting_information"},
}

def _normalize_legacy_requirements(original: set[str]) -> set[str]:
    normalized=set()
    if "RESULT" in original:
        normalized.add("valid_result")
    if "PROTOCOL" in original:
        normalized.add("registered_intervention")
    if "REPLICATION" in original:
        normalized.update({"independent_replication", "registered_replication_criteria"})
    if "GENERALIZATION" in original:
        normalized.update({"generalization_run", "target_population_context"})
    return normalized

def validate_claim_transition(current_state: str, target_level: str, upstream_types: set[str], provenance_class: str = "DRV") -> dict:
    if target_level not in CLAIM_LEVELS:
        raise ValueError("unsupported claim level")
    original=set(upstream_types)
    legacy_mode=bool(original.intersection({"RESULT", "PROTOCOL", "REPLICATION", "GENERALIZATION"}))
    normalized=set(upstream_types)
    if legacy_mode:
        missing=LEGACY_UPSTREAM[target_level]-original
        if missing:
            raise ValueError("claim gate missing upstream: "+",".join(sorted(missing)))
        normalized |= _normalize_legacy_requirements(original)
    missing_semantic=SEMANTIC_REQUIREMENTS[target_level]-normalized
    if missing_semantic:
        raise ValueError("claim transition missing requirements: "+",".join(sorted(missing_semantic)))
    if target_level=="EVIDENCE_SUPPORTED" and provenance_class!="EVD":
        raise ValueError("EVIDENCE_SUPPORTED requires EVD provenance")
    state_gate=validate_transition(current_state,target_level,normalized)
    return {**state_gate,"claim_level":target_level,"from_state":current_state,"provenance_class":provenance_class}
