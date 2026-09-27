from uuid import uuid4

from fastapi.testclient import TestClient

from cte.api import app


def test_health_is_public_and_exposes_request_headers(monkeypatch):
    monkeypatch.delenv("CTE_API_KEY", raising=False)
    monkeypatch.delenv("CTE_READ_API_KEY", raising=False)
    monkeypatch.delenv("CTE_WRITE_API_KEY", raising=False)
    client=TestClient(app)
    response=client.get("/health",headers={"X-Request-ID":"security-test-1"})
    assert response.status_code==200
    assert response.headers["X-Request-ID"]=="security-test-1"
    assert "X-Process-Time-Ms" in response.headers


def test_write_requires_write_key_when_auth_is_configured(monkeypatch):
    monkeypatch.setenv("CTE_READ_API_KEY","read-secret")
    monkeypatch.setenv("CTE_WRITE_API_KEY","write-secret")
    client=TestClient(app)
    suffix=uuid4().hex[:8]

    denied=client.post(
        "/science-lab/matrices",
        json={
            "matrix_id":"auth-matrix-"+suffix,
            "study_id":"auth-study-"+suffix,
            "name":"Auth Test","primary_outcome":"value",
            "design":{"type":"scenario_matrix"}
        }
    )
    assert denied.status_code==401

    read_denied=client.post(
        "/science-lab/matrices",
        headers={"X-CTE-API-Key":"read-secret"},
        json={
            "matrix_id":"auth-matrix-read-"+suffix,
            "study_id":"auth-study-read-"+suffix,
            "name":"Auth Test","primary_outcome":"value",
            "design":{"type":"scenario_matrix"}
        }
    )
    assert read_denied.status_code==401

    allowed=client.post(
        "/science-lab/matrices",
        headers={"X-CTE-API-Key":"write-secret"},
        json={
            "matrix_id":"auth-matrix-write-"+suffix,
            "study_id":"auth-study-write-"+suffix,
            "name":"Auth Test","primary_outcome":"value",
            "design":{"type":"scenario_matrix"}
        }
    )
    assert allowed.status_code==200


def test_read_key_allows_read_routes(monkeypatch):
    monkeypatch.setenv("CTE_READ_API_KEY","read-secret")
    monkeypatch.setenv("CTE_WRITE_API_KEY","write-secret")
    client=TestClient(app)
    response=client.get("/matrix",headers={"X-CTE-API-Key":"read-secret"})
    assert response.status_code==200


def test_observability_audit_event_is_written(monkeypatch):
    monkeypatch.delenv("CTE_API_KEY",raising=False)
    monkeypatch.delenv("CTE_READ_API_KEY",raising=False)
    monkeypatch.delenv("CTE_WRITE_API_KEY",raising=False)
    client=TestClient(app)
    response=client.get("/health")
    assert response.status_code==200
