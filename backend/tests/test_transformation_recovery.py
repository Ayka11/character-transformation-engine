from cte.contracts.state import StateSnapshot
from cte.contracts.transformation import TransformationContract
from cte.persistence import SQLiteRuntimeStore
from cte.state_snapshot_store import StateSnapshotStore
from cte.transformation_ledger import TransformationLedger
from cte.transformation_recovery import TransformationJournal, TransformationRecoveryService, JournalAttempt
from cte.provenance import content_hash

def test_crash_journal_survives_new_store_instance(tmp_path):
    path = str(tmp_path / "runtime.sqlite3")
    db1 = SQLiteRuntimeStore(path)
    journal1 = TransformationJournal(db1)
    attempt = JournalAttempt(
        "a1","exec1","c1",1,"req1","t","1","AFTER_CAPTURED","before","after")
    journal1.record(attempt, "AFTER_CAPTURED")
    db2 = SQLiteRuntimeStore(path)
    recovered = TransformationJournal(db2).attempts()
    assert recovered[0].status == "AFTER_CAPTURED"
    assert recovered[0].after_snapshot_id == "after"

def test_recovery_closes_orphan_without_rerunning_intervention():
    db = SQLiteRuntimeStore(":memory:")
    snapshots = StateSnapshotStore(db)
    ledger = TransformationLedger(db)
    journal = TransformationJournal(db)
    before = StateSnapshot.capture("before","c1",1,{"tempo":5},source_execution_id="exec1")
    after = StateSnapshot.capture("after","c1",2,{"tempo":6},parent_snapshot_id="before",source_execution_id="exec1")
    snapshots.save_pair_atomic(before, after)
    request_hash = content_hash({
        "execution_id":"exec1","character_id":"c1","sequence":1,
        "state":{"tempo":5},"contract_id":"t","contract_version":"1",
        "parent_snapshot_id":None
    })
    attempt = JournalAttempt(
        request_hash, "exec1","c1",1,request_hash,"t","1",
        "AFTER_CAPTURED","before","after"
    )
    journal.record(attempt, "AFTER_CAPTURED", after_hash=after.state_hash)
    service = TransformationRecoveryService(snapshots, ledger, journal)
    assert len(service.scan()) == 1
    contract = TransformationContract("t","1",expected_changes={"tempo":6})
    recovered = service.recover(request_hash, contract)
    assert recovered.status == "RECOVERED"
    assert ledger.find_by_request_hash(request_hash).status == "VALIDATED"
    assert len(service.scan()) == 0

def test_recovery_is_idempotent_when_ledger_already_exists():
    db = SQLiteRuntimeStore(":memory:")
    journal = TransformationJournal(db)
    attempt = JournalAttempt("a2","exec2","c2",1,"req2","t","1","AFTER_CAPTURED","before","after")
    journal.record(attempt, "AFTER_CAPTURED")
    from cte.transformation_recovery import TransformationRecoveryService
    service = TransformationRecoveryService(journal=journal)
    service.ledger.store.put_snapshot("transformation.ledger","existing",{
        "ledger_id":"existing","execution_id":"exec2","character_id":"c2",
        "contract_id":"t","contract_version":"1","status":"VALIDATED",
        "failure_code":None,"before_snapshot_id":"before","after_snapshot_id":"after",
        "before_hash":"b","after_hash":"a","certificate_id":"cert",
        "payload_hash":"p","request_hash":"req2"
    },"1.0")
    contract = TransformationContract("t","1")
    recovered = service.recover("a2", contract)
    assert recovered.status == "RECOVERED"
