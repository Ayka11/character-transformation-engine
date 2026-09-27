"""Cross-check transformation ledger entries against immutable snapshots."""
from __future__ import annotations
from dataclasses import dataclass
from .transformation_ledger import TransformationLedger
from .state_snapshot_store import StateSnapshotStore
from .contracts.state import StateDiffEngine
from .provenance import content_hash

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
        certificate_payload={
            "execution_id":entry.execution_id,
            "character_id":entry.character_id,
            "contract_id":entry.contract_id,
            "contract_version":entry.contract_version,
            "status":entry.status,
            "failure_code":entry.failure_code,
            "before_snapshot_id":entry.before_snapshot_id,
            "after_snapshot_id":entry.after_snapshot_id,
            "before_hash":entry.before_hash,
            "after_hash":entry.after_hash,
            "certificate_id":entry.certificate_id,
        }
        expected_payload_hash=content_hash(certificate_payload)
        if expected_payload_hash != entry.payload_hash:
            issues.append("LEDGER_PAYLOAD_HASH_MISMATCH")
        if entry.ledger_id != entry.payload_hash:
            issues.append("LEDGER_ID_HASH_MISMATCH")
        before=self.snapshots.get(entry.before_snapshot_id)
        if before is None:
            issues.append("BEFORE_SNAPSHOT_MISSING")
        elif not self.snapshots.verify(before.snapshot_id):
            issues.append("BEFORE_SNAPSHOT_INTEGRITY_FAILED")
        elif before.state_hash != entry.before_hash:
            issues.append("BEFORE_HASH_MISMATCH")
        if entry.after_snapshot_id:
            after=self.snapshots.get(entry.after_snapshot_id)
            if after is None:
                issues.append("AFTER_SNAPSHOT_MISSING")
            elif not self.snapshots.verify(after.snapshot_id):
                issues.append("AFTER_SNAPSHOT_INTEGRITY_FAILED")
            elif after.state_hash != entry.after_hash:
                issues.append("AFTER_HASH_MISMATCH")
        elif entry.status=="VALIDATED":
            issues.append("VALIDATED_WITHOUT_AFTER_SNAPSHOT")
        expected_certificate=entry.status=="VALIDATED"
        if expected_certificate and not entry.certificate_id:
            issues.append("VALIDATED_WITHOUT_CERTIFICATE")
        if not expected_certificate and entry.certificate_id:
            issues.append("FAILED_WITH_CERTIFICATE")
        if entry.status=="VALIDATED" and entry.certificate_id and before is not None and entry.after_snapshot_id:
            after=self.snapshots.get(entry.after_snapshot_id)
            if after is not None:
                diff=StateDiffEngine.compare(before,after)
                certificate_payload={
                    "execution_id":entry.execution_id,
                    "contract_id":entry.contract_id,
                    "contract_version":entry.contract_version,
                    "before_snapshot_id":entry.before_snapshot_id,
                    "after_snapshot_id":entry.after_snapshot_id,
                    "before_hash":entry.before_hash,
                    "after_hash":entry.after_hash,
                    "changed_fields":sorted(diff.changed),
                }
                if content_hash(certificate_payload) != entry.certificate_id:
                    issues.append("CERTIFICATE_HASH_MISMATCH")
        return IntegrityFinding(ledger_id,"PASS" if not issues else "FAIL",tuple(issues))

    def verify_all(self):
        return [self.verify(entry.ledger_id) for entry in self.ledger.list()]
