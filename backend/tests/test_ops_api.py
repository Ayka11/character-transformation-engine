from uuid import uuid4

from fastapi.testclient import TestClient

from cte.api import app


def test_ops_api_requires_separate_operational_key(monkeypatch):
    monkeypatch.delenv("CTE_OPS_API_KEY", raising=False)
    client=TestClient(app)
    response=client.get("/ops/backup")
    assert response.status_code==503


def test_ops_backup_and_validate_are_protected(monkeypatch):
    monkeypatch.setenv("CTE_OPS_API_KEY","ops-secret")
    client=TestClient(app)
    denied=client.get("/ops/backup")
    assert denied.status_code==401

    backup=client.get("/ops/backup",headers={"X-CTE-Ops-Key":"ops-secret"})
    assert backup.status_code==200
    data=backup.json()
    assert data["backup_version"]=="1.0"
    assert data["manifest_hash"]

    validated=client.post(
        "/ops/backup/validate",
        headers={"X-CTE-Ops-Key":"ops-secret"},
        json=data,
    )
    assert validated.status_code==200
    assert validated.json()["valid"] is True


def test_ops_restore_dry_run_does_not_mutate_store(monkeypatch):
    monkeypatch.setenv("CTE_OPS_API_KEY","ops-secret")
    client=TestClient(app)
    backup=client.get("/ops/backup",headers={"X-CTE-Ops-Key":"ops-secret"}).json()
    response=client.post(
        "/ops/backup/restore",
        headers={"X-CTE-Ops-Key":"ops-secret"},
        json={"backup":backup,"dry_run":True},
    )
    assert response.status_code==200
    assert response.json()["dry_run"] is True


