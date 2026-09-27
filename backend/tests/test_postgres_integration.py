import os
import pytest

from cte.postgres_persistence import PostgreSQLRuntimeStore
from cte.runtime_backup import build_backup, restore_backup, validate_backup
from cte.audit_retention import apply_retention, build_policy
from datetime import datetime, timezone, timedelta


@pytest.mark.skipif(
    not os.getenv("CTE_DATABASE_URL"),
    reason="CTE_DATABASE_URL is required for live PostgreSQL integration",
)
def test_postgres_snapshot_event_roundtrip():
    store=PostgreSQLRuntimeStore(os.environ["CTE_DATABASE_URL"])
    payload={"kind":"integration","value":42}
    snapshot=store.put_snapshot("integration.immutable","case-1",payload,"1.0")
    assert snapshot.payload==payload
    restored=store.get_snapshot("integration.immutable","case-1")
    assert restored is not None
    assert restored.payload_hash==snapshot.payload_hash
    assert restored.payload==payload

    store.append_event(
        "integration:event:1",
        "integration",
        "CHECK",
        {"ok":True},
        input_hash="input-hash",
        output_hash="output-hash",
        provenance_record_id="integration-1",
    )
    events=store.list_events("integration")
    assert len(events)==1
    assert events[0]["payload"]=={"ok":True}
    assert events[0]["input_hash"]=="input-hash"

    with pytest.raises(ValueError, match="immutable snapshot conflict"):
        store.put_snapshot("integration.immutable","case-1",{"value":43},"1.0")

    store.put_snapshot(
        "science_lab.matrix","case-1",{"matrix_id":"case-1","scenario_ids":[]},"2.3"
    )
    store.put_snapshot(
        "science_lab.matrix","case-1",{"matrix_id":"case-1","scenario_ids":["s1"]},"2.3"
    )
    latest=store.get_snapshot("science_lab.matrix","case-1")
    assert latest is not None
    assert latest.payload["scenario_ids"]==["s1"]

    backup=build_backup(store)
    validate_backup(backup)
    assert backup["manifest_hash"]
    restored=restore_backup(store,backup)
    assert restored["dry_run"] is False

    policy=build_policy("pg-audit-retention",retention_days=1,namespace="integration")
    retention=apply_retention(
        store,policy,archive_manifest_hash=backup["manifest_hash"],
        now=datetime.now(timezone.utc)+timedelta(days=2)
    )
    assert retention["deleted_events"]>=1
    assert store.list_events("integration")==[]
