import threading

from cte.contracts.transformation import TransformationContract
from cte.persistence import SQLiteRuntimeStore
from cte.state_snapshot_store import StateSnapshotStore
from cte.transformation_concurrency import TransformationConcurrencyGuard
from cte.transformation_runtime import TransformationExecutor

def test_different_requests_same_character_sequence_conflict():
    db=SQLiteRuntimeStore(":memory:")
    guard=TransformationConcurrencyGuard(db)
    guard.acquire("c1",7,"parent-a","request-a")
    try:
        guard.acquire("c1",7,"parent-b","request-b")
    except Exception as exc:
        assert getattr(exc,"code",None) == "VERSION_CONFLICT"
    else:
        raise AssertionError("expected VERSION_CONFLICT")

def test_same_request_is_idempotent_at_concurrency_guard():
    db=SQLiteRuntimeStore(":memory:")
    guard=TransformationConcurrencyGuard(db)
    first=guard.acquire("c1",7,"parent-a","request-a")
    second=guard.acquire("c1",7,"parent-a","request-a")
    assert first == second

def test_runtime_does_not_invoke_intervention_after_version_conflict():
    db=SQLiteRuntimeStore(":memory:")
    executor=TransformationExecutor(
        snapshot_store=StateSnapshotStore(db),
    )
    contract=TransformationContract("t","1",expected_changes={"tempo":6})
    calls=[]
    first=executor.execute("e1","c1",1,{"tempo":5},contract,
                           lambda state: calls.append("first") or {"tempo":6})
    second=executor.execute("e2","c1",1,{"tempo":5},contract,
                            lambda state: calls.append("second") or {"tempo":6})
    assert first.result.status == "VALIDATED"
    assert second.result.failure_code == "VERSION_CONFLICT"
    assert "second" not in calls

def test_concurrent_different_requests_only_one_intervention_runs():
    db=SQLiteRuntimeStore(":memory:")
    executor=TransformationExecutor(snapshot_store=StateSnapshotStore(db))
    contract=TransformationContract("t","1",expected_changes={"tempo":6})
    calls=[]
    barrier=threading.Barrier(2)
    results=[]

    def run(execution_id):
        def intervention(state):
            calls.append(execution_id)
            barrier.wait()
            return {"tempo":6}
        results.append(executor.execute(execution_id,"c1",1,{"tempo":5},contract,intervention))

    a=threading.Thread(target=run,args=("e1",))
    b=threading.Thread(target=run,args=("e2",))
    a.start(); b.start(); a.join(); b.join()
    assert len(calls) == 1
    assert sum(r.result.failure_code == "VERSION_CONFLICT" for r in results) == 1
