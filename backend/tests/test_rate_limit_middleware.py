from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from fastapi.testclient import TestClient

from cte.observability import SecurityObservabilityMiddleware


def test_middleware_enforces_configured_rate_limit(monkeypatch):
    monkeypatch.delenv("CTE_READ_API_KEY", raising=False)
    monkeypatch.delenv("CTE_WRITE_API_KEY", raising=False)
    monkeypatch.delenv("CTE_API_KEY", raising=False)
    monkeypatch.setenv("CTE_RATE_LIMIT_PER_MINUTE","2")

    app=FastAPI()
    app.add_middleware(SecurityObservabilityMiddleware, store=None)

    @app.get("/protected")
    def protected():
        return PlainTextResponse("ok")

    client=TestClient(app)
    assert client.get("/protected").status_code==200
    assert client.get("/protected").status_code==200
    limited=client.get("/protected")
    assert limited.status_code==429
    assert limited.headers.get("Retry-After")
