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


@pytest.mark.skipif(
    not os.getenv("CTE_DATABASE_URL"),
    reason="CTE_DATABASE_URL is required for live PostgreSQL integration",
)
def test_postgres_concurrent_immutable_snapshot_and_event_writes_are_idempotent():
    from concurrent.futures import ThreadPoolExecutor

    dsn = os.environ["CTE_DATABASE_URL"]
    suffix = os.urandom(6).hex()
    snapshot_key = f"concurrent-snapshot-{suffix}"
    event_id = f"concurrent-event-{suffix}"

    def write_snapshot(payload):
        return PostgreSQLRuntimeStore(dsn).put_snapshot(
            "integration.concurrent", snapshot_key, payload, "1.0"
        )

    def write_event(payload):
        PostgreSQLRuntimeStore(dsn).append_event(
            event_id,
            "integration.concurrent",
            "CHECK",
            payload,
            input_hash="same-input",
            output_hash="same-output",
        )
        return PostgreSQLRuntimeStore(dsn).get_event(event_id)

    with ThreadPoolExecutor(max_workers=2) as pool:
        snapshot_results = list(
            pool.map(write_snapshot, [{"value": 7}, {"value": 7}])
        )
        event_results = list(
            pool.map(write_event, [{"ok": True}, {"ok": True}])
        )

    assert [r.payload for r in snapshot_results] == [{"value": 7}, {"value": 7}]
    assert all(r.payload_hash == snapshot_results[0].payload_hash for r in snapshot_results)
    assert all(r["payload"] == {"ok": True} for r in event_results)

    with pytest.raises(ValueError, match="immutable snapshot conflict"):
        PostgreSQLRuntimeStore(dsn).put_snapshot(
            "integration.concurrent", snapshot_key, {"value": 8}, "1.0"
        )

    with pytest.raises(ValueError, match="immutable event conflict"):
        PostgreSQLRuntimeStore(dsn).append_event(
            event_id,
            "integration.concurrent",
            "CHECK",
            {"ok": False},
            input_hash="same-input",
            output_hash="same-output",
        )

    cleanup = PostgreSQLRuntimeStore(dsn)
    with cleanup.transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM runtime_events WHERE event_id=%s",
                (event_id,),
            )
            cur.execute(
                "DELETE FROM runtime_snapshots WHERE namespace=%s AND key=%s",
                ("integration.concurrent", snapshot_key),
            )


@pytest.mark.skipif(
    not os.getenv("CTE_DATABASE_URL"),
    reason="CTE_DATABASE_URL is required for live PostgreSQL integration",
)
def test_postgres_transformation_executor_and_provenance_roundtrip():
    from cte.contracts.transformation import TransformationContract
    from cte.state_snapshot_store import StateSnapshotStore
    from cte.transformation_ledger import TransformationLedger
    from cte.transformation_provenance import TransformationProvenanceBinder
    from cte.transformation_runtime import TransformationExecutor

    dsn = os.environ["CTE_DATABASE_URL"]
    store = PostgreSQLRuntimeStore(dsn)
    snapshots = StateSnapshotStore(store)
    ledger = TransformationLedger(store)
    execution_id = f"pg-provenance-{os.urandom(6).hex()}"

    result = TransformationExecutor(snapshots, ledger).execute(
        execution_id,
        "pg-character",
        1,
        {"tempo": 5},
        TransformationContract("pg-contract", "1", expected_changes={"tempo": 6}),
        lambda state: {"tempo": 6},
    )

    assert result.status == "VALIDATED"
    binding = TransformationProvenanceBinder(store).bind_execution(execution_id)
    assert binding["validated"] is True
    assert binding["integrity_status"] == "PASS"
    assert binding["ledger_id"] == result.ledger_id
    assert binding["certificate_id"]

    with store.transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM runtime_snapshots WHERE namespace='state.snapshot' AND payload_json->>'source_execution_id'=%s",
                (execution_id,),
            )
            cur.execute(
                "DELETE FROM runtime_snapshots WHERE namespace='transformation.ledger' AND key=%s",
                (binding["ledger_id"],),
            )
            cur.execute(
                "DELETE FROM runtime_snapshots WHERE namespace='transformation.certificate' AND key=%s",
                (binding["certificate_id"],),
            )


@pytest.mark.skipif(
    not os.getenv("CTE_DATABASE_URL"),
    reason="CTE_DATABASE_URL is required for live PostgreSQL integration",
)
def test_postgres_concurrent_transformation_guard_rejects_competing_request():
    from concurrent.futures import ThreadPoolExecutor
    from cte.contracts.errors import CTEError, CTEErrorCode
    from cte.transformation_concurrency import TransformationConcurrencyGuard

    dsn = os.environ["CTE_DATABASE_URL"]
    character_id = f"pg-concurrency-{os.urandom(6).hex()}"

    def acquire(request_hash):
        return TransformationConcurrencyGuard(
            PostgreSQLRuntimeStore(dsn)
        ).acquire(character_id, 1, None, request_hash)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(acquire, ["request-A", "request-B"]))

    successes = [r for r in results if not isinstance(r, Exception)]
    assert len(successes) == 1

    cleanup = PostgreSQLRuntimeStore(dsn)
    with cleanup.transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM runtime_snapshots WHERE namespace='transformation.lock' AND key=%s",
                (f"{character_id}:1",),
            )
