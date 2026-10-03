from cte.contracts.transformation import TransformationContract
from cte.persistence import SQLiteRuntimeStore
from cte.state_snapshot_store import StateSnapshotStore
from cte.transformation_ledger import TransformationLedger
from cte.transformation_runtime import TransformationExecutor

def test_ledger_records_validated_transformation():
    db=SQLiteRuntimeStore(":memory:")
    ss=StateSnapshotStore(db)
    ledger=TransformationLedger(db)
    out=TransformationExecutor(ss,ledger).execute(
        "e10","c1",1,{"tempo":5},
        TransformationContract("t1","1",expected_changes={"tempo":6}),
        lambda state:{**state,"tempo":6})
    entries=ledger.list()
    assert len(entries)==1
    assert entries[0].status=="VALIDATED"
    assert entries[0].certificate_id==out.certificate.certificate_id

def test_ledger_records_failed_intervention():
    db=SQLiteRuntimeStore(":memory:")
    ss=StateSnapshotStore(db)
    ledger=TransformationLedger(db)
    out=TransformationExecutor(ss,ledger).execute(
        "e11","c1",1,{"tempo":5},
        TransformationContract("t1","1",expected_changes={"tempo":6}),
        lambda state: (_ for _ in ()).throw(RuntimeError("boom")))
    entry=ledger.list()[0]
    assert out.result.status=="FAILED"
    assert entry.status=="FAILED"
    assert entry.failure_code=="INTERVENTION_FAILED"
    assert entry.certificate_id is None

def test_ledger_entry_is_immutable():
    db=SQLiteRuntimeStore(":memory:")
    ledger=TransformationLedger(db)
    from cte.transformation_ledger import TransformationLedgerEntry
    entry=TransformationLedgerEntry("l1","e","c","t","1","FAILED","X","b",None,"bh","",None,"h")
    ledger.append(entry)
    try:
        ledger.store.put_snapshot("transformation.ledger","l1",{**ledger.store.get_snapshot("transformation.ledger","l1").payload,"status":"VALIDATED"},"1.0")
    except ValueError as exc:
        assert "immutable snapshot conflict" in str(exc)
    else:
        assert False
