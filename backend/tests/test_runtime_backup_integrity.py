import copy

import pytest

from cte.persistence import SQLiteRuntimeStore
from cte.runtime_backup import build_backup, restore_backup, validate_backup


def test_backup_manifest_rejects_tampered_snapshot_payload():
    store = SQLiteRuntimeStore(":memory:")
    store.put_snapshot("backup.integrity", "snapshot-1", {"value": 1}, "1.0")
    backup = build_backup(store)

    tampered = copy.deepcopy(backup)
    tampered["snapshots"][0]["payload"]["value"] = 999
    with pytest.raises(ValueError, match="manifest hash mismatch"):
        validate_backup(tampered)


def test_backup_manifest_rejects_tampered_event_payload():
    store = SQLiteRuntimeStore(":memory:")
    store.append_event(
        "backup-event-1",
        "backup.integrity",
        "CHECK",
        {"value": 1},
    )
    backup = build_backup(store)

    tampered = copy.deepcopy(backup)
    tampered["events"][0]["payload"]["value"] = 999
    with pytest.raises(ValueError, match="manifest hash mismatch"):
        validate_backup(tampered)


def test_restore_preflight_rejects_immutable_snapshot_conflict():
    source = SQLiteRuntimeStore(":memory:")
    source.put_snapshot("backup.integrity", "snapshot-1", {"value": 1}, "1.0")
    backup = build_backup(source)

    target = SQLiteRuntimeStore(":memory:")
    target.put_snapshot("backup.integrity", "snapshot-1", {"value": 2}, "1.0")
    with pytest.raises(ValueError, match="restore preflight conflict"):
        restore_backup(target, backup)


def test_restore_preflight_rejects_event_conflict():
    source = SQLiteRuntimeStore(":memory:")
    source.append_event("backup-event-2", "backup.integrity", "CHECK", {"value": 1})
    backup = build_backup(source)

    target = SQLiteRuntimeStore(":memory:")
    target.append_event("backup-event-2", "backup.integrity", "CHECK", {"value": 2})
    with pytest.raises(ValueError, match="restore preflight conflict"):
        restore_backup(target, backup)
