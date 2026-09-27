"""Executable claim state-machine enforcement aligned to Evidence Graph V1.4/V1.9 tests.

The state machine remains conservative for evidence promotion while retaining
backward-compatible transition paths used by the repository's existing runtime tests.
"""
from __future__ import annotations

ALLOWED_TRANSITIONS = {
    ("HYPOTHESIS", "REGISTERED"): {"claim_registration"},
    ("REGISTERED", "DESCRIPTIVE_RESULT"): {"validated_descriptive_result"},
    ("REGISTERED", "ASSOCIATIONAL_RESULT"): {"registered_analysis", "valid_result", "association_design"},
    ("REGISTERED", "INTERVENTION_RESULT"): {"registered_intervention", "valid_result"},
    ("DESCRIPTIVE_RESULT", "INTERVENTION_RESULT"): {"registered_intervention", "valid_result"},
    ("ASSOCIATIONAL_RESULT", "REPLICATED_RESULT"): {"independent_replication", "registered_replication_criteria"},
    ("INTERVENTION_RESULT", "REPLICATED_RESULT"): {"independent_replication", "registered_replication_criteria"},
    ("REPLICATED_RESULT", "GENERALIZED_RESULT"): {"generalization_run", "target_population_context"},
    ("REPLICATED_RESULT", "EVIDENCE_SUPPORTED"): {"registered_evidence_criteria", "complete_provenance"},
    ("GENERALIZED_RESULT", "EVIDENCE_SUPPORTED"): {"registered_evidence_criteria", "complete_provenance"},
}

TERMINAL_RULES = {
    "CONTRADICTED": "unresolved_material_contradiction",
    "INDETERMINATE": "insufficient_or_conflicting_information",
}

def transition_requirements(current_state: str, target_state: str) -> set[str]:
    if target_state in TERMINAL_RULES:
        return {TERMINAL_RULES[target_state]}
    return ALLOWED_TRANSITIONS.get((current_state, target_state), set())

def validate_transition(current_state: str, target_state: str, available_requirements: set[str]) -> dict:
    required = transition_requirements(current_state, target_state)
    if not required:
        raise ValueError(f"unsupported claim transition: {current_state} -> {target_state}")
    missing = required - set(available_requirements)
    if missing:
        raise ValueError("claim transition missing requirements: " + ",".join(sorted(missing)))
    return {
        "allowed": True,
        "from_state": current_state,
        "to_state": target_state,
        "requirements": sorted(required),
    }
