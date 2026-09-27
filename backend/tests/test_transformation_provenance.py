from cte.contracts.transformation import TransformationContract
from cte.persistence import SQLiteRuntimeStore
from cte.state_snapshot_store import StateSnapshotStore
from cte.transformation_ledger import TransformationLedger
from cte.transformation_provenance import TransformationProvenanceBinder
from cte.transformation_runtime import TransformationExecutor


def test_transformation_provenance_binds_validated_execution():
    db=SQLiteRuntimeStore(":memory:")
    snapshots=StateSnapshotStore(db)
    ledger=TransformationLedger(db)
    executor=TransformationExecutor(snapshots,ledger)
    execution=executor.execute(
        "prov-1","c1",1,{"tempo":5},
        TransformationContract("protocol-1","1",expected_changes={"tempo":6}),
        lambda state: {"tempo":6},
    )
    bound=TransformationProvenanceBinder(db).bind_execution("prov-1")
    assert execution.result.status=="VALIDATED"
    assert bound["validated"] is True
    assert bound["status"]=="VALIDATED"
    assert bound["ledger_id"]
    assert bound["certificate_id"]
    assert bound["integrity_status"]=="PASS"
    assert bound["before_snapshot_id"]
    assert bound["after_snapshot_id"]


def test_transformation_provenance_does_not_promote_missing_execution():
    db=SQLiteRuntimeStore(":memory:")
    bound=TransformationProvenanceBinder(db).bind_execution("missing-execution")
    assert bound["validated"] is False
    assert bound["status"]=="MISSING"
    assert "TRANSFORMATION_LEDGER_ENTRY_MISSING" in bound["issues"]
