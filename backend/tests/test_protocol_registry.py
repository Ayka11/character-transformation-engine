import pytest

from cte.persistence import SQLiteRuntimeStore
from cte.protocol_registry import ProtocolRegistry


@pytest.fixture
def registry(tmp_path):
    return ProtocolRegistry(SQLiteRuntimeStore(str(tmp_path / "registry.sqlite3")))


def definition(**overrides):
    base = {
        "protocol_id": "regulation.pause", "version": "1.0", "status": "ACTIVE",
        "required_measurements": ["P3.pause_capacity"],
        "required_state": {"sprint_status": "ACTIVE"},
        "goal_tags": ["self_regulation"], "context_tags": ["work"],
        "contraindications": ["acute_crisis"], "minimum_capacity": 4,
        "evidence_class": "MODEL_DERIVED",
    }
    return {**base, **overrides}


def test_register_forces_draft_and_preserves_immutable_definition(registry):
    result = registry.register(definition(), actor_id="reviewer-1")
    assert result["lifecycle"] == "DRAFT"
    assert result["protocol"]["status"] == "DRAFT"
    original_hash = result["definition_hash"]
    with pytest.raises(ValueError, match="immutable snapshot conflict"):
        registry.register(definition(evidence_class="CHANGED"), actor_id="reviewer-1")
    assert registry.get("regulation.pause", "1.0")["definition_hash"] == original_hash


def test_lifecycle_history_is_append_only_and_transitions_are_guarded(registry):
    registry.register(definition(), actor_id="reviewer-1")
    active = registry.transition("regulation.pause", "1.0", target_status="ACTIVE",
                                 actor_id="approver-1", reason="review completed")
    assert active["previous_status"] == "DRAFT"
    assert active["lifecycle"] == "ACTIVE"
    suspended = registry.transition("regulation.pause", "1.0", target_status="SUSPENDED",
                                    actor_id="safety-officer", reason="investigation")
    assert suspended["lifecycle"] == "SUSPENDED"
    assert [e["payload"]["status"] for e in registry.history("regulation.pause", "1.0")] == [
        "DRAFT", "ACTIVE", "SUSPENDED"
    ]
    with pytest.raises(ValueError, match="invalid lifecycle transition"):
        registry.transition("regulation.pause", "1.0", target_status="DRAFT",
                            actor_id="reviewer-1", reason="cannot roll back lifecycle")


def test_retired_version_is_terminal_and_new_versions_are_separate(registry):
    registry.register(definition(), actor_id="reviewer-1")
    registry.transition("regulation.pause", "1.0", target_status="ACTIVE",
                        actor_id="approver-1", reason="approved")
    registry.transition("regulation.pause", "1.0", target_status="RETIRED",
                        actor_id="approver-1", reason="superseded")
    with pytest.raises(ValueError, match="invalid lifecycle transition"):
        registry.transition("regulation.pause", "1.0", target_status="ACTIVE",
                            actor_id="approver-1", reason="reactivation forbidden")
    result = registry.register(definition(version="2.0"), actor_id="reviewer-1")
    assert result["lifecycle"] == "DRAFT"
    assert len(registry.list_versions("regulation.pause")) == 2


def test_unknown_protocol_version_and_missing_actor_are_rejected(registry):
    with pytest.raises(KeyError):
        registry.transition("missing", "1.0", target_status="ACTIVE",
                            actor_id="reviewer", reason="test")
    with pytest.raises(ValueError, match="actor_id"):
        registry.register(definition(), actor_id="")


def test_same_lifecycle_event_is_idempotent(registry):
    registry.register(definition(), actor_id="reviewer-1")
    registry.transition("regulation.pause", "1.0", target_status="ACTIVE",
                        actor_id="approver-1", reason="approved")
    repeated = registry.transition("regulation.pause", "1.0", target_status="SUSPENDED",
                                   actor_id="safety-1", reason="incident")
    assert repeated["lifecycle"] == "SUSPENDED"
    assert len(registry.history("regulation.pause", "1.0")) == 3
