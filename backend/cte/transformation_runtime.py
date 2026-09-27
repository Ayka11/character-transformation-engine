"""Runtime executor for validated state transitions."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Any
from .contracts.state import StateSnapshot
from .contracts.transformation import TransformationContract, TransformationResult, validate_transition
from .state_snapshot_store import StateSnapshotStore
from .provenance import content_hash

@dataclass(frozen=True)
class TransformationExecution:
    execution_id: str
    before_snapshot_id: str
    after_snapshot_id: str | None
    result: TransformationResult

class TransformationExecutor:
    def __init__(self, snapshot_store: StateSnapshotStore | None = None):
        self.snapshots = snapshot_store or StateSnapshotStore()

    def execute(self, execution_id: str, character_id: str, sequence: int,
                state: dict[str, Any], contract: TransformationContract,
                intervention: Callable[[dict[str, Any]], dict[str, Any]],
                *, parent_snapshot_id: str | None = None) -> TransformationExecution:
        before=StateSnapshot.capture(
            f"{execution_id}:before:{sequence}", character_id, sequence, state,
            parent_snapshot_id=parent_snapshot_id, source_execution_id=execution_id,
        )
        self.snapshots.save(before)
        try:
            after_state=intervention(dict(state))
        except Exception as exc:
            result=TransformationResult.failed("INTERVENTION_FAILED", {"error":str(exc)})
            return TransformationExecution(execution_id,before.snapshot_id,None,result)

        after=StateSnapshot.capture(
            f"{execution_id}:after:{sequence}", character_id, sequence+1, after_state,
            parent_snapshot_id=before.snapshot_id, source_execution_id=execution_id,
        )
        self.snapshots.save(after)
        from .contracts.state import StateDiffEngine
        diff=StateDiffEngine.compare(
            before, after, expected=contract.expected_changes,
            allowed=set(contract.allowed_changes), forbidden=set(contract.forbidden_changes),
        )
        result=validate_transition(
            contract, diff,
            before_snapshot_id=before.snapshot_id,
            after_snapshot_id=after.snapshot_id,
        )
        return TransformationExecution(execution_id,before.snapshot_id,after.snapshot_id,result)
