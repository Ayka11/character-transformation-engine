"""Immutable durable storage boundary for canonical StateSnapshot objects."""
from __future__ import annotations
from .contracts.state import StateSnapshot
from .persistence import build_runtime_store

NAMESPACE = "state.snapshot"

class StateSnapshotStore:
    def __init__(self, runtime_store=None):
        self.store = runtime_store or build_runtime_store()

    @staticmethod
    def _payload(snapshot: StateSnapshot) -> dict:
        return {
            "snapshot_id": snapshot.snapshot_id,
            "character_id": snapshot.character_id,
            "sequence": snapshot.sequence,
            "state": snapshot.state,
            "state_hash": snapshot.state_hash,
            "lineage_hash": snapshot.lineage_hash,
            "parent_snapshot_id": snapshot.parent_snapshot_id,
            "source_execution_id": snapshot.source_execution_id,
            "schema_version": snapshot.schema_version,
            "canonicalization_version": snapshot.canonicalization_version,
        }

    def save_pair_atomic(self, before: StateSnapshot, after: StateSnapshot):
        rows=[(NAMESPACE,before.snapshot_id,self._payload(before),before.schema_version),
              (NAMESPACE,after.snapshot_id,self._payload(after),after.schema_version)]
        return self.store.put_snapshots_atomic(rows)

    def save(self, snapshot: StateSnapshot):
        # Namespace is intentionally absent from MUTABLE_SNAPSHOT_NAMESPACES.
        return self.store.put_snapshot(NAMESPACE, snapshot.snapshot_id, self._payload(snapshot), snapshot.schema_version)

    def get(self, snapshot_id: str) -> StateSnapshot | None:
        row = self.store.get_snapshot(NAMESPACE, snapshot_id)
        return self._from_payload(row.payload) if row else None

    def list(self) -> list[StateSnapshot]:
        return [self._from_payload(row.payload) for row in self.store.list_snapshots(NAMESPACE)]

    def get_lineage(self, character_id: str) -> list[StateSnapshot]:
        return sorted((s for s in self.list() if s.character_id == character_id), key=lambda s: s.sequence)

    def verify(self, snapshot_id: str) -> bool:
        snapshot = self.get(snapshot_id)
        if snapshot is None:
            return False
        reconstructed = StateSnapshot.capture(
            snapshot.snapshot_id, snapshot.character_id, snapshot.sequence, snapshot.state,
            parent_snapshot_id=snapshot.parent_snapshot_id,
            source_execution_id=snapshot.source_execution_id,
            schema_version=snapshot.schema_version,
            canonicalization_version=snapshot.canonicalization_version,
        )
        return reconstructed.state_hash == snapshot.state_hash and reconstructed.lineage_hash == snapshot.lineage_hash

    @staticmethod
    def _from_payload(payload: dict) -> StateSnapshot:
        return StateSnapshot(**payload)
