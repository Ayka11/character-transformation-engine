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


def test_concurrent_lifecycle_transitions_use_compare_and_append(registry, monkeypatch):
    import threading

    registry.register(definition(protocol_id="regulation.race"), actor_id="author")
    barrier = threading.Barrier(2)
    original = registry._current_status

    def synchronized_status(protocol_id, version):
        status = original(protocol_id, version)
        if status == "DRAFT":
            barrier.wait(timeout=5)
        return status

    monkeypatch.setattr(registry, "_current_status", synchronized_status)
    outcomes = []

    def transition(target, actor):
        try:
            outcomes.append(("ok", registry.transition(
                "regulation.race", "1.0", target_status=target,
                actor_id=actor, reason="concurrency regression test",
            )["lifecycle"]))
        except ValueError as exc:
            outcomes.append(("conflict", str(exc)))

    threads = [
        threading.Thread(target=transition, args=("ACTIVE", "approver-a")),
        threading.Thread(target=transition, args=("RETIRED", "approver-b")),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert all(not thread.is_alive() for thread in threads)
    assert sum(kind == "ok" for kind, _ in outcomes) == 1
    assert sum(kind == "conflict" for kind, _ in outcomes) == 1
    assert any(message == "concurrent lifecycle transition conflict"
               for kind, message in outcomes if kind == "conflict")
    history = registry.history("regulation.race", "1.0")
    assert len(history) == 2
    assert history[-1]["payload"]["status"] in {"ACTIVE", "RETIRED"}


def test_integrity_audit_accepts_untampered_definition_and_history(registry):
    registry.register(definition(protocol_id="regulation.audit"), actor_id="author")
    registry.transition("regulation.audit", "1.0", target_status="ACTIVE",
                        actor_id="approver", reason="review complete")
    result = registry.verify_integrity("regulation.audit", "1.0")
    assert result["valid"] is True
    assert result["definition_hash_valid"] is True
    assert result["history_valid"] is True
    assert result["event_count"] == 2
    assert result["current_status"] == "ACTIVE"
    assert result["violations"] == []


def test_integrity_audit_detects_definition_hash_tampering(registry):
    registered = registry.register(definition(protocol_id="regulation.tampered"), actor_id="author")
    with registry.store._connect() as conn:
        conn.execute(
            "UPDATE runtime_snapshots SET payload_hash=? WHERE namespace=? AND key=?",
            ("forged-hash", "protocol.registry.definition", "regulation.tampered@1.0"),
        )
        conn.commit()
    result = registry.verify_integrity("regulation.tampered", "1.0")
    assert result["valid"] is False
    assert result["definition_hash_valid"] is False
    assert "definition_hash_mismatch" in result["violations"]


def test_integrity_audit_detects_lifecycle_event_hash_tampering(registry):
    registry.register(definition(protocol_id="regulation.event-tampered"), actor_id="author")
    event = registry.history("regulation.event-tampered", "1.0")[0]
    with registry.store._connect() as conn:
        conn.execute(
            "UPDATE runtime_events SET output_hash=? WHERE event_id=?",
            ("forged-hash", event["event_id"]),
        )
        conn.commit()
    result = registry.verify_integrity("regulation.event-tampered", "1.0")
    assert result["valid"] is False
    assert result["history_valid"] is False
    assert "event[0]:output_hash_mismatch" in result["violations"]
