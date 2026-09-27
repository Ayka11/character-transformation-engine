import json
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cte.contracts.state import StateSnapshot
from cte.contracts.transformation import TransformationContract
from cte.persistence import SQLiteRuntimeStore
from cte.state_snapshot_store import StateSnapshotStore
from cte.transformation_api import install_transformation_api
from cte.transformation_integrity import TransformationIntegrityVerifier
from cte.transformation_ledger import TransformationLedger
from cte.transformation_runtime import TransformationExecutor
from cte.transformation_api import install_transformation_api

def test_integrity_detects_lineage_hash_tampering():
    db=SQLiteRuntimeStore(":memory:")
    ss=StateSnapshotStore(db); ledger=TransformationLedger(db)
    TransformationExecutor(ss,ledger).execute(
        "audit1","c1",1,{"tempo":5},
        TransformationContract("t","1",expected_changes={"tempo":6}),
        lambda s:{"tempo":6},
    )
    entry=ledger.list()[0]
    with db._connect() as conn:
        forged_payload = '{"snapshot_id":"%s","character_id":"c1","sequence":2,"state":{"tempo":6},"state_hash":"%s","lineage_hash":"FORGED","parent_snapshot_id":"%s","source_execution_id":"audit1","schema_version":"1.0","canonicalization_version":"1.0"}' % (entry.after_snapshot_id, entry.after_hash, entry.before_snapshot_id)
        conn.execute(
            "UPDATE runtime_snapshots SET payload_json=? WHERE namespace='state.snapshot' AND key=?",
            (forged_payload, entry.after_snapshot_id),
        )
        conn.commit()
    finding=TransformationIntegrityVerifier(ss,ledger).verify(entry.ledger_id)
    assert finding.status=="FAIL"
    assert "AFTER_SNAPSHOT_INTEGRITY_FAILED" in finding.issues

def test_transformation_inspection_api_uses_404_for_missing_resources():
    db=SQLiteRuntimeStore(":memory:")
    app=FastAPI()
    install_transformation_api(app,db)
    client=TestClient(app)
    assert client.get("/transformation/snapshots/missing").status_code==404
    assert client.get("/transformation/ledger/missing").status_code==404
    assert client.get("/transformation/journal/missing").status_code==404

def test_runtime_store_immutable_event_rejects_payload_conflict():
    db=SQLiteRuntimeStore(":memory:")
    db.append_event("event-1","test","A",{"x":1})
    try:
        db.append_event("event-1","test","A",{"x":2})
    except ValueError as exc:
        assert "immutable event conflict" in str(exc)
    else:
        raise AssertionError("expected immutable event conflict")

def test_integrity_detects_forged_certificate_id():
    db=SQLiteRuntimeStore(":memory:")
    snapshots=StateSnapshotStore(db)
    ledger=TransformationLedger(db)
    TransformationExecutor(snapshots,ledger).execute(
        "cert-audit","c1",1,{"tempo":5},
        TransformationContract("t","1",expected_changes={"tempo":6}),
        lambda s:{"tempo":6},
    )
    entry=ledger.list()[0]
    with db._connect() as conn:
        conn.execute(
            "UPDATE runtime_snapshots SET payload_json=? WHERE namespace='transformation.ledger' AND key=?",
            (json.dumps({
                "ledger_id":entry.ledger_id,
                "execution_id":entry.execution_id,
                "character_id":entry.character_id,
                "contract_id":entry.contract_id,
                "contract_version":entry.contract_version,
                "status":entry.status,
                "failure_code":entry.failure_code,
                "before_snapshot_id":entry.before_snapshot_id,
                "after_snapshot_id":entry.after_snapshot_id,
                "before_hash":entry.before_hash,
                "after_hash":entry.after_hash,
                "certificate_id":"FORGED-CERTIFICATE",
                "payload_hash":entry.payload_hash,
                "request_hash":entry.request_hash,
            }), entry.ledger_id),
        )
        conn.commit()
    finding=TransformationIntegrityVerifier(snapshots,ledger).verify(entry.ledger_id)
    assert finding.status=="FAIL"
    assert "CERTIFICATE_HASH_MISMATCH" in finding.issues



def test_transformation_provenance_api_exposes_validated_binding():
    db=SQLiteRuntimeStore(":memory:")
    snapshots=StateSnapshotStore(db)
    ledger=TransformationLedger(db)
    TransformationExecutor(snapshots,ledger).execute(
        "api-prov-1","c1",1,{"tempo":5},
        TransformationContract("t","1",expected_changes={"tempo":6}),
        lambda s:{"tempo":6},
    )
    app=FastAPI()
    install_transformation_api(app,db)
    client=TestClient(app)
    response=client.get("/transformation/provenance/api-prov-1")
    assert response.status_code==200
    body=response.json()
    assert body["validated"] is True
    assert body["integrity_status"]=="PASS"
    assert body["certificate_id"]
