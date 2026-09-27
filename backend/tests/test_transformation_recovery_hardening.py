from cte.persistence import SQLiteRuntimeStore
from cte.state_snapshot_store import StateSnapshotStore
from cte.transformation_integrity import TransformationIntegrityVerifier
from cte.transformation_ledger import TransformationLedger, TransformationLedgerEntry
from cte.transformation_recovery import TransformationJournal, TransformationRecoveryService, JournalAttempt
from cte.contracts.transformation import TransformationContract

def test_integrity_detects_forged_ledger_payload_hash():
    db=SQLiteRuntimeStore(":memory:")
    snapshots=StateSnapshotStore(db)
    ledger=TransformationLedger(db)
    entry=TransformationLedgerEntry(
        "ledger-1","exec-1","c1","protocol-1","1","FAILED","INTERVENTION_FAILED",
        "before","", "bh","",None,"forged","request-1")
    ledger.append(entry)
    finding=TransformationIntegrityVerifier(snapshots,ledger).verify("ledger-1")
    assert finding.status=="FAIL"
    assert "LEDGER_PAYLOAD_HASH_MISMATCH" in finding.issues
    assert "LEDGER_ID_HASH_MISMATCH" in finding.issues

def test_recovery_closes_intervention_started_without_rerunning_intervention():
    db=SQLiteRuntimeStore(":memory:")
    snapshots=StateSnapshotStore(db)
    ledger=TransformationLedger(db)
    journal=TransformationJournal(db)
    attempt=JournalAttempt("attempt-1","exec-1","c1",1,"request-1","protocol-1","1","INTERVENTION_STARTED","before")
    journal.record(attempt,"INTERVENTION_STARTED")
    recovery=TransformationRecoveryService(snapshots,ledger,journal)
    recovered=recovery.recover("attempt-1",TransformationContract("protocol-1","1"))
    assert recovered.status=="RECOVERED"
    assert ledger.list()[0].status=="FAILED"
    assert ledger.list()[0].failure_code=="INTERVENTION_OUTCOME_UNKNOWN"
    assert ledger.list()[0].after_snapshot_id is None
