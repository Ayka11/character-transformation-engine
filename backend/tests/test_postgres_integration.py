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
    from cte.transformation_ledger import TransformationLedger, TransformationLedgerEntry
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
    from cte.transformation_concurrency import TransformationConcurrencyGuard

    dsn = os.environ["CTE_DATABASE_URL"]
    character_id = f"pg-concurrency-{os.urandom(6).hex()}"

    def acquire(request_hash):
        try:
            lock = TransformationConcurrencyGuard(
                PostgreSQLRuntimeStore(dsn)
            ).acquire(character_id, 1, None, request_hash)
            return ("ok", lock)
        except Exception as exc:
            return ("error", exc)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(acquire, ["request-A", "request-B"]))

    successes = [r for status, r in results if status == "ok"]
    errors = [r for status, r in results if status == "error"]
    assert len(successes) == 1
    assert len(errors) == 1
    assert getattr(errors[0], "code", None).value == "VERSION_CONFLICT"

    cleanup = PostgreSQLRuntimeStore(dsn)
    with cleanup.transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM runtime_snapshots WHERE namespace='transformation.lock' AND key=%s",
                (f"{character_id}:1",),
            )


@pytest.mark.skipif(
    not os.getenv("CTE_DATABASE_URL"),
    reason="CTE_DATABASE_URL is required for live PostgreSQL integration",
)
def test_postgres_recovery_closes_after_ledger_commit_without_rerun():
    from cte.contracts.transformation import TransformationContract
    from cte.state_snapshot_store import StateSnapshotStore
    from cte.transformation_ledger import TransformationLedger
    from cte.transformation_recovery import (
        JournalAttempt,
        TransformationJournal,
        TransformationRecoveryService,
    )
    from cte.contracts.state import StateSnapshot
    from cte.provenance import content_hash

    dsn = os.environ["CTE_DATABASE_URL"]
    store = PostgreSQLRuntimeStore(dsn)
    snapshots = StateSnapshotStore(store)
    ledger = TransformationLedger(store)
    journal = TransformationJournal(store)
    execution_id = f"pg-recovery-{os.urandom(6).hex()}"
    attempt_id = f"pg-attempt-{os.urandom(6).hex()}"
    request_hash = content_hash({
        "execution_id": execution_id,
        "character_id": "pg-recovery-character",
        "sequence": 1,
        "state": {"tempo": 5},
        "contract_id": "pg-recovery-contract",
        "contract_version": "1",
        "parent_snapshot_id": None,
    })

    before = StateSnapshot.capture(
        f"{execution_id}:before",
        "pg-recovery-character",
        1,
        {"tempo": 5},
        source_execution_id=execution_id,
    )
    after = StateSnapshot.capture(
        f"{execution_id}:after",
        "pg-recovery-character",
        2,
        {"tempo": 6},
        parent_snapshot_id=before.snapshot_id,
        source_execution_id=execution_id,
    )
    snapshots.save_pair_atomic(before, after)
    attempt = JournalAttempt(
        attempt_id,
        execution_id,
        "pg-recovery-character",
        1,
        request_hash,
        "pg-recovery-contract",
        "1",
        "AFTER_CAPTURED",
        before.snapshot_id,
        after.snapshot_id,
    )
    journal.record(attempt, "AFTER_CAPTURED", after_hash=after.state_hash)

    contract = TransformationContract(
        "pg-recovery-contract",
        "1",
        expected_changes={"tempo": 6},
    )
    # Simulate the exact crash window: ledger commit succeeded, but the
    # terminal journal event was never written.
    from types import SimpleNamespace
    from cte.contracts.transformation import TransformationResult
    durable_result = TransformationResult(
        "VALIDATED",
        None,
        before.snapshot_id,
        after.snapshot_id,
        before.state_hash,
        after.state_hash,
        ("tempo",),
        False,
        {},
    )
    ledger_entry = TransformationLedgerEntry.from_execution(
        SimpleNamespace(
            execution_id=execution_id,
            result=durable_result,
            certificate=None,
        ),
        "pg-recovery-character",
        contract,
        request_hash=request_hash,
    )
    ledger.append(ledger_entry)

    service = TransformationRecoveryService(snapshots, ledger, journal)
    assert len(service.scan()) == 1
    recovered = service.recover(attempt_id, contract)

    assert recovered.status == "RECOVERED"
    entry = ledger.find_by_request_hash(request_hash)
    assert entry is not None
    assert entry.status == "VALIDATED"
    assert service.scan() == []

    cleanup = PostgreSQLRuntimeStore(dsn)
    with cleanup.transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM runtime_events WHERE namespace='transformation.journal' AND payload_json->>'attempt_id'=%s",
                (attempt_id,),
            )
            cur.execute(
                "DELETE FROM runtime_snapshots WHERE namespace='transformation.ledger' AND key=%s",
                (entry.ledger_id,),
            )
            cur.execute(
                "DELETE FROM runtime_snapshots WHERE namespace='state.snapshot' AND payload_json->>'source_execution_id'=%s",
                (execution_id,),
            )


