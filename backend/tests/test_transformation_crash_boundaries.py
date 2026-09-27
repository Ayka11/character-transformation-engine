import pytest

from cte.contracts.transformation import TransformationContract
from cte.persistence import SQLiteRuntimeStore
from cte.state_snapshot_store import StateSnapshotStore
from cte.transformation_ledger import TransformationLedger
from cte.transformation_recovery import TransformationJournal
from cte.transformation_runtime import TransformationExecutor

class FailingLedger(TransformationLedger):
    def append(self, entry):
        raise RuntimeError("simulated ledger commit crash")

def test_intervention_failure_is_not_terminal_until_ledger_commit():
    db=SQLiteRuntimeStore(":memory:")
    snapshots=StateSnapshotStore(db)
    ledger=FailingLedger(db)
    journal=TransformationJournal(db)
    executor=TransformationExecutor(snapshots,ledger,journal)
    with pytest.raises(RuntimeError, match="simulated ledger commit crash"):
        executor.execute(
            "crash-fail","c1",1,{"tempo":5},
            TransformationContract("t","1"),
            lambda state: (_ for _ in ()).throw(RuntimeError("intervention boom")),
        )
    attempts=journal.attempts()
    assert len(attempts)==1
    assert attempts[0].status=="INTERVENTION_STARTED"
    assert len(journal.events(attempts[0].attempt_id))==2

def test_successful_ledger_commit_precedes_terminal_journal():
    db=SQLiteRuntimeStore(":memory:")
    snapshots=StateSnapshotStore(db)
    ledger=TransformationLedger(db)
    journal=TransformationJournal(db)
    executor=TransformationExecutor(snapshots,ledger,journal)
    out=executor.execute(
        "ordered","c1",1,{"tempo":5},
        TransformationContract("t","1",expected_changes={"tempo":6}),
        lambda state:{"tempo":6},
    )
    assert out.result.status=="VALIDATED"
    entry=ledger.list()[0]
    assert entry.status=="VALIDATED"
    attempt=next(a for a in journal.attempts() if a.execution_id=="ordered")
    assert attempt.status=="VALIDATED"
