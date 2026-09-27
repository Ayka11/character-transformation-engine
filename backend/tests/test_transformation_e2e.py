"""Final end-to-end transformation integrity path."""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cte.contracts.transformation import TransformationContract
from cte.persistence import SQLiteRuntimeStore
from cte.state_snapshot_store import StateSnapshotStore
from cte.transformation_api import install_transformation_api
from cte.transformation_integrity import TransformationIntegrityVerifier
from cte.transformation_ledger import TransformationLedger
from cte.transformation_runtime import TransformationExecutor

def test_full_transformation_cycle_is_durable_and_inspectable():
    db=SQLiteRuntimeStore(":memory:")
    snapshots=StateSnapshotStore(db)
    ledger=TransformationLedger(db)
    executor=TransformationExecutor(snapshots,ledger)

    out=executor.execute(
        "e2e-1","character-1",1,{"tempo":5,"recovery":7},
        TransformationContract("protocol-1","1",expected_changes={"tempo":6}),
        lambda state:{**state,"tempo":6},
    )

    assert out.result.status=="VALIDATED"
    assert out.certificate is not None

    entry=ledger.list()[0]
    finding=TransformationIntegrityVerifier(snapshots,ledger).verify(entry.ledger_id)
    assert finding.status=="PASS"

    app=FastAPI()
    install_transformation_api(app,db)
    client=TestClient(app)

    lineage=client.get("/transformation/lineage/character-1")
    assert lineage.status_code==200
    assert lineage.json()["count"]==2
    assert all(item["verified"] for item in lineage.json()["integrity"])

    ledger_response=client.get(f"/transformation/ledger/{entry.ledger_id}")
    assert ledger_response.status_code==200
    assert ledger_response.json()["integrity"]["status"]=="PASS"

    integrity=client.get("/transformation/integrity")
    assert integrity.status_code==200
    assert integrity.json()["count"]==1
    assert integrity.json()["findings"][0]["status"]=="PASS"

    recovery=client.get("/transformation/recovery/scan")
    assert recovery.status_code==200
    assert recovery.json()["count"]==0
