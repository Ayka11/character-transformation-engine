"""Portable logical backup/restore for the CTE runtime store contract."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json

from .provenance import content_hash
from .persistence import MUTABLE_SNAPSHOT_NAMESPACES

BACKUP_VERSION = "1.0"


def build_backup(store) -> dict:
    snapshot_namespaces = store.list_snapshot_namespaces()
    event_namespaces = store.list_event_namespaces()
    snapshots = []
    for namespace in snapshot_namespaces:
        for item in store.list_snapshots(namespace):
            snapshots.append({
                "namespace": item.namespace,
                "key": item.key,
                "version": item.version,
                "payload": item.payload,
                "payload_hash": item.payload_hash,
            })
    events = []
    for namespace in event_namespaces:
        for event in store.list_events(namespace):
            events.append({**event, "namespace": namespace})
    snapshots.sort(key=lambda x: (x["namespace"], x["key"]))
    events.sort(key=lambda x: (x["namespace"], x["event_id"]))
    payload = {
        "backup_version": BACKUP_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "store_backend": store.__class__.__name__,
        "snapshots": snapshots,
        "events": events,
    }
    payload["manifest_hash"] = content_hash({
        "backup_version": payload["backup_version"],
        "snapshots": snapshots,
        "events": events,
    })
    return payload



def backup_to_path(store, path: str | Path) -> dict:
    """Alias with an operationally explicit name for scheduled backup jobs."""
    return save_backup(store, path)

def save_backup(store, path: str | Path) -> dict:
    backup = build_backup(store)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(backup, sort_keys=True, separators=(",", ":"), ensure_ascii=False),
        encoding="utf-8",
    )
    return {
        "path": str(target),
        "manifest_hash": backup["manifest_hash"],
        "snapshot_count": len(backup["snapshots"]),
        "event_count": len(backup["events"]),
    }


def load_backup(path: str | Path) -> dict:
    backup = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_backup(backup)
    return backup


def validate_backup(backup: dict) -> None:
    if not isinstance(backup, dict) or backup.get("backup_version") != BACKUP_VERSION:
        raise ValueError("unsupported backup version")
    snapshots = backup.get("snapshots")
    events = backup.get("events")
    manifest = backup.get("manifest_hash")
    if not isinstance(snapshots, list) or not isinstance(events, list) or not manifest:
        raise ValueError("backup manifest is incomplete")
    expected = content_hash({
        "backup_version": backup["backup_version"],
        "snapshots": snapshots,
        "events": events,
    })
    if expected != manifest:
        raise ValueError("backup manifest hash mismatch")
    for item in snapshots:
        required = {"namespace", "key", "version", "payload", "payload_hash"}
        if not required.issubset(item):
            raise ValueError("backup snapshot entry is incomplete")
        if content_hash(item["payload"]) != item["payload_hash"]:
            raise ValueError(f"snapshot payload hash mismatch: {item['namespace']}:{item['key']}")
    for item in events:
        required = {"event_id", "namespace", "event_type", "payload"}
        if not required.issubset(item):
            raise ValueError("backup event entry is incomplete")


def restore_backup(store, backup: dict, *, dry_run: bool = False) -> dict:
    validate_backup(backup)
    planned = {"snapshots": 0, "events": 0, "immutable_conflicts": [], "event_conflicts": [], "dry_run": dry_run}

    for item in backup["snapshots"]:
        existing = store.get_snapshot(item["namespace"], item["key"])
        if existing is None:
            continue
        if existing.payload_hash != item["payload_hash"] and item["namespace"] not in MUTABLE_SNAPSHOT_NAMESPACES:
            planned["immutable_conflicts"].append(f"{item['namespace']}:{item['key']}")

    for item in backup["events"]:
        existing = store.get_event(item["event_id"])
        if existing is None:
            continue
        same = (
            existing.get("namespace") == item["namespace"]
            and existing.get("event_type") == item["event_type"]
            and existing.get("payload") == item["payload"]
            and existing.get("input_hash") == item.get("input_hash")
            and existing.get("output_hash") == item.get("output_hash")
        )
        if not same:
            planned["event_conflicts"].append(item["event_id"])

    if planned["immutable_conflicts"] or planned["event_conflicts"]:
        raise ValueError(
            "restore preflight conflict: "
            + ",".join(planned["immutable_conflicts"] + planned["event_conflicts"])
        )

    if dry_run:
        planned["snapshots"] = len(backup["snapshots"])
        planned["events"] = len(backup["events"])
        return planned

    for item in backup["snapshots"]:
        store.put_snapshot(item["namespace"], item["key"], item["payload"], item["version"])
        planned["snapshots"] += 1

    for item in backup["events"]:
        store.append_event(
            item["event_id"],
            item["namespace"],
            item["event_type"],
            item["payload"],
            item.get("input_hash"),
            item.get("output_hash"),
            item.get("provenance_record_id"),
        )
        planned["events"] += 1

    return planned
