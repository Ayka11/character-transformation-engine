from cte.contracts.errors import CTEErrorCode
from cte.contracts.state import StateSnapshot
from cte.persistence import SQLiteRuntimeStore
from cte.state_snapshot_store import StateSnapshotStore
from cte.transformation_concurrency import TransformationConcurrencyGuard

def test_non_initial_transformation_requires_parent():
    db=SQLiteRuntimeStore(":memory:")
    guard=TransformationConcurrencyGuard(db)
    try:
        guard.acquire("c1",2,None,"req")
    except Exception as exc:
        assert getattr(exc,"code",None)==CTEErrorCode.VERSION_CONFLICT.value
    else:
        raise AssertionError("expected parent requirement")

def test_parent_must_exist():
    db=SQLiteRuntimeStore(":memory:")
    guard=TransformationConcurrencyGuard(db)
    try:
        guard.acquire("c1",2,"missing","req")
    except Exception as exc:
        assert getattr(exc,"code",None)==CTEErrorCode.VERSION_CONFLICT.value
    else:
        raise AssertionError("expected missing parent conflict")

def test_parent_must_belong_to_same_character():
    db=SQLiteRuntimeStore(":memory:")
    ss=StateSnapshotStore(db)
    ss.save(StateSnapshot.capture("p","other",1,{"tempo":5},source_execution_id="x"))
    guard=TransformationConcurrencyGuard(db)
    try:
        guard.acquire("c1",2,"p","req")
    except Exception as exc:
        assert getattr(exc,"code",None)==CTEErrorCode.VERSION_CONFLICT.value
    else:
        raise AssertionError("expected cross-character parent conflict")
