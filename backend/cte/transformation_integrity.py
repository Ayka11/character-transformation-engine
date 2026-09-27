"""Cross-check transformation ledger entries against immutable snapshots."""
from __future__ import annotations
from dataclasses import dataclass
from .transformation_ledger import TransformationLedger
from .state_snapshot_store import StateSnapshotStore

@dataclass(frozen=True)
class IntegrityFinding:
    ledger_id: str
    status: str
    issues: tuple[str, ...]

class TransformationIntegrityVerifier:
    def __init__(self, snapshots=None, ledger=None):
        self.snapshots=snapshots or StateSnapshotStore()
        self.ledger=ledger or TransformationLedger(self.snapshots.store)

    def verify(self, ledger_id: str) -> IntegrityFinding:
        entry=self.ledger.get(ledger_id)
        if entry is None:
            return IntegrityFinding(ledger_id,"MISSING_LEDGER",("ledger entry not found",))
        issues=[]
        before=self.snapshots.get(entry.before_snapshot_id)
        if before is None:
            issues.append("BEFORE_SNAPSHOT_MISSING")
        elif before.state_hash != entry.before_hash:
            issues.append("BEFORE_HASH_MISMATCH")
        if entry.after_snapshot_id:
            after=self.snapshots.get(entry.after_snapshot_id)
            if after is None:
                issues.append("AFTER_SNAPSHOT_MISSING")
            elif after.state_hash != entry.after_hash:
                issues.append("AFTER_HASH_MISMATCH")
        elif entry.status=="VALIDATED":
            issues.append("VALIDATED_WITHOUT_AFTER_SNAPSHOT")
        expected_certificate = entry.status=="VALIDATED"
        if expected_certificate and not entry.certificate_id:
            issues.append("VALIDATED_WITHOUT_CERTIFICATE")
        if not expected_certificate and entry.certificate_id:
            issues.append("FAILED_WITH_CERTIFICATE")
        return IntegrityFinding(ledger_id,"PASS" if not issues else "FAIL",tuple(issues))

    def verify_all(self):
        return [self.verify(entry.ledger_id) for entry in self.ledger.list()]
