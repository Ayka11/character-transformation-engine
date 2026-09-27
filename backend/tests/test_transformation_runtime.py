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
