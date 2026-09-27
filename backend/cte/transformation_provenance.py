"""Validated transformation provenance binding for Research and Science Lab runs.

A research run may reference a transformation execution, but the reference is
validated only when its immutable ledger entry and all referenced artifacts
pass integrity verification.
"""
from __future__ import annotations

from .transformation_ledger import TransformationLedger
from .transformation_integrity import TransformationIntegrityVerifier
from .state_snapshot_store import StateSnapshotStore


class TransformationProvenanceBinder:
    def __init__(self, runtime_store):
        self.snapshots = StateSnapshotStore(runtime_store)
        self.ledger = TransformationLedger(runtime_store)
        self.integrity = TransformationIntegrityVerifier(self.snapshots, self.ledger)

    def bind_execution(self, execution_id: str) -> dict:
        entries = [x for x in self.ledger.list() if x.execution_id == execution_id]
        if not entries:
            return {
                "execution_id": execution_id,
                "status": "MISSING",
                "validated": False,
                "ledger_id": None,
                "certificate_id": None,
                "issues": ["TRANSFORMATION_LEDGER_ENTRY_MISSING"],
            }

        entry = entries[-1]
        finding = self.integrity.verify(entry.ledger_id)
        return {
            "execution_id": execution_id,
            "status": entry.status,
            "validated": entry.status == "VALIDATED" and finding.status == "PASS",
            "ledger_id": entry.ledger_id,
            "certificate_id": entry.certificate_id,
            "before_snapshot_id": entry.before_snapshot_id,
            "after_snapshot_id": entry.after_snapshot_id,
            "before_hash": entry.before_hash,
            "after_hash": entry.after_hash,
            "contract_id": entry.contract_id,
            "contract_version": entry.contract_version,
            "request_hash": entry.request_hash,
            "integrity_status": finding.status,
            "issues": list(finding.issues),
        }
