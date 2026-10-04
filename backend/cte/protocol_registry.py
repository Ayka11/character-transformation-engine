"""Versioned, append-only protocol registry service.

Lifecycle events are immutable and definitions are immutable snapshots. This module
provides governance primitives; it does not provide authentication or authorization.
Callers must enforce an authenticated actor and role policy before mutations.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping
from .persistence import content_hash
from .protocol_selection import _validate_protocol

NAMESPACE = "protocol.registry.definition"
EVENT_NAMESPACE = "protocol.registry.lifecycle"
REVIEW_NAMESPACE = "protocol.registry.review"
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
        # The selector validator normalizes tag arrays to sets for matching; snapshots
        # must use deterministic JSON-compatible lists.
        for field in ("required_measurements", "contraindications", "goal_tags", "context_tags"):
            protocol[field] = sorted(protocol[field])
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
        if target_status == "ACTIVE" and not self._has_approved_review(
            protocol_id, version, snapshot.payload_hash, actor_id.strip()
        ):
            raise ValueError("approved independent review required for activation")
        payload = self._lifecycle_payload(
            protocol_id, version, target_status, actor_id.strip(), reason.strip()
        )
        event_id = "protocol-lifecycle-" + content_hash(payload)
        self.store.append_event_if_latest_status(
            EVENT_NAMESPACE, protocol_id, version, current, event_id,
            "PROTOCOL_LIFECYCLE_CHANGED", payload, output_hash=content_hash(payload),
            provenance_record_id=f"{protocol_id}@{version}",
        )
        event = self.store.get_event(event_id)
        return {"protocol_id": protocol_id, "version": version, "definition_hash": snapshot.payload_hash,
                "previous_status": current, "lifecycle": target_status, "lifecycle_event": event}


    def record_review(self, protocol_id: str, version: str, *, reviewer_id: str,
                      outcome: str, reason: str) -> dict[str, Any]:
        """Append a review bound to this exact immutable definition hash.

        The caller must supply reviewer_id from a verified server-side principal.
        This method records governance evidence; it does not authenticate the caller.
        """
        if not all(isinstance(x, str) and x.strip()
                   for x in (protocol_id, version, reviewer_id, outcome, reason)):
            raise ValueError("protocol_id, version, reviewer_id, outcome and reason are required")
        normalized_outcome = outcome.strip().upper()
        if normalized_outcome not in {"APPROVED", "REJECTED"}:
            raise ValueError("review outcome must be APPROVED or REJECTED")
        snapshot = self.store.get_snapshot(NAMESPACE, f"{protocol_id}@{version}")
        if snapshot is None:
            raise KeyError(f"unknown protocol version: {protocol_id}@{version}")
        lifecycle = self.history(protocol_id, version)
        if not lifecycle:
            raise ValueError("protocol definition has no lifecycle event")
        author_id = lifecycle[0]["payload"].get("actor_id")
        if reviewer_id.strip() == author_id:
            raise ValueError("author cannot review own protocol")
        if self._current_status(protocol_id, version) not in {"DRAFT", "SUSPENDED"}:
            raise ValueError("reviews can only be recorded for DRAFT or SUSPENDED protocols")
        payload = {
            "protocol_id": protocol_id, "version": version,
            "definition_hash": snapshot.payload_hash, "author_id": author_id,
            "reviewer_id": reviewer_id.strip(), "outcome": normalized_outcome,
            "reason": reason.strip(),
            "recorded_at": datetime.now(timezone.utc).isoformat(timespec="microseconds"),
        }
        event_id = "protocol-review-" + content_hash(payload)
        self.store.append_event(
            event_id, REVIEW_NAMESPACE, "PROTOCOL_REVIEW_RECORDED", payload,
            output_hash=content_hash(payload), provenance_record_id=f"{protocol_id}@{version}",
        )
        return self.store.get_event(event_id)

    def _has_approved_review(self, protocol_id: str, version: str,
                             definition_hash: str, approver_id: str) -> bool:
        lifecycle = self.history(protocol_id, version)
        if not lifecycle:
            return False
        author_id = lifecycle[0]["payload"].get("actor_id")
        for event in self.store.list_events(REVIEW_NAMESPACE):
            payload = event.get("payload", {})
            if payload.get("protocol_id") != protocol_id or payload.get("version") != version:
                continue
            if payload.get("definition_hash") != definition_hash or payload.get("outcome") != "APPROVED":
                continue
            if payload.get("author_id") != author_id or payload.get("reviewer_id") in {author_id, approver_id}:
                continue
            if event.get("event_type") != "PROTOCOL_REVIEW_RECORDED":
                continue
            if event.get("event_id") != "protocol-review-" + content_hash(payload):
                continue
            if event.get("output_hash") != content_hash(payload):
                continue
            if event.get("provenance_record_id") != f"{protocol_id}@{version}":
                continue
            return True
        return False

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
        events = [event for event in self.store.list_events(EVENT_NAMESPACE)
                  if event["payload"].get("protocol_id") == protocol_id
                  and event["payload"].get("version") == version]
        # Order by the store's insertion timestamp, not by the payload timestamp
        # being audited. Payload timestamps may be tampered with; using them to
        # order the chain can hide or mislabel lifecycle violations.
        def event_order(event: dict) -> datetime:
            stored_at = event.get("created_at")
            if isinstance(stored_at, str):
                try:
                    return datetime.fromisoformat(stored_at)
                except ValueError:
                    pass
            payload_at = event.get("payload", {}).get("recorded_at", "")
            try:
                return datetime.fromisoformat(payload_at)
            except (TypeError, ValueError):
                return datetime.min.replace(tzinfo=timezone.utc)
        return sorted(events, key=event_order)

    def verify_integrity(self, protocol_id: str, version: str) -> dict[str, Any]:
        """Audit a version's immutable definition and append-only lifecycle chain."""
        snapshot = self.store.get_snapshot(NAMESPACE, f"{protocol_id}@{version}")
        violations: list[str] = []
        if snapshot is None:
            return {
                "protocol_id": protocol_id, "version": version, "valid": False,
                "definition_hash_valid": False, "history_valid": False,
                "event_count": 0, "current_status": None,
                "violations": ["definition_missing"],
            }

        definition_hash_valid = content_hash(snapshot.payload) == snapshot.payload_hash
        if not definition_hash_valid:
            violations.append("definition_hash_mismatch")
        if (snapshot.payload.get("protocol_id") != protocol_id
                or snapshot.payload.get("version") != version):
            violations.append("definition_identity_mismatch")

        events = self.history(protocol_id, version)
        if not events:
            violations.append("lifecycle_history_missing")
        previous_status = None
        previous_time = None
        for index, event in enumerate(events):
            payload = event.get("payload", {})
            prefix = f"event[{index}]"
            if event.get("event_type") != "PROTOCOL_LIFECYCLE_CHANGED":
                violations.append(f"{prefix}:event_type_mismatch")
            if payload.get("protocol_id") != protocol_id or payload.get("version") != version:
                violations.append(f"{prefix}:identity_mismatch")
            if event.get("output_hash") != content_hash(payload):
                violations.append(f"{prefix}:output_hash_mismatch")
            if event.get("event_id") != "protocol-lifecycle-" + content_hash(payload):
                violations.append(f"{prefix}:event_id_mismatch")
            if event.get("provenance_record_id") != f"{protocol_id}@{version}":
                violations.append(f"{prefix}:provenance_mismatch")
            if payload.get("status") not in LIFECYCLE:
                violations.append(f"{prefix}:unknown_status")
            elif index == 0:
                if payload.get("status") != "DRAFT":
                    violations.append("lifecycle_initial_status_not_draft")
            elif previous_status is not None and payload.get("status") not in _ALLOWED[previous_status]:
                violations.append(f"{prefix}:invalid_transition")
            if not isinstance(payload.get("actor_id"), str) or not payload.get("actor_id", "").strip():
                violations.append(f"{prefix}:actor_missing")
            if not isinstance(payload.get("reason"), str) or not payload.get("reason", "").strip():
                violations.append(f"{prefix}:reason_missing")
            timestamp = payload.get("recorded_at")
            if not isinstance(timestamp, str) or not timestamp:
                violations.append(f"{prefix}:timestamp_missing")
            elif previous_time is not None and timestamp < previous_time:
                violations.append(f"{prefix}:timestamp_order_invalid")
            previous_status = payload.get("status")
            previous_time = timestamp if isinstance(timestamp, str) else previous_time

        review_events = [
            event for event in self.store.list_events(REVIEW_NAMESPACE)
            if event.get("payload", {}).get("protocol_id") == protocol_id
            and event.get("payload", {}).get("version") == version
        ]
        valid_reviews = []
        author_id = events[0].get("payload", {}).get("actor_id") if events else None
        for index, event in enumerate(review_events):
            payload = event.get("payload", {})
            prefix = f"review[{index}]"
            review_valid = True
            if event.get("event_type") != "PROTOCOL_REVIEW_RECORDED":
                violations.append(f"{prefix}:event_type_mismatch")
                review_valid = False
            if payload.get("protocol_id") != protocol_id or payload.get("version") != version:
                violations.append(f"{prefix}:identity_mismatch")
                review_valid = False
            if payload.get("definition_hash") != snapshot.payload_hash:
                violations.append(f"{prefix}:definition_hash_mismatch")
                review_valid = False
            if payload.get("author_id") != author_id:
                violations.append(f"{prefix}:author_identity_mismatch")
                review_valid = False
            reviewer_id = payload.get("reviewer_id")
            if not isinstance(reviewer_id, str) or not reviewer_id.strip():
                violations.append(f"{prefix}:reviewer_missing")
                review_valid = False
            elif reviewer_id == author_id:
                violations.append(f"{prefix}:self_review")
                review_valid = False
            if payload.get("outcome") not in {"APPROVED", "REJECTED"}:
                violations.append(f"{prefix}:outcome_invalid")
                review_valid = False
            if not isinstance(payload.get("reason"), str) or not payload.get("reason", "").strip():
                violations.append(f"{prefix}:reason_missing")
                review_valid = False
            timestamp = payload.get("recorded_at")
            if not isinstance(timestamp, str) or not timestamp:
                violations.append(f"{prefix}:timestamp_missing")
                review_valid = False
            if event.get("output_hash") != content_hash(payload):
                violations.append(f"{prefix}:output_hash_mismatch")
                review_valid = False
            if event.get("event_id") != "protocol-review-" + content_hash(payload):
                violations.append(f"{prefix}:event_id_mismatch")
                review_valid = False
            if event.get("provenance_record_id") != f"{protocol_id}@{version}":
                violations.append(f"{prefix}:provenance_mismatch")
                review_valid = False
            if review_valid:
                valid_reviews.append(event)

        for index, event in enumerate(events):
            payload = event.get("payload", {})
            if payload.get("status") != "ACTIVE":
                continue
            activation_time = payload.get("recorded_at")
            has_prior_approval = any(
                review.get("payload", {}).get("outcome") == "APPROVED"
                and review.get("payload", {}).get("definition_hash") == snapshot.payload_hash
                and review.get("payload", {}).get("reviewer_id") != payload.get("actor_id")
                and isinstance(review.get("payload", {}).get("recorded_at"), str)
                and isinstance(activation_time, str)
                and review["payload"]["recorded_at"] <= activation_time
                for review in valid_reviews
            )
            if not has_prior_approval:
                violations.append(f"event[{index}]:activation_without_valid_review")

        history_valid = not any(
            item != "definition_hash_mismatch" and item != "definition_identity_mismatch"
            for item in violations
        ) and bool(events)
        review_history_valid = not any(item.startswith("review[") or ":activation_without_valid_review" in item
                                        for item in violations)
        return {
            "protocol_id": protocol_id, "version": version,
            "valid": not violations, "definition_hash_valid": definition_hash_valid,
            "history_valid": history_valid, "review_history_valid": review_history_valid,
            "event_count": len(events), "review_event_count": len(review_events),
            "current_status": events[-1]["payload"].get("status") if events else None,
            "violations": violations,
        }

    def _lifecycle_payload(self, protocol_id: str, version: str, status: str,
                           actor_id: str, reason: str) -> dict[str, Any]:
        return {"protocol_id": protocol_id, "version": version, "status": status,
                "actor_id": actor_id, "reason": reason,
                "recorded_at": datetime.now(timezone.utc).isoformat(timespec="microseconds")}

    def _append_lifecycle(self, protocol_id: str, version: str, status: str,
                          actor_id: str, reason: str) -> dict[str, Any]:
        payload = self._lifecycle_payload(protocol_id, version, status, actor_id, reason)
        event_id = "protocol-lifecycle-" + content_hash(payload)
        self.store.append_event(event_id, EVENT_NAMESPACE, "PROTOCOL_LIFECYCLE_CHANGED",
                                payload, output_hash=content_hash(payload),
                                provenance_record_id=f"{protocol_id}@{version}")
        return self.store.get_event(event_id)

    def _current_status(self, protocol_id: str, version: str) -> str:
        events = self.history(protocol_id, version)
        if not events:
            raise ValueError("protocol definition has no lifecycle event")
        return events[-1]["payload"]["status"]
