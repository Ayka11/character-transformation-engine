"""Adversarial invariants for the transformation runtime."""
import pytest

from cte.contracts.state import StateSnapshot
from cte.contracts.transformation import TransformationContract
from cte.persistence import SQLiteRuntimeStore
from cte.state_snapshot_store import StateSnapshotStore
from cte.transformation_ledger import TransformationLedger
from cte.transformation_runtime import TransformationExecutor
from cte.transformation_integrity import TransformationIntegrityVerifier
from cte.transformation_recovery import TransformationJournal, TransformationRecoveryService, JournalAttempt
from cte.provenance import content_hash

def _runtime():
    db=SQLiteRuntimeStore(":memory:")
    return db, StateSnapshotStore(db), TransformationLedger(db)

def test_no_certificate_can_exist_for_partial_or_rolled_back_result():
    db,ss,ledger=_runtime()
    executor=TransformationExecutor(ss,ledger)
    partial=executor.execute(
        "partial","c1",1,{"tempo":5},
        TransformationContract("t","1",expected_changes={"tempo":7}),
        lambda s:{**s,"tempo":6},
    )
    assert partial.result.status=="PARTIAL"
    assert partial.certificate is None
    entry=ledger.list()[0]
    assert entry.certificate_id is None
    assert TransformationIntegrityVerifier(ss,ledger).verify(entry.ledger_id).status=="PASS"

def test_forbidden_change_never_becomes_validated():
    db,ss,ledger=_runtime()
    executor=TransformationExecutor(ss,ledger)
    out=executor.execute(
        "forbidden","c1",1,{"tempo":5,"stress":2},
        TransformationContract("t","1",expected_changes={"tempo":6},forbidden_changes=("stress",)),
        lambda s:{**s,"tempo":6,"stress":3},
    )
    assert out.result.status=="FAILED"
    assert out.result.failure_code=="UNEXPECTED_CHANGE"
    assert out.certificate is None

def test_tampered_after_snapshot_is_detected():
    db,ss,ledger=_runtime()
    out=TransformationExecutor(ss,ledger).execute(
        "tamper","c1",1,{"tempo":5},
        TransformationContract("t","1",expected_changes={"tempo":6}),
        lambda s:{**s,"tempo":6},
    )
    entry=ledger.list()[0]
    with db._connect() as conn:
        conn.execute(
            "UPDATE runtime_snapshots SET payload_json=? WHERE namespace='state.snapshot' AND key=?",
            ('{"snapshot_id":"tampered","character_id":"c1","sequence":2,"state":{"tempo":999},"state_hash":"forged","lineage_hash":"forged","parent_snapshot_id":"x","source_execution_id":"tamper","schema_version":"1.0","canonicalization_version":"1.0"}',
             entry.after_snapshot_id),
        )
        conn.commit()
    finding=TransformationIntegrityVerifier(ss,ledger).verify(entry.ledger_id)
    assert finding.status=="FAIL"
    assert "AFTER_HASH_MISMATCH" in finding.issues

def test_recovery_never_reexecutes_intervention():
    db,ss,ledger=_runtime()
    journal=TransformationJournal(db)
    before=StateSnapshot.capture("before","c1",1,{"tempo":5},source_execution_id="e1")
    after=StateSnapshot.capture("after","c1",2,{"tempo":6},parent_snapshot_id="before",source_execution_id="e1")
    ss.save_pair_atomic(before,after)
    request_hash=content_hash({
        "execution_id":"e1","character_id":"c1","sequence":1,"state":{"tempo":5},
        "contract_id":"t","contract_version":"1","parent_snapshot_id":None,
    })
    journal.record(JournalAttempt(
        request_hash,"e1","c1",1,request_hash,"t","1","AFTER_CAPTURED","before","after"
    ),"AFTER_CAPTURED",after_hash=after.state_hash)
    service=TransformationRecoveryService(ss,ledger,journal)
    result=service.recover(request_hash,TransformationContract("t","1",expected_changes={"tempo":6}))
    assert result.status=="RECOVERED"
    assert ledger.find_by_request_hash(request_hash) is not None

def test_same_request_replay_does_not_create_second_ledger_entry():
    db,ss,ledger=_runtime()
    calls=[]
    contract=TransformationContract("t","1",expected_changes={"tempo":6})
    executor=TransformationExecutor(ss,ledger)
    first=executor.execute("e1","c1",1,{"tempo":5},contract,
                           lambda s:calls.append(1) or {"tempo":6})
    second=executor.execute("e1","c1",1,{"tempo":5},contract,
                            lambda s:calls.append(2) or {"tempo":6})
    assert first.result.status=="VALIDATED"
    assert second.result.details["idempotent_replay"] is True
    assert calls==[1]
    assert len(ledger.list())==1

def test_failed_execution_cannot_forge_validated_certificate():
    db,ss,ledger=_runtime()
    executor=TransformationExecutor(ss,ledger)
    out=executor.execute(
        "failed","c1",1,{"tempo":5},
        TransformationContract("t","1",expected_changes={"tempo":6}),
        lambda s: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    assert out.result.status=="FAILED"
    assert out.result.failure_code=="INTERVENTION_FAILED"
    assert out.certificate is None
    entry=ledger.list()[0]
    assert entry.certificate_id is None