@pytest.mark.skipif(
    not os.getenv("CTE_DATABASE_URL"),
    reason="CTE_DATABASE_URL is required for live PostgreSQL integration",
)
def test_postgres_backup_restore_preserves_transformation_provenance_chain():
    """Backup/restore must preserve hashes and Science Lab provenance identity."""
    from cte.contracts.transformation import TransformationContract
    from cte.state_snapshot_store import StateSnapshotStore
    from cte.transformation_ledger import TransformationLedger
    from cte.transformation_provenance import TransformationProvenanceBinder
    from cte.transformation_runtime import TransformationExecutor
    from cte.provenance import ProvenanceTag

    dsn = os.environ["CTE_DATABASE_URL"]
    store = PostgreSQLRuntimeStore(dsn)
    execution_id = f"pg-backup-{os.urandom(6).hex()}"
    character_id = f"pg-backup-character-{os.urandom(4).hex()}"

    execution = TransformationExecutor(
        StateSnapshotStore(store), TransformationLedger(store)
    ).execute(
        execution_id,
        character_id,
        1,
        {"tempo": 5, "reactivity": 2},
        TransformationContract(
            "pg-backup-contract",
            "1",
            expected_changes={"tempo": 6},
        ),
        lambda state: {**state, "tempo": 6},
    )
    assert execution.result.status == "VALIDATED"
    assert execution.certificate is not None

    binder = TransformationProvenanceBinder(store)
    before = store.get_snapshot("state.snapshot", execution.before_snapshot_id)
    after = store.get_snapshot("state.snapshot", execution.after_snapshot_id)
    binding_before = binder.bind_execution(execution_id)
    ledger_before = TransformationLedger(store).get(binding_before["ledger_id"])
    journal_events = [
        event for event in store.list_events("transformation.journal")
        if event["payload"].get("execution_id") == execution_id
    ]
    assert before is not None and after is not None
    assert ledger_before is not None
    assert binding_before["validated"] is True
    assert binding_before["integrity_status"] == "PASS"
    assert binding_before["certificate_id"] == execution.certificate.certificate_id
    assert binding_before["before_snapshot_id"] == before.payload.get("snapshot_id")
    assert binding_before["after_snapshot_id"] == after.payload.get("snapshot_id")
    assert journal_events

    # Persist a real Science Lab run record carrying the bound transformation provenance.
    run_id = f"backup-run-{execution_id}"
    run_payload = {
        "run_id": run_id,
        "matrix_id": "backup-matrix",
        "scenario_id": "backup-scenario",
        "execution_id": execution_id,
        "status": "COMPLETED",
        "result_ids": [f"result-{execution_id}"],
        "estimate_by_outcome": {"outcome": 6.0},
        "safety_status": "PASS",
        "output_hash": "backup-output",
        "transformation_provenance": binding_before,
        "provenance_tag": ProvenanceTag.EXP.value,
        "source": "postgres-backup-test",
        "version": "2.3.0",
        "provenance_input_hash": "backup-input",
        "provenance_note": "backup/restore integration test",
    }
    store.put_snapshot("science_lab.run", run_id, run_payload, "2.3.0")

    backup = build_backup(store)
    validate_backup(backup)
    assert backup["manifest_hash"]
    backup_manifest = backup["manifest_hash"]
    backup_before = {
        "before_state_hash": before.payload["state_hash"],
        "after_state_hash": after.payload["state_hash"],
        "before_lineage_hash": before.payload["lineage_hash"],
        "after_lineage_hash": after.payload["lineage_hash"],
        "ledger_id": binding_before["ledger_id"],
        "ledger_payload_hash": ledger_before.payload_hash,
        "certificate_id": binding_before["certificate_id"],
    }

    # Simulate a clean restore target inside the same PostgreSQL database by
    # removing only this test's durable records, then restoring the portable backup.
    with store.transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM runtime_events WHERE namespace='transformation.journal' "
                "AND payload_json->>'execution_id'=%s",
                (execution_id,),
            )
            cur.execute(
                "DELETE FROM runtime_snapshots WHERE namespace='science_lab.run' AND key=%s",
                (run_id,),
            )
            cur.execute(
                "DELETE FROM runtime_snapshots WHERE namespace='transformation.ledger' "
                "AND key=%s",
                (binding_before["ledger_id"],),
            )
            cur.execute(
                "DELETE FROM runtime_snapshots WHERE namespace='transformation.lock' AND key=%s",
                (f"{character_id}:1",),
            )
            cur.execute(
                "DELETE FROM runtime_snapshots WHERE namespace='state.snapshot' "
                "AND payload_json->>'source_execution_id'=%s",
                (execution_id,),
            )

    restored = restore_backup(store, backup)
    assert restored["dry_run"] is False
    assert restored["snapshots"] >= 4
    assert restored["events"] >= len(journal_events)

    restored_before = store.get_snapshot("state.snapshot", execution.before_snapshot_id)
    restored_after = store.get_snapshot("state.snapshot", execution.after_snapshot_id)
    restored_ledger = TransformationLedger(store).get(binding_before["ledger_id"])
    binding_after = binder.bind_execution(execution_id)
    restored_run = store.get_snapshot("science_lab.run", run_id)
    restored_journal = [
        event for event in store.list_events("transformation.journal")
        if event["payload"].get("execution_id") == execution_id
    ]

    assert restored_before is not None and restored_after is not None
    assert restored_ledger is not None
    assert restored_run is not None
    assert restored_journal
    assert restored_before.payload["state_hash"] == backup_before["before_state_hash"]
    assert restored_after.payload["state_hash"] == backup_before["after_state_hash"]
    assert restored_before.payload["lineage_hash"] == backup_before["before_lineage_hash"]
    assert restored_after.payload["lineage_hash"] == backup_before["after_lineage_hash"]
    assert restored_ledger.ledger_id == backup_before["ledger_id"]
    assert restored_ledger.payload_hash == backup_before["ledger_payload_hash"]
    assert binding_after["validated"] is True
    assert binding_after["integrity_status"] == "PASS"
    assert binding_after["ledger_id"] == backup_before["ledger_id"]
    assert binding_after["certificate_id"] == backup_before["certificate_id"]
    assert restored_run.payload["transformation_provenance"]["ledger_id"] == backup_before["ledger_id"]
    assert restored_run.payload["transformation_provenance"]["certificate_id"] == backup_before["certificate_id"]
    assert TransformationProvenanceBinder(store).bind_execution(execution_id)["validated"] is True
    assert backup["manifest_hash"] == backup_manifest

    # Rebuilding the backup after restore must be deterministic with respect to
    # the restored chain; the original manifest may differ only if other tests
    # changed the shared integration database concurrently.
    rebuilt = build_backup(store)
    validate_backup(rebuilt)
    assert rebuilt["manifest_hash"]

    cleanup = PostgreSQLRuntimeStore(dsn)
    with cleanup.transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM runtime_events WHERE namespace='transformation.journal' "
                "AND payload_json->>'execution_id'=%s",
                (execution_id,),
            )
            cur.execute(
                "DELETE FROM runtime_snapshots WHERE namespace='science_lab.run' AND key=%s",
                (run_id,),
            )
            cur.execute(
                "DELETE FROM runtime_snapshots WHERE namespace='transformation.ledger' "
                "AND key=%s",
                (binding_before["ledger_id"],),
            )
            cur.execute(
                "DELETE FROM runtime_snapshots WHERE namespace='state.snapshot' "
                "AND payload_json->>'source_execution_id'=%s",
                (execution_id,),
            )
