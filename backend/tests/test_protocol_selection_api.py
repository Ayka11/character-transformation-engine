from fastapi.testclient import TestClient

from cte.api import app

client = TestClient(app)


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


def request_body(**overrides):
    body = {
        "protocols": [protocol()],
        "profile": {"P3.pause_capacity": 6},
        "state": {"sprint_status": "ACTIVE"},
        "goals": ["self_regulation"],
        "contexts": ["work"],
        "capacity": 6,
        "safety_status": "PASS",
    }
    body.update(overrides)
    return body


def test_protocol_candidate_api_returns_review_only_candidate():
    response = client.post("/protocols/v1/select-candidates", json=request_body())
    assert response.status_code == 200
    payload = response.json()
    assert payload["scientific_status"] == "IMPLEMENTATION_BASELINE"
    assert payload["ranked"] is False
    assert payload["authoritative_scalar"] is False
    candidate = payload["candidates"][0]
    assert candidate["status"] == "ELIGIBLE_FOR_REVIEW"
    assert candidate["selection_authorized"] is False
    assert candidate["requires_human_review"] is True


def test_protocol_candidate_api_fails_closed_on_unknown_safety():
    response = client.post("/protocols/v1/select-candidates", json=request_body(safety_status="UNKNOWN"))
    assert response.status_code == 200
    assert response.json()["candidates"][0]["status"] == "CONDITIONAL"


def test_protocol_candidate_api_excludes_candidates_on_safety_block():
    response = client.post("/protocols/v1/select-candidates", json=request_body(safety_status="BLOCK"))
    assert response.status_code == 200
    assert response.json()["candidates"][0]["status"] == "INELIGIBLE"


def test_protocol_candidate_api_keeps_missing_measurements_unknown():
    response = client.post("/protocols/v1/select-candidates", json=request_body(profile={}))
    assert response.status_code == 200
    candidate = response.json()["candidates"][0]
    assert candidate["status"] == "INSUFFICIENT_DATA"
    assert any(reason.startswith("missing_measurements:") for reason in candidate["reasons"])


def test_protocol_candidate_api_rejects_invalid_safety_status():
    response = client.post("/protocols/v1/select-candidates", json=request_body(safety_status="MAYBE"))
    assert response.status_code == 422


def test_protocol_candidate_api_rejects_invalid_registry_entry():
    response = client.post("/protocols/v1/select-candidates", json=request_body(protocols=[{"protocol_id": "x"}]))
    assert response.status_code == 422
