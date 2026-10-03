"""Runtime executor for validated state transitions."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Any
from .contracts.state import StateSnapshot, StateDiffEngine
from .contracts.transformation import TransformationContract, TransformationResult, TransformationCertificate, validate_transition
from .contracts.errors import CTEErrorCode
from .state_snapshot_store import StateSnapshotStore
from .transformation_ledger import TransformationLedger, TransformationLedgerEntry
from .transformation_recovery import TransformationJournal, JournalAttempt
from .transformation_concurrency import TransformationConcurrencyGuard
from .persistence import SQLiteRuntimeStore
from .provenance import content_hash

@dataclass(frozen=True)
class TransformationExecution:
    execution_id: str
    before_snapshot_id: str
    after_snapshot_id: str | None
    result: TransformationResult
    certificate: TransformationCertificate | None = None

class TransformationExecutor:
    def __init__(self, snapshot_store: StateSnapshotStore | None = None, ledger: TransformationLedger | None = None,
                 journal: TransformationJournal | None = None, concurrency_guard: TransformationConcurrencyGuard | None = None):
        if snapshot_store is None and ledger is None and journal is None and concurrency_guard is None:
            isolated_store=SQLiteRuntimeStore(":memory:")
            self.snapshots=StateSnapshotStore(isolated_store)
            self.ledger=TransformationLedger(isolated_store)
            self.journal=TransformationJournal(isolated_store)
            self.concurrency=TransformationConcurrencyGuard(isolated_store)
        else:
            self.snapshots=snapshot_store or StateSnapshotStore()
            self.ledger=ledger or TransformationLedger(self.snapshots.store)
            self.journal=journal or TransformationJournal(self.snapshots.store)
            self.concurrency=concurrency_guard or TransformationConcurrencyGuard(self.snapshots.store)

    def execute(self, execution_id: str, character_id: str, sequence: int,
                state: dict[str, Any], contract: TransformationContract,
                intervention: Callable[[dict[str, Any]], dict[str, Any]],
                *, parent_snapshot_id: str | None = None) -> TransformationExecution:
        request_hash=content_hash({
            "execution_id":execution_id,"character_id":character_id,"sequence":sequence,
            "state":state,"contract_id":contract.contract_id,"contract_version":contract.version,
            "parent_snapshot_id":parent_snapshot_id})
        existing=self.ledger.find_by_request_hash(request_hash)
        if existing is not None:
            return self._replay_existing(existing)
        try:
            self.concurrency.acquire(character_id,sequence,parent_snapshot_id,request_hash)
        except Exception as exc:
            code=getattr(exc,"code","VERSION_CONFLICT")
            details=getattr(exc,"details",{"error":str(exc)})
            return TransformationExecution(execution_id,"",None,
                TransformationResult.failed(code,details,status="FAILED",before_snapshot_id=""))
        before=StateSnapshot.capture(f"{execution_id}:before:{sequence}",character_id,sequence,state,
                                     parent_snapshot_id=parent_snapshot_id,source_execution_id=execution_id)
        self.snapshots.save(before)
        attempt=JournalAttempt(request_hash,execution_id,character_id,sequence,request_hash,
                               contract.contract_id,contract.version,"PREPARED",before.snapshot_id)
        self.journal.record(attempt,"PREPARED")
        started=JournalAttempt(**{**attempt.__dict__,"status":"INTERVENTION_STARTED"})
        self.journal.record(started,"INTERVENTION_STARTED")
        try:
            after_state=intervention(dict(state))
        except Exception as exc:
            result=TransformationResult.failed(
                "INTERVENTION_FAILED",{"error":str(exc),"rollback_status":"NOT_REQUIRED"},
                before_snapshot_id=before.snapshot_id)
            execution=TransformationExecution(execution_id,before.snapshot_id,None,result)
            # Durable commit order is ledger first, terminal journal second.
            # A crash before the ledger commit leaves the attempt non-terminal,
            # allowing recovery to retry the durable bookkeeping.
            self.ledger.append(TransformationLedgerEntry.from_execution(
                execution,character_id,contract,request_hash=request_hash))
            failed=JournalAttempt(**{**started.__dict__,"status":"FAILED","error":str(exc)})
            self.journal.record(failed,"FAILED")
            return execution

        after=StateSnapshot.capture(f"{execution_id}:after:{sequence}",character_id,sequence+1,after_state,
                                    parent_snapshot_id=before.snapshot_id,source_execution_id=execution_id)
        self.snapshots.save(after)
        captured=JournalAttempt(**{**started.__dict__,"status":"AFTER_CAPTURED","after_snapshot_id":after.snapshot_id})
        self.journal.record(captured,"AFTER_CAPTURED",after_hash=after.state_hash)
        diff=StateDiffEngine.compare(before,after,expected=contract.expected_changes,
                                     allowed=set(contract.allowed_changes),forbidden=set(contract.forbidden_changes))
        result=validate_transition(contract,diff,before_snapshot_id=before.snapshot_id,after_snapshot_id=after.snapshot_id,before_state=before.state,after_state=after.state)

        if result.status=="FAILED" and diff.state_changed:
            # Forbidden changes remain hard FAILED; unplanned changes without
            # rollback are retained as PARTIAL state for recovery/audit.
            if diff.forbidden:
                pass
            elif contract.rollback is not None:
                try:
                    restored_state=contract.rollback(dict(after_state),dict(state))
                    restored=StateSnapshot.capture(f"{execution_id}:rollback:{sequence}",character_id,sequence+2,
                                                    restored_state,parent_snapshot_id=after.snapshot_id,source_execution_id=execution_id)
                    self.snapshots.save(restored)
                    restored_diff=StateDiffEngine.compare(before,restored)
                    if restored_diff.state_changed:
                        result=TransformationResult.failed("ROLLBACK_FAILED",
                            {"rollback_status":"FAILED_TO_RESTORE","rollback_snapshot_id":restored.snapshot_id},
                            before_snapshot_id=before.snapshot_id,after_snapshot_id=after.snapshot_id,status="ROLLBACK_FAILED",
                            before_hash=before.state_hash,after_hash=after.state_hash,changed_fields=tuple(sorted(diff.changed)))
                    else:
                        result=TransformationResult.failed(result.failure_code or "VALIDATION_FAILED",
                            {"rollback_status":"ROLLED_BACK","rollback_snapshot_id":restored.snapshot_id},
                            before_snapshot_id=before.snapshot_id,after_snapshot_id=after.snapshot_id,status="ROLLED_BACK",
                            before_hash=before.state_hash,after_hash=after.state_hash,changed_fields=tuple(sorted(diff.changed)))
                except Exception as rollback_exc:
                    result=TransformationResult.failed("ROLLBACK_FAILED",
                        {"rollback_status":"FAILED_TO_EXECUTE","error":str(rollback_exc)},
                        before_snapshot_id=before.snapshot_id,after_snapshot_id=after.snapshot_id,status="ROLLBACK_FAILED",
                        before_hash=before.state_hash,after_hash=after.state_hash,changed_fields=tuple(sorted(diff.changed)))
            else:
                result=TransformationResult.failed(result.failure_code or "VALIDATION_FAILED",
                    {"rollback_status":"NOT_CONFIGURED","partial_state":True},
                    before_snapshot_id=before.snapshot_id,after_snapshot_id=after.snapshot_id,status="PARTIAL",
                    before_hash=before.state_hash,after_hash=after.state_hash,changed_fields=tuple(sorted(diff.changed)))

        certificate=None
        if result.status=="VALIDATED" and result.certificate_eligible:
            certificate=TransformationCertificate.issue(execution_id,contract,result)
        execution=TransformationExecution(execution_id,before.snapshot_id,after.snapshot_id,result,certificate)
        self.ledger.append(TransformationLedgerEntry.from_execution(execution,character_id,contract,request_hash=request_hash))
        terminal=JournalAttempt(**{**captured.__dict__,"status":result.status})
        self.journal.record(terminal,result.status,failure_code=result.failure_code)
        return execution

    def _replay_existing(self,entry):
        changed_fields=()
        if entry.before_snapshot_id and entry.after_snapshot_id:
            before=self.snapshots.get(entry.before_snapshot_id)
            after=self.snapshots.get(entry.after_snapshot_id)
            if before is not None and after is not None:
                changed_fields=tuple(sorted(StateDiffEngine.compare(before,after).changed))
        result=TransformationResult(entry.status,entry.failure_code,entry.before_snapshot_id,
            entry.after_snapshot_id or "",entry.before_hash,entry.after_hash,changed_fields,bool(entry.certificate_id),
            {"idempotent_replay":True})
        certificate=None
        if entry.certificate_id:
            certificate=TransformationCertificate(entry.certificate_id,entry.execution_id,entry.contract_id,
                entry.contract_version,entry.before_snapshot_id,entry.after_snapshot_id or "",
                entry.before_hash,entry.after_hash,changed_fields,entry.certificate_id)
        return TransformationExecution(entry.execution_id,entry.before_snapshot_id,entry.after_snapshot_id,result,certificate)
