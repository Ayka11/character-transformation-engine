import pytest

from cte.compatibility_matrix_adapter import (
    canonical_value_profile,
    evaluate_canonical_value_compatibility,
)


def test_canonical_value_ids_translate_to_registered_labels():
    assert canonical_value_profile({
        "P4.value_autonomy": 8,
        "P4.value_order": 3,
    }) == {"Autonomy": 8.0, "Order": 3.0}


def test_canonical_evaluation_emits_contract_and_heuristic_review():
    result = evaluate_canonical_value_compatibility(
        {"P4.value_order": 8, "P4.value_autonomy": 3},
        {"P4.value_order": 7, "P4.value_autonomy": 4},
        contexts=["work"],
    )
    assert result["input_contract"] == {
        "matrix_version": "1.0",
        "domain": "P4",
        "scale": "0-10",
        "canonical_ids_required": True,
    }
    tension = next(row for row in result["rows"] if row["kind"] == "VALUE_TENSION")
    assert tension["status"] == "CONDITIONAL"
    assert tension["requires_human_review"] is True


@pytest.mark.parametrize("item_id", [
    "Autonomy",
    "P2.big5_openness",
    "P1.sleep_quality",
    "P4.value_not_registered",
])
def test_noncanonical_or_non_p4_keys_are_rejected(item_id):
    with pytest.raises(ValueError):
        canonical_value_profile({item_id: 5})


@pytest.mark.parametrize("value", [-0.1, 10.1, float("nan"), float("inf"), True, "5"])
def test_values_must_follow_finite_0_to_10_contract(value):
    with pytest.raises(ValueError):
        canonical_value_profile({"P4.value_autonomy": value})


def test_missing_value_is_not_imputed():
    result = evaluate_canonical_value_compatibility(
        {"P4.value_order": 8},
        {"P4.value_autonomy": 6},
    )
    assert result["status"] == "PARTIAL"
    assert all(row["status"] == "UNKNOWN" for row in result["rows"])
