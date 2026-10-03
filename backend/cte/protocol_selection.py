"""Conservative, non-ranking protocol candidate selection.

This module selects reviewable options from an explicitly supplied protocol registry.
It does not prescribe interventions, infer clinical conditions, or establish efficacy.
"""
from __future__ import annotations

from math import isfinite
from typing import Any, Mapping, Sequence

DOMAINS = frozenset({"P1", "P2", "P3", "P4", "P5"})
SAFETY_STATES = frozenset({"PASS", "BLOCK", "UNKNOWN"})
REGISTRY_STATES = frozenset({"ACTIVE", "SUSPENDED", "RETIRED", "DRAFT"})
SCIENTIFIC_STATUS = "IMPLEMENTATION_BASELINE"


def _string_set(value: Any, field: str) -> set[str]:
    if not isinstance(value, (list, tuple, set, frozenset)):
        raise ValueError(f"{field} must be a list of strings")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError(f"{field} must contain non-empty strings")
    return {item.strip() for item in value}


def _finite_number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(float(value)):
        raise ValueError(f"{field} must be a finite number")
    return float(value)


def _validate_protocol(protocol: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(protocol, Mapping):
        raise ValueError("each protocol must be an object")
    protocol_id = protocol.get("protocol_id")
    version = protocol.get("version")
    if not isinstance(protocol_id, str) or not protocol_id.strip():
        raise ValueError("protocol_id must be a non-empty string")
    if not isinstance(version, str) or not version.strip():
        raise ValueError(f"{protocol_id}.version must be a non-empty string")
    status = protocol.get("status", "DRAFT")
    if status not in REGISTRY_STATES:
        raise ValueError(f"{protocol_id}.status is unsupported")
    required_measurements = _string_set(protocol.get("required_measurements", []), f"{protocol_id}.required_measurements")
    for item_id in required_measurements:
        if item_id.split(".", 1)[0] not in DOMAINS or "." not in item_id:
            raise ValueError(f"{protocol_id} has a non-canonical measurement ID: {item_id}")
    required_state = protocol.get("required_state", {})
    if not isinstance(required_state, Mapping):
        raise ValueError(f"{protocol_id}.required_state must be an object")
    contraindications = _string_set(protocol.get("contraindications", []), f"{protocol_id}.contraindications")
    goal_tags = _string_set(protocol.get("goal_tags", []), f"{protocol_id}.goal_tags")
    context_tags = _string_set(protocol.get("context_tags", []), f"{protocol_id}.context_tags")
    minimum_capacity = protocol.get("minimum_capacity")
    if minimum_capacity is not None:
        minimum_capacity = _finite_number(minimum_capacity, f"{protocol_id}.minimum_capacity")
        if not 0 <= minimum_capacity <= 10:
            raise ValueError(f"{protocol_id}.minimum_capacity must be between 0 and 10")
    evidence_class = protocol.get("evidence_class", "UNSPECIFIED")
    if not isinstance(evidence_class, str) or not evidence_class.strip():
        raise ValueError(f"{protocol_id}.evidence_class must be a non-empty string")
    return {
        "protocol_id": protocol_id.strip(),
        "version": version.strip(),
        "status": status,
        "required_measurements": required_measurements,
        "required_state": dict(required_state),
        "contraindications": contraindications,
        "goal_tags": goal_tags,
        "context_tags": context_tags,
        "minimum_capacity": minimum_capacity,
        "evidence_class": evidence_class.strip(),
        "requires_human_review": bool(protocol.get("requires_human_review", True)),
    }


def select_protocol_candidates(
    protocols: Sequence[Mapping[str, Any]],
    profile: Mapping[str, Any],
    state: Mapping[str, Any],
    *,
    goals: Sequence[str] = (),
    contexts: Sequence[str] = (),
    constraints: Sequence[str] = (),
    capacity: float | None = None,
    safety_status: str = "UNKNOWN",
) -> dict[str, Any]:
    """Return protocol options with explicit reasons, never a score or winner.

    A safety BLOCK makes all protocols ineligible. UNKNOWN safety or missing required
    inputs prevents eligibility. Every result remains a candidate for human review;
    selection is not authorization to execute an intervention.
    """
    if not isinstance(profile, Mapping) or not isinstance(state, Mapping):
        raise ValueError("profile and state must be objects")
    if safety_status not in SAFETY_STATES:
        raise ValueError("safety_status must be PASS, BLOCK, or UNKNOWN")
    goal_set = _string_set(goals, "goals")
    context_set = _string_set(contexts, "contexts")
    constraint_set = _string_set(constraints, "constraints")
    if capacity is not None:
        capacity = _finite_number(capacity, "capacity")
        if not 0 <= capacity <= 10:
            raise ValueError("capacity must be between 0 and 10")

    candidates = []
    seen_ids = set()
    for raw_protocol in protocols:
        p = _validate_protocol(raw_protocol)
        if p["protocol_id"] in seen_ids:
            raise ValueError(f"duplicate protocol_id: {p['protocol_id']}")
        seen_ids.add(p["protocol_id"])
        reasons: list[str] = []
        status = "ELIGIBLE_FOR_REVIEW"

        if p["status"] != "ACTIVE":
            status = "INELIGIBLE"
            reasons.append(f"registry_status:{p['status']}")
        elif safety_status == "BLOCK":
            status = "INELIGIBLE"
            reasons.append("safety_gate:BLOCK")
        elif p["contraindications"] & constraint_set:
            status = "INELIGIBLE"
            reasons.append("active_contraindication")
        elif p["goal_tags"] and not (p["goal_tags"] & goal_set):
            status = "NOT_MATCHED"
            reasons.append("no_matching_goal_tag")
        elif p["context_tags"] and not (p["context_tags"] & context_set):
            status = "NOT_MATCHED"
            reasons.append("no_matching_context_tag")
        else:
            missing = sorted(item for item in p["required_measurements"] if profile.get(item) is None)
            missing_state = sorted(key for key in p["required_state"] if state.get(key) is None)
            if missing or missing_state:
                status = "INSUFFICIENT_DATA"
                if missing:
                    reasons.append("missing_measurements:" + ",".join(missing))
                if missing_state:
                    reasons.append("missing_state:" + ",".join(missing_state))
            else:
                failed_state = sorted(key for key, expected in p["required_state"].items() if state.get(key) != expected)
                if failed_state:
                    status = "INELIGIBLE"
                    reasons.append("required_state_mismatch:" + ",".join(failed_state))
                if p["minimum_capacity"] is not None and capacity is None:
                    status = "INSUFFICIENT_DATA"
                    reasons.append("capacity_required")
                elif p["minimum_capacity"] is not None and capacity < p["minimum_capacity"]:
                    status = "INELIGIBLE"
                    reasons.append("below_minimum_capacity")
                if safety_status == "UNKNOWN" and status == "ELIGIBLE_FOR_REVIEW":
                    status = "CONDITIONAL"
                    reasons.append("safety_gate:UNKNOWN")

        candidates.append({
            "protocol_id": p["protocol_id"],
            "version": p["version"],
            "status": status,
            "reasons": reasons or ["declared_requirements_satisfied"],
            "evidence_class": p["evidence_class"],
            "requires_human_review": True,
            "registry_requires_human_review": p["requires_human_review"],
            "selection_authorized": False,
        })

    return {
        "selector_version": "1.0",
        "scientific_status": SCIENTIFIC_STATUS,
        "safety_status": safety_status,
        "authoritative_scalar": False,
        "ranked": False,
        "selection_authorized": False,
        "candidates": candidates,
    }
