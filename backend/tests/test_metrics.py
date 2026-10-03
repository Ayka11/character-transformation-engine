from fastapi.testclient import TestClient

from cte.api import app


def test_metrics_endpoint_is_prometheus_compatible(monkeypatch):
    monkeypatch.delenv("CTE_API_KEY", raising=False)
    monkeypatch.delenv("CTE_READ_API_KEY", raising=False)
    monkeypatch.delenv("CTE_WRITE_API_KEY", raising=False)
    client=TestClient(app)
    response=client.get("/metrics")
    assert response.status_code==200
    assert response.headers["content-type"].startswith("text/plain")
    assert "# TYPE cte_http_requests_total counter" in response.text
    assert 'method="GET",path="/metrics"' not in response.text


def test_metrics_is_protected_when_read_auth_is_enabled(monkeypatch):
    monkeypatch.setenv("CTE_READ_API_KEY","read-secret")
    monkeypatch.setenv("CTE_WRITE_API_KEY","write-secret")
    client=TestClient(app)
    denied=client.get("/metrics")
    assert denied.status_code==401
    allowed=client.get("/metrics",headers={"X-CTE-API-Key":"read-secret"})
    assert allowed.status_code==200
    assert "cte_http_responses_total" in allowed.text