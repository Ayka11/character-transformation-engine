from datetime import datetime, timezone, timedelta
import json

from cte.audit_retention import apply_retention, build_policy
from cte.persistence import SQLiteRuntimeStore
from cte.runtime_backup import build_backup, restore_backup, validate_backup


def test_logical_backup_roundtrip(tmp_path):
    source=SQLiteRuntimeStore(str(tmp_path/"source.sqlite3"))
    source.put_snapshot("immutable.test","one",{"value":1},"1.0")
    source.put_snapshot("research.study","study",{"status":"REGISTERED"},"1.2")
    source.append_event(
        "event-1","api","HTTP_REQUEST",{"status":200},
        input_hash="in",output_hash="out",provenance_record_id="p"
    )
    backup=build_backup(source)
    validate_backup(backup)
    assert backup["manifest_hash"]

    target=SQLiteRuntimeStore(str(tmp_path/"target.sqlite3"))
    restored=restore_backup(target,backup)
    assert restored["snapshots"]==2
    assert restored["events"]==1
    assert target.get_snapshot("immutable.test","one").payload=={"value":1}
    assert target.list_events("api")[0]["event_id"]=="event-1"


def test_backup_detects_tampering():
    backup={
        "backup_version":"1.0",
        "snapshots":[],
        "events":[],
        "manifest_hash":"wrong"
    }
    try:
        validate_backup(backup)
    except ValueError as e:
        assert "manifest hash mismatch" in str(e)
    else:
        assert False


def test_restore_is_dry_run_safe(tmp_path):
    source=SQLiteRuntimeStore(str(tmp_path/"source.sqlite3"))
    source.put_snapshot("immutable.test","one",{"value":1},"1.0")
    backup=build_backup(source)
    target=SQLiteRuntimeStore(str(tmp_path/"target.sqlite3"))
    plan=restore_backup(target,backup,dry_run=True)
    assert plan["dry_run"] is True
    assert target.get_snapshot("immutable.test","one") is None


def test_audit_retention_requires_archived_backup(tmp_path):
    store=SQLiteRuntimeStore(str(tmp_path/"runtime.sqlite3"))
    store.append_event("old","api","HTTP_REQUEST",{"status":200})
    policy=build_policy("policy-1",retention_days=1)
    try:
        apply_retention(
            store,policy,archive_manifest_hash=None,
            now=datetime.now(timezone.utc)+timedelta(days=2)
        )
    except ValueError as e:
        assert "archive backup manifest" in str(e)
    else:
        assert False


def test_audit_retention_prunes_only_selected_namespace(tmp_path):
    store=SQLiteRuntimeStore(str(tmp_path/"runtime.sqlite3"))
    store.append_event("old-api","api","HTTP_REQUEST",{"status":200})
    store.append_event("old-graph","graph","EDGE_REGISTERED",{"status":200})
    policy=build_policy("policy-1",retention_days=1)
    result=apply_retention(
        store,policy,archive_manifest_hash="archive-hash",
        now=datetime.now(timezone.utc)+timedelta(days=2)
    )
    assert result["deleted_events"]==1
    assert store.list_events("api")==[]
    assert [x["event_id"] for x in store.list_events("graph")]==["old-graph"]


def test_restore_preflight_rejects_immutable_conflict_before_writes(tmp_path):
    source=SQLiteRuntimeStore(str(tmp_path/"source.sqlite3"))
    source.put_snapshot("immutable.test","one",{"value":1},"1.0")
    source.put_snapshot("immutable.test","two",{"value":2},"1.0")
    backup=build_backup(source)

    target=SQLiteRuntimeStore(str(tmp_path/"target.sqlite3"))
    target.put_snapshot("immutable.test","one",{"value":999},"1.0")
    try:
        restore_backup(target,backup)
    except ValueError as e:
        assert "restore preflight conflict" in str(e)
    else:
        assert False
    assert target.get_snapshot("immutable.test","two") is None


def test_audit_retention_policy_is_hash_stable(tmp_path):
    store=SQLiteRuntimeStore(str(tmp_path/"runtime.sqlite3"))
    policy=build_policy("stable",retention_days=30,namespace="api")
    assert policy.immutable_hash==build_policy(
        "stable",retention_days=30,namespace="api"
    ).immutable_hash
