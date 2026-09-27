from cte.contracts.transformation import TransformationContract
from cte.persistence import SQLiteRuntimeStore
from cte.state_snapshot_store import StateSnapshotStore
from cte.transformation_ledger import TransformationLedger
from cte.transformation_runtime import TransformationExecutor
from cte.transformation_integrity import TransformationIntegrityVerifier

def test_integrity_verifier_passes_validated_ledger():
    db=SQLiteRuntimeStore(":memory:")
    ss=StateSnapshotStore(db); ledger=TransformationLedger(db)
    out=TransformationExecutor(ss,ledger).execute("iv1","c",1,{"tempo":5},
        TransformationContract("t","1",expected_changes={"tempo":6}),lambda s:{**s,"tempo":6})
    finding=TransformationIntegrityVerifier(ss,ledger).verify(ledger.list()[0].ledger_id)
    assert finding.status=="PASS"
    assert out.certificate is not None

def test_integrity_verifier_detects_missing_after_snapshot():
    db=SQLiteRuntimeStore(":memory:")
    ledger=TransformationLedger(db); ss=StateSnapshotStore(db)
    TransformationExecutor(ss,ledger).execute("iv2","c",1,{"tempo":5},
        TransformationContract("t","1",expected_changes={"tempo":6}),lambda s:{**s,"tempo":6})
    entry=ledger.list()[0]
    # Simulate a damaged store and commit the fixture corruption.
    with db._connect() as conn:
        conn.execute(
            "DELETE FROM runtime_snapshots WHERE namespace='state.snapshot' AND key=?",
            (entry.after_snapshot_id,),
        )
        conn.commit()
    finding=TransformationIntegrityVerifier(ss,ledger).verify(entry.ledger_id)
    assert "AFTER_SNAPSHOT_MISSING" in finding.issues
