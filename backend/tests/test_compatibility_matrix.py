import pytest
from cte.compatibility_matrix import evaluate_compatibility_matrix

def test_empty_profiles_return_unknown_without_scalar():
    result = evaluate_compatibility_matrix({}, {})
    assert result["status"] == "UNKNOWN"
    assert result["authoritative_scalar"] is False
    assert result["coverage"] == {"known_rows": 0, "total_rows": 0, "unknown_rows": 0}

def test_missing_trait_measurements_remain_unknown():
    result = evaluate_compatibility_matrix({"Honesty": 4}, {"Autonomy": 3})
    assert result["status"] == "PARTIAL"
    assert result["coverage"]["unknown_rows"] == 2
    assert all(row["status"] == "UNKNOWN" for row in result["rows"])

def test_observed_numeric_gap_is_descriptive_not_a_verdict():
    result = evaluate_compatibility_matrix({"Honesty": 9}, {"Honesty": 2})
    row = result["rows"][0]
    assert row["gap"] == 7
    assert row["status"] == "OBSERVED_ALIGNMENT"
    assert row["evidence_class"] == "DESCRIPTIVE"
    assert result["authoritative_scalar"] is False

def test_value_tension_is_conditional_and_requires_review():
    result = evaluate_compatibility_matrix(
        {"Order": 9, "Autonomy": 2}, {"Order": 8, "Autonomy": 3}, contexts=["work"])
    row = next(item for item in result["rows"] if item["kind"] == "VALUE_TENSION")
    assert row["status"] == "CONDITIONAL"
    assert row["evidence_class"] == "HEURISTIC"
    assert row["requires_human_review"] is True
    assert row["contexts"] == ["work"]

def test_role_rules_are_heuristic_and_unregistered_pairs_unknown():
    result = evaluate_compatibility_matrix({}, {}, roles_a=["Leader"], roles_b=["Leader", "Artist"])
    competition = next(item for item in result["rows"] if item["pair"] == ["Leader", "Leader"])
    unknown = next(item for item in result["rows"] if item["pair"] == ["Leader", "Artist"])
    assert competition["interaction"] == "COMPETITION"
    assert competition["status"] == "CONDITIONAL"
    assert unknown["status"] == "UNKNOWN"

@pytest.mark.parametrize("value", [float("nan"), float("inf"), True, "high"])
def test_non_finite_or_non_numeric_profile_values_rejected(value):
    with pytest.raises(ValueError):
        evaluate_compatibility_matrix({"trait": value}, {})



def test_result_semantics_labels_descriptive_only_without_calling_it_compatibility():
    result = evaluate_compatibility_matrix({"Honesty": 9}, {"Honesty": 2})
    semantics = result["result_semantics"]
    assert semantics["interpretation"] == "DESCRIPTIVE_ONLY"
    assert semantics["descriptive_row_count"] == 1
    assert semantics["heuristic_row_count"] == 0
    assert semantics["unknown_row_count"] == 0
    assert semantics["context_semantics"] == "ANNOTATION_ONLY"
    assert "not a validated compatibility estimate" in semantics["warning"]


def test_context_labels_do_not_silently_change_rule_outcomes():
    baseline = evaluate_compatibility_matrix({"Order": 8, "Autonomy": 3}, {"Order": 7, "Autonomy": 4})
    contextual = evaluate_compatibility_matrix(
        {"Order": 8, "Autonomy": 3}, {"Order": 7, "Autonomy": 4}, contexts=["work", "family"]
    )
    assert [(r["kind"], r["status"], r.get("rule_id")) for r in baseline["rows"]] == [
        (r["kind"], r["status"], r.get("rule_id")) for r in contextual["rows"]
    ]
    assert contextual["contexts"] == ["family", "work"]
    assert contextual["result_semantics"]["context_semantics"] == "ANNOTATION_ONLY"


def test_unknown_only_result_is_not_described_as_a_compatibility_estimate():
    result = evaluate_compatibility_matrix({"Honesty": 4}, {"Autonomy": 3})
    assert result["result_semantics"]["interpretation"] == "UNKNOWN_ONLY"
    assert result["result_semantics"]["unknown_row_count"] == 2
