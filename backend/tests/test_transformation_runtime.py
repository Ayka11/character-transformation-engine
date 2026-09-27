from cte.contracts.transformation import TransformationContract
from cte.persistence import SQLiteRuntimeStore
from cte.state_snapshot_store import StateSnapshotStore
from cte.transformation_runtime import TransformationExecutor

def test_runtime_persists_before_after_and_validates_change():
    ss=StateSnapshotStore(SQLiteRuntimeStore(":memory:"))
    runtime=TransformationExecutor(ss)
    result=runtime.execute(
        "e1","c1",10,{"tempo":5},
        TransformationContract("t1","1",expected_changes={"tempo":6}),
        lambda state: {**state,"tempo":6},
    )
    assert result.result.status=="VALIDATED"
    assert result.result.certificate_eligible
    assert len(ss.get_lineage("c1"))==2

def test_runtime_rejects_successful_noop_as_no_state_change():
    ss=StateSnapshotStore(SQLiteRuntimeStore(":memory:"))
    runtime=TransformationExecutor(ss)
    result=runtime.execute(
        "e2","c1",20,{"tempo":5},
        TransformationContract("t1","1",expected_changes={"tempo":6}),
        lambda state: state,
    )
    assert result.result.status=="FAILED"
    assert result.result.failure_code=="NO_STATE_CHANGE"
    assert not result.result.certificate_eligible
    assert result.after_snapshot_id is not None

def test_certificate_exists_only_for_validated_transition():
    ss=StateSnapshotStore(SQLiteRuntimeStore(":memory:"))
    runtime=TransformationExecutor(ss)
    ok=runtime.execute("e3","c1",30,{"tempo":5},
        TransformationContract("t1","1",expected_changes={"tempo":6}),
        lambda state:{**state,"tempo":6})
    assert ok.certificate is not None
    assert ok.certificate.execution_id=="e3"
    assert ok.certificate.before_hash != ok.certificate.after_hash

def test_intervention_exception_is_auditable_failure_without_certificate():
    ss=StateSnapshotStore(SQLiteRuntimeStore(":memory:"))
    runtime=TransformationExecutor(ss)
    out=runtime.execute("e4","c1",40,{"tempo":5},
        TransformationContract("t1","1",expected_changes={"tempo":6}),
        lambda state: (_ for _ in ()).throw(RuntimeError("boom")))
    assert out.result.status=="FAILED"
    assert out.result.failure_code=="INTERVENTION_FAILED"
    assert out.after_snapshot_id is None
    assert out.certificate is None
    assert out.before_snapshot_id=="e4:before:40"

def test_repeated_identical_request_is_idempotent():
    db=SQLiteRuntimeStore(":memory:")
    ss=StateSnapshotStore(db)
    ledger=__import__("cte.transformation_ledger",fromlist=["TransformationLedger"]).TransformationLedger(db)
    calls={"n":0}
    def intervention(state):
        calls["n"]+=1
        return {**state,"tempo":6}
    runtime=TransformationExecutor(ss,ledger)
    contract=TransformationContract("t1","1",expected_changes={"tempo":6})
    first=runtime.execute("idem","c1",1,{"tempo":5},contract,intervention)
    second=runtime.execute("idem","c1",1,{"tempo":5},contract,intervention)
    assert first.certificate.certificate_id==second.certificate.certificate_id
    assert calls["n"]==1
    assert len(ledger.list())==1
    assert ledger.list()[0].request_hash
