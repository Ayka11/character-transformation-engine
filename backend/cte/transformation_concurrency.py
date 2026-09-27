"""Optimistic lineage guard for concurrent transformation attempts."""
from __future__ import annotations
from dataclasses import dataclass
from .contracts.errors import CTEError, CTEErrorCode
from .persistence import build_runtime_store

NAMESPACE = "transformation.lock"

@dataclass(frozen=True)
class TransformationLock:
    character_id: str
    sequence: int
    parent_snapshot_id: str | None
    request_hash: str

class TransformationConcurrencyGuard:
    def __init__(self, runtime_store=None):
        self.store = runtime_store or build_runtime_store()

    def acquire(self, character_id: str, sequence: int,
                parent_snapshot_id: str | None, request_hash: str) -> TransformationLock:
        key=f"{character_id}:{sequence}"
        payload={
            "character_id":character_id,
            "sequence":sequence,
            "parent_snapshot_id":parent_snapshot_id,
            "request_hash":request_hash,
        }
        try:
            self.store.put_snapshot(NAMESPACE, key, payload, "1.0")
        except ValueError as exc:
            existing=self.store.get_snapshot(NAMESPACE,key)
            if existing and existing.payload.get("request_hash") == request_hash:
                return TransformationLock(character_id,sequence,parent_snapshot_id,request_hash)
            raise CTEError(
                CTEErrorCode.VERSION_CONFLICT,
                "transformation sequence already claimed",
                {"character_id":character_id,"sequence":sequence,
                 "existing_request_hash":existing.payload.get("request_hash") if existing else None,
                 "requested_request_hash":request_hash},
            ) from exc
        return TransformationLock(character_id,sequence,parent_snapshot_id,request_hash)

    def get(self, character_id: str, sequence: int) -> TransformationLock | None:
        row=self.store.get_snapshot(NAMESPACE,f"{character_id}:{sequence}")
        if row is None:
            return None
        p=row.payload
        return TransformationLock(p["character_id"],p["sequence"],
                                  p.get("parent_snapshot_id"),p["request_hash"])
