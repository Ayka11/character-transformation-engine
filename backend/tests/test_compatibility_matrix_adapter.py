import pytest

from cte.compatibility_matrix_adapter import (
    canonical_measurement_profile,
    canonical_value_profile,
    evaluate_canonical_compatibility,
    evaluate_canonical_value_compatibility,
)


def test_canonical_value_ids_translate_to_registered_labels():
    assert canonical_value_profile({"P4.value_autonomy": 8, "P4.value_order": 3}) == {"Autonomy": 8.0, "Order": 3.0}


def test_canonical_evaluation_emits_contract_and_heuristic_review():
    result = evaluate_canonical_value_compatibility(
        {"P4.value_order": 8, "P4.value_autonomy": 3},
        {"P4.value_order": 7, "P4.value_autonomy": 4}, contexts=["work"],
    )
    assert result["input_contract"]["matrix_version"] == "1.0"
    assert result["input_contract"]["domain"] == "P4"
    assert result["input_contract"]["profile_a_provenance"][0]["canonical_id"].startswith("P4.")
    tension = next(row for row in result["rows"] if row["kind"] == "VALUE_TENSION")
    assert tension["status"] == "CONDITIONAL"
    assert tension["requires_human_review"] is True


@pytest.mark.parametrize("item_id", ["Autonomy", "P2.big5_openness", "P1.sleep_quality", "P4.value_not_registered"])
def test_noncanonical_or_non_p4_keys_are_rejected(item_id):
    with pytest.raises(ValueError):
        canonical_value_profile({item_id: 5})


@pytest.mark.parametrize("value", [-0.1, 10.1, float("nan"), float("inf"), True, "5"])
def test_values_must_follow_finite_0_to_10_contract(value):
    with pytest.raises(ValueError):
        canonical_value_profile({"P4.value_autonomy": value})


def test_missing_value_is_not_imputed():
    result = evaluate_canonical_value_compatibility({"P4.value_order": 8}, {"P4.value_autonomy": 6})
    assert result["status"] == "PARTIAL"
    assert all(row["status"] == "UNKNOWN" for row in result["rows"])


@pytest.mark.parametrize("item_id", ["P1.sleep_quality", "P2.big5_openness", "P3.impulse_control", "P4.value_autonomy", "P5.adaptability"])
def test_general_adapter_accepts_registered_items_from_all_domains(item_id):
    assert canonical_measurement_profile({item_id: 5})


def test_general_adapter_keeps_non_p4_measurements_keyed_by_canonical_id():
    profile = canonical_measurement_profile({
        "P1.sleep_quality": 7, "P2.big5_openness": 6, "P3.impulse_control": 5,
        "P4.value_autonomy": 8, "P5.adaptability": 4,
    })
    assert set(profile) == {"P1.sleep_quality", "P2.big5_openness", "P3.impulse_control", "Autonomy", "P5.adaptability"}


def test_all_domain_evaluation_preserves_provenance_and_unknowns():
    result = evaluate_canonical_compatibility(
        {"P1.sleep_quality": 7, "P4.value_order": 8},
        {"P1.sleep_quality": 6, "P4.value_autonomy": 7}, contexts=["work"],
    )
    contract = result["input_contract"]
    assert contract["domains_supported"] == ["P1", "P2", "P3", "P4", "P5"]
    assert {r["canonical_id"] for r in contract["profile_a_provenance"]} == {"P1.sleep_quality", "P4.value_order"}
    assert result["status"] == "PARTIAL"
    assert any(row["status"] == "UNKNOWN" for row in result["rows"])


@pytest.mark.parametrize("item_id", ["P1.sleep_quality", "P2.big5_openness", "P3.impulse_control", "P5.adaptability"])
@pytest.mark.parametrize("value", [-0.1, 10.1, float("nan"), float("inf"), True, "5"])
def test_all_domain_adapter_enforces_canonical_scale(item_id, value):
    with pytest.raises(ValueError):
        canonical_measurement_profile({item_id: value})
