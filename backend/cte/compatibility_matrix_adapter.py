"""Strict adapter between canonical Master Matrix P4 values and Matrix V2.

Only registered P4 value IDs on the declared 0–10 scale are accepted. This
prevents accidental comparison of unrelated measures or silently mismatched keys.
"""
from __future__ import annotations

from math import isfinite
from typing import Any, Mapping, Sequence

from .compatibility_matrix import evaluate_compatibility_matrix
from .master_matrix import get_matrix_item


def canonical_value_profile(profile: Mapping[str, Any], *, person: str = "profile") -> dict[str, float]:
    """Validate canonical P4 item IDs and translate them to Matrix V2 value labels."""
    normalized: dict[str, float] = {}
    for item_id, raw_value in profile.items():
        try:
            item = get_matrix_item(item_id)
        except KeyError as exc:
            raise ValueError(f"{person}.{item_id} is not a registered Master Matrix item") from exc
        if item.domain != "P4" or item.kind != "value":
            raise ValueError(f"{person}.{item_id} must be a canonical P4 value item")
        if (
            isinstance(raw_value, bool)
            or not isinstance(raw_value, (int, float))
            or not isfinite(float(raw_value))
        ):
            raise ValueError(f"{person}.{item_id} must be a finite number")
        value = float(raw_value)
        if not 0 <= value <= 10:
            raise ValueError(f"{person}.{item_id} must be within the declared 0–10 scale")
        normalized[item.name] = value
    return normalized


def evaluate_canonical_value_compatibility(
    profile_a: Mapping[str, Any],
    profile_b: Mapping[str, Any],
    *,
    contexts: Sequence[str] = (),
) -> dict[str, Any]:
    """Evaluate value findings from canonical P4 IDs without inferring missing values."""
    a = canonical_value_profile(profile_a, person="profile_a")
    b = canonical_value_profile(profile_b, person="profile_b")
    result = evaluate_compatibility_matrix(a, b, contexts=contexts)
    result["input_contract"] = {
        "matrix_version": "1.0",
        "domain": "P4",
        "scale": "0-10",
        "canonical_ids_required": True,
    }
    return result
