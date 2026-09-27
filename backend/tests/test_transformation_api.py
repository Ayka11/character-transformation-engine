from fastapi import FastAPI
from fastapi.testclient import TestClient

from cte.persistence import SQLiteRuntimeStore
from cte.state_snapshot_store import StateSnapshotStore
from cte.contracts.state import StateSnapshot
from cte.transformation_api import install_transformation_api

def test_transformation_lineage_api_reports_verified_snapshots():
    app=FastAPI()
    db=SQLiteRuntimeStore(":memory:")
    install_transformation_api(app,db)
    snapshots=StateSnapshotStore(db)
    before=StateSnapshot.capture("b","c1",1,{"tempo":5},source_execution_id="e1")
    after=StateSnapshot.capture("a","c1",2,{"tempo":6},parent_snapshot_id="b",source_execution_id="e1")
    snapshots.save_pair_atomic(before,after)
    client=TestClient(app)
    response=client.get("/transformation/lineage/c1")
    assert response.status_code == 200
    payload=response.json()
    assert payload["count"] == 2
    assert all(item["verified"] for item in payload["integrity"])

def test_transformation_recovery_scan_api_is_empty_for_terminal_journal():
    app=FastAPI()
    db=SQLiteRuntimeStore(":memory:")
    install_transformation_api(app,db)
    client=TestClient(app)
    response=client.get("/transformation/recovery/scan")
    assert response.status_code == 200
    assert response.json()["count"] == 0
