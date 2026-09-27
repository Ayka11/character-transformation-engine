"""Immutable ledger for transformation attempts and their validation outcomes."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .persistence import build_runtime_store
from .provenance import content_hash

NAMESPACE = "transformation.ledger"

@dataclass(frozen=True)
class TransformationLedgerEntry:
    ledger_id: str
    execution_id: str
    character_id: str
    contract_id: str
    contract_version: str
    status: str
    failure_code: str | None
    before_snapshot_id: str
    after_snapshot_id: str | None
    before_hash: str
    after_hash: str
    certificate_id: str | None
    payload_hash: str

    @classmethod
    def from_execution(cls, execution, character_id, contract):
        result=execution.result
        certificate_id=execution.certificate.certificate_id if execution.certificate else None
        payload={
            "execution_id":execution.execution_id,
            "character_id":character_id,
            "contract_id":contract.contract_id,
            "contract_version":contract.version,
            "status":result.status,
            "failure_code":result.failure_code,
            "before_snapshot_id":result.before_snapshot_id,
            "after_snapshot_id":result.after_snapshot_id,
            "before_hash":result.before_hash,
            "after_hash":result.after_hash,
            "certificate_id":certificate_id,
        }
        payload_hash=content_hash(payload)
        return cls(content_hash(payload), execution.execution_id, character_id,
                   contract.contract_id, contract.version, result.status,
                   result.failure_code, result.before_snapshot_id,
                   result.after_snapshot_id, result.before_hash, result.after_hash,
                   certificate_id, payload_hash)

class TransformationLedger:
    def __init__(self, runtime_store=None):
        self.store=runtime_store or build_runtime_store()

    @staticmethod
    def _payload(entry):
        return {
            "ledger_id":entry.ledger_id,
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
            "payload_hash":entry.payload_hash,
        }

    def append(self, entry):
        return self.store.put_snapshot(NAMESPACE, entry.ledger_id, self._payload(entry), "1.0")

    def get(self, ledger_id):
        row=self.store.get_snapshot(NAMESPACE, ledger_id)
        return TransformationLedger._from_payload(row.payload) if row else None

    def list(self):
        return [TransformationLedger._from_payload(x.payload) for x in self.store.list_snapshots(NAMESPACE)]

    @staticmethod
    def _from_payload(payload):
        return TransformationLedgerEntry(**payload)
