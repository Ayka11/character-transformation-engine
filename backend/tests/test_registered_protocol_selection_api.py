import pytest
from fastapi.testclient import TestClient

from cte.api import app, RUNTIME_STORE
from cte.protocol_registry import ProtocolRegistry

client = TestClient(app)


def definition(**overrides):
    base = {
        "protocol_id": "api.registry.pause",
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


def body(protocol_id="api.registry.pause", version="1.0", **overrides):
    payload = {
        "protocol_refs": [{"protocol_id": protocol_id, "version": version}],
        "profile": {"P3.pause_capacity": 6},
        "state": {"sprint_status": "ACTIVE"},
        "goals": ["self_regulation"],
        "contexts": ["work"],
        "capacity": 6,
        "safety_status": "PASS",
    }
    payload.update(overrides)
    return payload


def test_registered_selection_uses_active_immutable_definition_and_hash():
    registry = ProtocolRegistry(RUNTIME_STORE)
    registry.register(definition(), actor_id="test-author")
    registry.record_review("api.registry.pause", "1.0", reviewer_id="test-reviewer", outcome="APPROVED", reason="independent test review")
    registry.transition("api.registry.pause", "1.0", target_status="ACTIVE",
                        actor_id="test-approver", reason="test activation")

    response = client.post("/protocols/v1/select-registered-candidates", json=body())
    assert response.status_code == 200
    payload = response.json()
    candidate = payload["candidates"][0]
    assert payload["registry_backed"] is True
    assert payload["ranked"] is False
    assert candidate["status"] == "ELIGIBLE_FOR_REVIEW"
    assert candidate["definition_hash"]
    # The immutable snapshot remains DRAFT; selection uses the separately governed ACTIVE state.
    stored = registry.get("api.registry.pause", "1.0")
    assert stored["protocol"]["status"] == "DRAFT"
    assert stored["lifecycle"] == "ACTIVE"
    assert candidate["registry_source"] == "immutable_protocol_registry"
    assert candidate["selection_authorized"] is False


def test_registered_selection_rejects_unknown_version():
    response = client.post(
        "/protocols/v1/select-registered-candidates",
        json=body(protocol_id="api.registry.missing"),
    )
    assert response.status_code == 404


def test_registered_selection_rejects_duplicate_refs():
    payload = body()
    payload["protocol_refs"] = payload["protocol_refs"] * 2
    response = client.post("/protocols/v1/select-registered-candidates", json=payload)
    assert response.status_code == 422


def test_registered_selection_keeps_unknown_safety_conditional():
    registry = ProtocolRegistry(RUNTIME_STORE)
    registry.register(definition(protocol_id="api.registry.unknown-safety"), actor_id="test-author")
    registry.record_review("api.registry.unknown-safety", "1.0", reviewer_id="test-reviewer", outcome="APPROVED", reason="independent test review")
    registry.transition("api.registry.unknown-safety", "1.0", target_status="ACTIVE",
                        actor_id="test-approver", reason="test activation")
    response = client.post(
        "/protocols/v1/select-registered-candidates",
        json=body(protocol_id="api.registry.unknown-safety", safety_status="UNKNOWN"),
    )
    assert response.status_code == 200
    assert response.json()["candidates"][0]["status"] == "CONDITIONAL"
    assert response.json()["candidates"][0]["selection_authorized"] is False


@pytest.mark.parametrize("lifecycle", ["DRAFT", "SUSPENDED", "RETIRED"])
def test_non_active_registry_lifecycle_never_becomes_review_eligible(lifecycle):
    protocol_id = f"api.registry.lifecycle-{lifecycle.lower()}"
    registry = ProtocolRegistry(RUNTIME_STORE)
    registry.register(definition(protocol_id=protocol_id), actor_id="test-author")

    if lifecycle != "DRAFT":
        registry.record_review(protocol_id, "1.0", reviewer_id="test-reviewer", outcome="APPROVED", reason="independent test review")
        registry.transition(protocol_id, "1.0", target_status="ACTIVE",
                            actor_id="test-approver", reason="test activation")
        if lifecycle in {"SUSPENDED", "RETIRED"}:
            registry.transition(protocol_id, "1.0", target_status=lifecycle,
                                actor_id="test-approver", reason="test lifecycle guard")

    response = client.post(
        "/protocols/v1/select-registered-candidates",
        json=body(protocol_id=protocol_id),
    )
    assert response.status_code == 200
    candidate = response.json()["candidates"][0]
    assert candidate["status"] == "INELIGIBLE"
    assert f"registry_status:{lifecycle}" in candidate["reasons"]
    assert candidate["selection_authorized"] is False
