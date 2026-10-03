"""Strict adapters from canonical Master Matrix items to Compatibility Matrix V2."""
from __future__ import annotations

from math import isfinite
from typing import Any, Mapping, Sequence

from .compatibility_matrix import evaluate_compatibility_matrix
from .master_matrix import MATRIX_VERSION, get_matrix_item


def _validated_item_value(item_id: str, raw_value: Any, *, person: str):
    try:
        item = get_matrix_item(item_id)
    except KeyError as exc:
        raise ValueError(f"{person}.{item_id} is not a registered Master Matrix item") from exc
    if isinstance(raw_value, bool) or not isinstance(raw_value, (int, float)) or not isfinite(float(raw_value)):
        raise ValueError(f"{person}.{item_id} must be a finite number")
    try:
        lower, upper = (float(part) for part in item.scale.split("-", maxsplit=1))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{item_id} has an unsupported canonical scale: {item.scale!r}") from exc
    value = float(raw_value)
    if not lower <= value <= upper:
        raise ValueError(f"{person}.{item_id} must be within the declared {item.scale} scale")
    return item, value


def canonical_value_profile(profile: Mapping[str, Any], *, person: str = "profile") -> dict[str, float]:
    """Validate canonical P4 item IDs and translate them to Matrix V2 value labels."""
    normalized = {}
    for item_id, raw_value in profile.items():
        item, value = _validated_item_value(item_id, raw_value, person=person)
        if item.domain != "P4" or item.kind != "value":
            raise ValueError(f"{person}.{item_id} must be a canonical P4 value item")
        normalized[item.name] = value
    return normalized


def canonical_measurement_profile(profile: Mapping[str, Any], *, person: str = "profile") -> dict[str, float]:
    """Validate P1–P5 canonical IDs, keeping non-P4 keys canonical."""
    normalized = {}
    for item_id, raw_value in profile.items():
        item, value = _validated_item_value(item_id, raw_value, person=person)
        key = item.name if item.domain == "P4" and item.kind == "value" else item.id
        if key in normalized:
            raise ValueError(f"{person} contains duplicate normalized measurement key: {key}")
        normalized[key] = value
    return normalized


def _provenance(profile: Mapping[str, Any]) -> list[dict[str, str]]:
    records = []
    for item_id in sorted(profile):
        item = get_matrix_item(item_id)
        records.append({
            "canonical_id": item.id,
            "domain": item.domain,
            "kind": item.kind,
            "scale": item.scale,
            "direction": item.direction,
            "provenance_tag": item.provenance_tag,
        })
    return records


def evaluate_canonical_value_compatibility(profile_a: Mapping[str, Any], profile_b: Mapping[str, Any], *, contexts: Sequence[str] = ()) -> dict[str, Any]:
    """Evaluate P4 values without inferring missing data."""
    a = canonical_value_profile(profile_a, person="profile_a")
    b = canonical_value_profile(profile_b, person="profile_b")
    result = evaluate_compatibility_matrix(a, b, contexts=contexts)
    result["input_contract"] = {
        "matrix_version": MATRIX_VERSION, "domain": "P4", "scale": "0-10",
        "canonical_ids_required": True,
        "profile_a_provenance": _provenance(profile_a),
        "profile_b_provenance": _provenance(profile_b),
    }
    return result


def evaluate_canonical_compatibility(profile_a: Mapping[str, Any], profile_b: Mapping[str, Any], *, roles_a: Sequence[str] = (), roles_b: Sequence[str] = (), contexts: Sequence[str] = ()) -> dict[str, Any]:
    """Evaluate canonical measurements across P1–P5 with descriptive gaps only."""
    a = canonical_measurement_profile(profile_a, person="profile_a")
    b = canonical_measurement_profile(profile_b, person="profile_b")
    result = evaluate_compatibility_matrix(a, b, roles_a=roles_a, roles_b=roles_b, contexts=contexts)
    result["input_contract"] = {
        "matrix_version": MATRIX_VERSION,
        "domains_supported": ["P1", "P2", "P3", "P4", "P5"],
        "canonical_ids_required": True,
        "scale_validation": "per canonical item",
        "profile_a_provenance": _provenance(profile_a),
        "profile_b_provenance": _provenance(profile_b),
    }
    return result
