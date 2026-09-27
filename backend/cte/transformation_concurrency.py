"""Optimistic lineage guard for concurrent transformation attempts."""
from __future__ import annotations
from dataclasses import dataclass
from .contracts.errors import CTEError, CTEErrorCode
from .persistence import build_runtime_store

NAMESPACE = "transformation.lock"
SNAPSHOT_NAMESPACE = "state.snapshot"

@dataclass(frozen=True)
class TransformationLock:
    character_id: str
    sequence: int
    parent_snapshot_id: str | None
    request_hash: str

class TransformationConcurrencyGuard:
    def __init__(self, runtime_store=None):
        self.store = runtime_store or build_runtime_store()

    def _validate_parent(self, character_id, sequence, parent_snapshot_id):
        if parent_snapshot_id is None:
            if sequence > 1:
                raise CTEError(
                    CTEErrorCode.VERSION_CONFLICT,
                    "non-initial transformation requires a parent snapshot",
                    {"character_id":character_id,"sequence":sequence},
                )
            return
        parent=self.store.get_snapshot(SNAPSHOT_NAMESPACE,parent_snapshot_id)
        if parent is None:
            raise CTEError(
                CTEErrorCode.VERSION_CONFLICT,
                "parent snapshot does not exist",
                {"character_id":character_id,"sequence":sequence,
                 "parent_snapshot_id":parent_snapshot_id},
            )
        payload=parent.payload
        if payload.get("character_id") != character_id:
            raise CTEError(
                CTEErrorCode.VERSION_CONFLICT,
                "parent snapshot belongs to another character",
                {"character_id":character_id,"parent_snapshot_id":parent_snapshot_id,
                 "parent_character_id":payload.get("character_id")},
            )

    def acquire(self, character_id: str, sequence: int,
                parent_snapshot_id: str | None, request_hash: str) -> TransformationLock:
        self._validate_parent(character_id,sequence,parent_snapshot_id)
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
