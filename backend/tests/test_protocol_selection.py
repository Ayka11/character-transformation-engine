import pytest

from cte.protocol_selection import select_protocol_candidates


def protocol(**overrides):
    base = {
        "protocol_id": "regulation.pause",
        "version": "1.0",
        "status": "ACTIVE",
        "required_measurements": ["P3.pause_capacity"],
        "required_state": {"sprint_status": "ACTIVE"},
        "goal_tags": ["self_regulation"],
        "context_tags": ["work"],
        "contraindications": ["acute_crisis"],
        "minimum_capacity": 4,
        "evidence_class": "MODEL_DERIVED",
    }
    return {**base, **overrides}


def select(p, **kwargs):
    defaults = {
        "profile": {"P3.pause_capacity": 6},
        "state": {"sprint_status": "ACTIVE"},
        "goals": ["self_regulation"],
        "contexts": ["work"],
        "capacity": 6,
        "safety_status": "PASS",
    }
    defaults.update(kwargs)
    return select_protocol_candidates([p], **defaults)["candidates"][0]


def test_matching_candidate_is_reviewable_not_authorized():
    result = select(protocol())
    assert result["status"] == "ELIGIBLE_FOR_REVIEW"
    assert result["selection_authorized"] is False
    assert result["requires_human_review"] is True


def test_safety_block_excludes_all_protocols():
    result = select(protocol(), safety_status="BLOCK")
    assert result["status"] == "INELIGIBLE"
    assert "safety_gate:BLOCK" in result["reasons"]


def test_unknown_safety_never_returns_eligible():
    result = select(protocol(), safety_status="UNKNOWN")
    assert result["status"] == "CONDITIONAL"
    assert "safety_gate:UNKNOWN" in result["reasons"]


def test_missing_required_measurement_is_not_imputed():
    result = select(protocol(), profile={})
    assert result["status"] == "INSUFFICIENT_DATA"
    assert any(reason.startswith("missing_measurements:") for reason in result["reasons"])


def test_missing_capacity_is_insufficient_data():
    result = select(protocol(), capacity=None)
    assert result["status"] == "INSUFFICIENT_DATA"
    assert "capacity_required" in result["reasons"]


def test_contraindication_excludes_candidate():
    result = select(protocol(), constraints=["acute_crisis"])
    assert result["status"] == "INELIGIBLE"
    assert "active_contraindication" in result["reasons"]


def test_goal_and_context_mismatch_are_not_ranked_as_winners():
    result = select(protocol(), goals=["other"], contexts=["home"])
    assert result["status"] == "NOT_MATCHED"
    payload = select_protocol_candidates([protocol()], {}, {}, safety_status="BLOCK")
    assert payload["ranked"] is False
    assert payload["authoritative_scalar"] is False


def test_rejects_unknown_measurement_namespace():
    with pytest.raises(ValueError, match="non-canonical measurement ID"):
        select(protocol(required_measurements=["X9.fake"]))


def test_rejects_duplicate_protocol_ids():
    with pytest.raises(ValueError, match="duplicate protocol_id"):
        select_protocol_candidates([protocol(), protocol()], {}, {}, safety_status="PASS")


def test_inactive_protocol_is_not_a_candidate_for_execution():
    result = select(protocol(status="DRAFT"))
    assert result["status"] == "INELIGIBLE"
    assert "registry_status:DRAFT" in result["reasons"]
