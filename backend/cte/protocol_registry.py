"""Versioned, append-only protocol registry service.

Lifecycle events are immutable and definitions are immutable snapshots. This module
provides governance primitives; it does not provide authentication or authorization.
Callers must enforce an authenticated actor and role policy before mutations.
"""
from __future__ import annotations

from typing import Any, Mapping
from .persistence import content_hash
from .protocol_selection import _validate_protocol

NAMESPACE = "protocol.registry.definition"
EVENT_NAMESPACE = "protocol.registry.lifecycle"
LIFECYCLE = frozenset({"DRAFT", "ACTIVE", "SUSPENDED", "RETIRED"})
_ALLOWED = {
    "DRAFT": frozenset({"ACTIVE", "RETIRED"}),
    "ACTIVE": frozenset({"SUSPENDED", "RETIRED"}),
    "SUSPENDED": frozenset({"ACTIVE", "RETIRED"}),
    "RETIRED": frozenset(),
}


def _event_id(protocol_id: str, version: str, status: str, actor_id: str, reason: str) -> str:
    return "protocol-lifecycle-" + content_hash({
        "protocol_id": protocol_id, "version": version, "status": status,
        "actor_id": actor_id, "reason": reason,
    })


class ProtocolRegistry:
    """Persistent registry with immutable versioned definitions and lifecycle history."""

    def __init__(self, store: Any):
        self.store = store

    def register(self, definition: Mapping[str, Any], *, actor_id: str) -> dict[str, Any]:
        if not isinstance(actor_id, str) or not actor_id.strip():
            raise ValueError("actor_id is required")
        protocol = _validate_protocol(definition)
        protocol["status"] = "DRAFT"
        protocol_id, version = protocol["protocol_id"], protocol["version"]
        key = f"{protocol_id}@{version}"
        snapshot = self.store.put_snapshot(NAMESPACE, key, protocol, version)
        event = self._append_lifecycle(protocol_id, version, "DRAFT", actor_id.strip(), "registered")
        return {"protocol": snapshot.payload, "definition_hash": snapshot.payload_hash,
                "lifecycle": "DRAFT", "lifecycle_event": event}

    def transition(self, protocol_id: str, version: str, *, target_status: str,
                   actor_id: str, reason: str) -> dict[str, Any]:
        if not all(isinstance(x, str) and x.strip() for x in (protocol_id, version, actor_id, reason)):
            raise ValueError("protocol_id, version, actor_id and reason are required")
        if target_status not in LIFECYCLE:
            raise ValueError("unsupported lifecycle status")
        key = f"{protocol_id}@{version}"
        snapshot = self.store.get_snapshot(NAMESPACE, key)
        if snapshot is None:
            raise KeyError(f"unknown protocol version: {key}")
        current = self._current_status(protocol_id, version)
        if target_status not in _ALLOWED[current]:
            raise ValueError(f"invalid lifecycle transition: {current} -> {target_status}")
        event = self._append_lifecycle(protocol_id, version, target_status, actor_id.strip(), reason.strip())
        return {"protocol_id": protocol_id, "version": version, "definition_hash": snapshot.payload_hash,
                "previous_status": current, "lifecycle": target_status, "lifecycle_event": event}

    def get(self, protocol_id: str, version: str) -> dict[str, Any] | None:
        snapshot = self.store.get_snapshot(NAMESPACE, f"{protocol_id}@{version}")
        if snapshot is None:
            return None
        return {"protocol": snapshot.payload, "definition_hash": snapshot.payload_hash,
                "lifecycle": self._current_status(protocol_id, version)}

    def list_versions(self, protocol_id: str | None = None) -> list[dict[str, Any]]:
        result = []
        for snapshot in self.store.list_snapshots(NAMESPACE):
            definition = snapshot.payload
            if protocol_id is not None and definition["protocol_id"] != protocol_id:
                continue
            result.append({"protocol": definition, "definition_hash": snapshot.payload_hash,
                           "lifecycle": self._current_status(definition["protocol_id"], definition["version"])})
        return result

    def history(self, protocol_id: str, version: str) -> list[dict[str, Any]]:
        return [event for event in self.store.list_events(EVENT_NAMESPACE)
                if event["payload"].get("protocol_id") == protocol_id
                and event["payload"].get("version") == version]

    def _append_lifecycle(self, protocol_id: str, version: str, status: str,
                          actor_id: str, reason: str) -> dict[str, Any]:
        payload = {"protocol_id": protocol_id, "version": version, "status": status,
                   "actor_id": actor_id, "reason": reason}
        event_id = _event_id(protocol_id, version, status, actor_id, reason)
        self.store.append_event(event_id, EVENT_NAMESPACE, "PROTOCOL_LIFECYCLE_CHANGED",
                                payload, output_hash=content_hash(payload),
                                provenance_record_id=f"{protocol_id}@{version}")
        event = self.store.get_event(event_id)
        return event

    def _current_status(self, protocol_id: str, version: str) -> str:
        events = self.history(protocol_id, version)
        if not events:
            raise ValueError("protocol definition has no lifecycle event")
        return events[-1]["payload"]["status"]
