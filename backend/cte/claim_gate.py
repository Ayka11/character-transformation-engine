"""Executable claim-state gate for Evidence Graph V1.4."""
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

REQUIRED_UPSTREAM = {
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

def validate_claim_transition(
    current_state: str,
    target_level: str,
    upstream_types: set[str],
    provenance_class: str = "DRV",
) -> dict:
    if target_level not in CLAIM_LEVELS:
        raise ValueError("unsupported claim level")

    requirements = set(upstream_types)
    legacy_required = REQUIRED_UPSTREAM.get(target_level, set())
    missing_upstream = legacy_required - requirements
    if missing_upstream:
        raise ValueError(
            "claim gate missing upstream: " + ",".join(sorted(missing_upstream))
        )

    if (
        current_state == "REGISTERED"
        and target_level == "DESCRIPTIVE_RESULT"
        and "RESULT" in requirements
    ):
        requirements.add("validated_descriptive_result")

    if current_state == "HYPOTHESIS" and target_level == "REGISTERED":
        requirements.add("claim_registration")

    if target_level == "EVIDENCE_SUPPORTED" and provenance_class != "EVD":
        raise ValueError("EVIDENCE_SUPPORTED requires EVD provenance")

    state_gate = validate_transition(current_state, target_level, requirements)
    return {
        **state_gate,
        "claim_level": target_level,
        "from_state": current_state,
        "provenance_class": provenance_class,
    }
