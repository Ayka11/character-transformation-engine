"""Durable crash journal and recovery scanner for transformation execution."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from types import SimpleNamespace
from .persistence import build_runtime_store
from .provenance import content_hash
from .contracts.state import StateDiffEngine
from .contracts.transformation import validate_transition, TransformationCertificate, TransformationResult
from .state_snapshot_store import StateSnapshotStore
from .transformation_ledger import TransformationLedger, TransformationLedgerEntry

NAMESPACE = "transformation.journal"
TERMINAL = {"VALIDATED", "FAILED", "PARTIAL", "ROLLED_BACK", "ROLLBACK_FAILED", "RECOVERED"}
STATUS_ORDER = {"PREPARED": 10, "INTERVENTION_STARTED": 20, "AFTER_CAPTURED": 30, "VALIDATED": 100, "FAILED": 100, "PARTIAL": 100, "ROLLED_BACK": 100, "ROLLBACK_FAILED": 100, "RECOVERED": 110}

@dataclass(frozen=True)
class JournalAttempt:
    attempt_id: str
    execution_id: str
    character_id: str
    sequence: int
    request_hash: str
    contract_id: str
    contract_version: str
    status: str
    before_snapshot_id: str
    after_snapshot_id: str | None = None
    error: str | None = None

class TransformationJournal:
    def __init__(self, runtime_store=None):
        self.store = runtime_store or build_runtime_store()

    def record(self, attempt: JournalAttempt, event_type: str, **extra: Any) -> None:
        payload = {
            "attempt_id": attempt.attempt_id,
            "execution_id": attempt.execution_id,
            "character_id": attempt.character_id,
            "sequence": attempt.sequence,
            "request_hash": attempt.request_hash,
            "contract_id": attempt.contract_id,
            "contract_version": attempt.contract_version,
            "status": attempt.status,
            "before_snapshot_id": attempt.before_snapshot_id,
            "after_snapshot_id": attempt.after_snapshot_id,
            **extra,
        }
        event_id = content_hash({"attempt_id": attempt.attempt_id, "event_type": event_type, **payload})
        self.store.append_event(event_id, NAMESPACE, event_type, payload)

    def events(self, attempt_id: str | None = None) -> list[dict]:
        rows = self.store.list_events(NAMESPACE)
        if attempt_id is None:
            return rows
        return [row for row in rows if row["payload"].get("attempt_id") == attempt_id]

    def attempts(self) -> list[JournalAttempt]:
        grouped: dict[str, list[dict]] = {}
        for event in self.events():
            grouped.setdefault(event["payload"]["attempt_id"], []).append(event)
        result = []
        for attempt_id, events in grouped.items():
            # SQLite timestamps have one-second resolution, so event ordering
            # cannot be used as the lifecycle clock. A terminal event always
            # dominates an earlier non-terminal event.
            terminal_events = [e for e in events if e["payload"].get("status") in TERMINAL]
            candidates = terminal_events if terminal_events else events
            last_event = max(
                candidates,
                key=lambda e: (
                    STATUS_ORDER.get(e["payload"].get("status"), 0),
                    e["payload"].get("status", ""),
                    e.get("event_id", ""),
                ),
            )
            last = last_event["payload"]
            result.append(JournalAttempt(
                attempt_id=attempt_id, execution_id=last["execution_id"],
                character_id=last["character_id"], sequence=last["sequence"],
                request_hash=last["request_hash"], contract_id=last["contract_id"],
                contract_version=last["contract_version"], status=last["status"],
                before_snapshot_id=last["before_snapshot_id"],
                after_snapshot_id=last.get("after_snapshot_id"), error=last.get("error"),
            ))
        return result

class TransformationRecoveryService:
    def __init__(self, snapshots=None, ledger=None, journal=None):
        self.snapshots = snapshots or StateSnapshotStore()
        self.ledger = ledger or TransformationLedger(self.snapshots.store)
        self.journal = journal or TransformationJournal(self.snapshots.store)

    def scan(self) -> list[JournalAttempt]:
        return [a for a in self.journal.attempts() if a.status not in TERMINAL]

    def recover(self, attempt_id: str, contract) -> JournalAttempt:
        attempt = next((a for a in self.journal.attempts() if a.attempt_id == attempt_id), None)
        if attempt is None:
            raise ValueError("journal attempt not found")
        existing = self.ledger.find_by_request_hash(attempt.request_hash)
        if existing is not None:
            recovered = JournalAttempt(**{**attempt.__dict__, "status": "RECOVERED",
                                          "after_snapshot_id": existing.after_snapshot_id})
            self.journal.record(recovered, "RECOVERED", ledger_id=existing.ledger_id)
            return recovered
        after = self.snapshots.get(attempt.after_snapshot_id) if attempt.after_snapshot_id else None
        before = self.snapshots.get(attempt.before_snapshot_id)
        if after is None:
            if before is None:
                result = TransformationResult.failed(
                    "INTERVENTION_OUTCOME_UNKNOWN",
                    {"recovery_status":"OUTCOME_UNKNOWN","rerun_forbidden":True},
                    before_snapshot_id=attempt.before_snapshot_id,
                )
                execution = SimpleNamespace(
                    execution_id=attempt.execution_id,
                    before_snapshot_id=attempt.before_snapshot_id,
                    after_snapshot_id=None,
                    result=result,
                    certificate=None,
                )
                entry = TransformationLedgerEntry.from_execution(
                    execution, attempt.character_id, contract, request_hash=attempt.request_hash)
                self.ledger.append(entry)
                recovered = JournalAttempt(**{**attempt.__dict__,"status":"RECOVERED"})
                self.journal.record(
                    recovered, "RECOVERED",
                    recovered_status=result.status,
                    ledger_id=entry.ledger_id,
                    rerun_forbidden=True,
                )
                return recovered
            result = TransformationResult.failed(
                "INTERVENTION_OUTCOME_UNKNOWN",
                {"recovery_status":"OUTCOME_UNKNOWN","rerun_forbidden":True},
                before_snapshot_id=before.snapshot_id,
            )
            execution = SimpleNamespace(
                execution_id=attempt.execution_id,
                before_snapshot_id=before.snapshot_id,
                after_snapshot_id=None,
                result=result,
                certificate=None,
            )
            entry = TransformationLedgerEntry.from_execution(
                execution, attempt.character_id, contract, request_hash=attempt.request_hash)
            self.ledger.append(entry)
            recovered = JournalAttempt(**{**attempt.__dict__,"status":"RECOVERED"})
            self.journal.record(
                recovered, "RECOVERED",
                recovered_status=result.status,
                ledger_id=entry.ledger_id,
                rerun_forbidden=True,
            )
            return recovered
        if after is None or before is None:
            raise ValueError("recovery requires durable before and after snapshots")
        if not self.snapshots.verify(before.snapshot_id) or not self.snapshots.verify(after.snapshot_id):
            raise ValueError("snapshot integrity verification failed")
        diff = StateDiffEngine.compare(
            before, after, expected=contract.expected_changes,
            allowed=set(contract.allowed_changes), forbidden=set(contract.forbidden_changes))
        result = validate_transition(contract, diff,
            before_snapshot_id=before.snapshot_id, after_snapshot_id=after.snapshot_id,
            before_state=before.state, after_state=after.state)
        certificate = None
        if result.status == "VALIDATED" and result.certificate_eligible:
            certificate = TransformationCertificate.issue(attempt.execution_id, contract, result)
        execution = SimpleNamespace(execution_id=attempt.execution_id, result=result, certificate=certificate)
        entry = TransformationLedgerEntry.from_execution(
            execution, attempt.character_id, contract, request_hash=attempt.request_hash)
        self.ledger.append(entry)
        recovered = JournalAttempt(**{**attempt.__dict__, "status": "RECOVERED"})
        self.journal.record(recovered, "RECOVERED",
                            recovered_status=result.status, ledger_id=entry.ledger_id)
        return recovered
