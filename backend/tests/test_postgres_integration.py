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

    assert result.result.status == "VALIDATED"
    binding = TransformationProvenanceBinder(store).bind_execution(execution_id)
    assert binding["validated"] is True
    assert binding["integrity_status"] == "PASS"
    assert binding["ledger_id"] == ledger.list()[0].ledger_id
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
    from cte.transformation_ledger import TransformationLedgerEntry
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


@pytest.mark.skipif(
    not os.getenv("CTE_DATABASE_URL"),
    reason="CTE_DATABASE_URL is required for live PostgreSQL integration",
)
def test_postgres_retention_cannot_destroy_transformation_provenance():
    from cte.audit_retention import apply_retention, build_policy
    from cte.contracts.transformation import TransformationContract
    from cte.state_snapshot_store import StateSnapshotStore
    from cte.transformation_ledger import TransformationLedger
    from cte.transformation_provenance import TransformationProvenanceBinder
    from cte.transformation_recovery import TransformationJournal

    dsn = os.environ["CTE_DATABASE_URL"]
    store = PostgreSQLRuntimeStore(dsn)
    execution_id = f"pg-retention-{os.urandom(6).hex()}"
    character_id = f"pg-retention-character-{os.urandom(4).hex()}"

    execution = __import__("cte.transformation_runtime", fromlist=["TransformationExecutor"]).TransformationExecutor(
        StateSnapshotStore(store), TransformationLedger(store)
    ).execute(
        execution_id,
        character_id,
        1,
        {"tempo": 5},
        TransformationContract("pg-retention-contract", "1", expected_changes={"tempo": 6}),
        lambda state: {"tempo": 6},
    )
    assert execution.result.status == "VALIDATED"

    binder = TransformationProvenanceBinder(store)
    before = binder.bind_execution(execution_id)
    journal_before = [
        e for e in TransformationJournal(store).events()
        if e["payload"].get("execution_id") == execution_id
    ]
    assert before["validated"] is True
    assert journal_before

    with pytest.raises(ValueError, match="protected namespace"):
        apply_retention(
            store,
            build_policy("forbidden-transformation-journal", retention_days=1, namespace="transformation.journal"),
            archive_manifest_hash="archived",
            now=datetime.now(timezone.utc) + timedelta(days=2),
        )

    # Ordinary audit retention remains allowed and must not alter the
    # transformation snapshots/ledger/journal for this execution.
    store.append_event(
        f"pg-retention-audit-{os.urandom(4).hex()}",
        "api",
        "AUDIT",
        {"execution_id": execution_id},
    )
    audit = apply_retention(
        store,
        build_policy("api-retention", retention_days=1, namespace="api"),
        archive_manifest_hash="archived",
        now=datetime.now(timezone.utc) + timedelta(days=2),
    )
    assert audit["deleted_events"] >= 1

    after = binder.bind_execution(execution_id)
    journal_after = [
        e for e in TransformationJournal(store).events()
        if e["payload"].get("execution_id") == execution_id
    ]
    assert after["validated"] is True
    assert after["integrity_status"] == "PASS"
    assert after["ledger_id"] == before["ledger_id"]
    assert journal_after == journal_before

    cleanup = PostgreSQLRuntimeStore(dsn)
    with cleanup.transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM runtime_events WHERE namespace='transformation.journal' "
                "AND payload_json->>'execution_id'=%s",
                (execution_id,),
            )
            cur.execute(
                "DELETE FROM runtime_events WHERE namespace='api' "
                "AND payload_json->>'execution_id'=%s",
                (execution_id,),
            )
            cur.execute(
                "DELETE FROM runtime_snapshots WHERE namespace='transformation.ledger' "
                "AND key=%s",
                (before["ledger_id"],),
            )
            cur.execute(
                "DELETE FROM runtime_snapshots WHERE namespace='state.snapshot' "
                "AND payload_json->>'source_execution_id'=%s",
                (execution_id,),
            )
            cur.execute(
                "DELETE FROM runtime_snapshots WHERE namespace='transformation.lock' AND key=%s",
                (f"{character_id}:1",),
            )

@pytest.mark.skipif(
    not os.getenv("CTE_DATABASE_URL"),
    reason="CTE_DATABASE_URL is required for live PostgreSQL integration",
)
def test_postgres_matches_sqlite_transformation_provenance_contract():
    from cte.persistence import SQLiteRuntimeStore
    from cte.state_snapshot_store import StateSnapshotStore
    from cte.transformation_ledger import TransformationLedger
    from cte.transformation_provenance import TransformationProvenanceBinder
    from cte.transformation_runtime import TransformationExecutor
    from cte.contracts.transformation import TransformationContract

    pg = PostgreSQLRuntimeStore(os.environ["CTE_DATABASE_URL"])
    sqlite = SQLiteRuntimeStore(":memory:")
    suffix = os.urandom(6).hex()
    execution_id = f"parity-{suffix}"
    character_id = f"parity-character-{suffix}"
    contract = TransformationContract("parity-contract", "1", expected_changes={"tempo": 6})

    results = []
    for store in (sqlite, pg):
        execution = TransformationExecutor(
            StateSnapshotStore(store), TransformationLedger(store)
        ).execute(
            execution_id, character_id, 1, {"tempo": 5}, contract,
            lambda state: {"tempo": 6},
        )
        binding = TransformationProvenanceBinder(store).bind_execution(execution_id)
        assert execution.result.status == "VALIDATED"
        assert binding["validated"] is True
        assert binding["integrity_status"] == "PASS"
        results.append((execution, binding))

    sqlite_execution, sqlite_binding = results[0]
    pg_execution, pg_binding = results[1]
    assert pg_execution.result.status == sqlite_execution.result.status
    assert pg_execution.result.failure_code == sqlite_execution.result.failure_code
    assert pg_execution.result.before_hash == sqlite_execution.result.before_hash
    assert pg_execution.result.after_hash == sqlite_execution.result.after_hash
    assert pg_execution.result.changed_fields == sqlite_execution.result.changed_fields
    assert pg_binding["ledger_id"] == sqlite_binding["ledger_id"]
    assert pg_binding["certificate_id"] == sqlite_binding["certificate_id"]
    assert pg_binding["before_hash"] == sqlite_binding["before_hash"]
    assert pg_binding["after_hash"] == sqlite_binding["after_hash"]
    assert pg_binding["request_hash"] == sqlite_binding["request_hash"]

    for store in (sqlite, pg):
        ledger_id = TransformationProvenanceBinder(store).bind_execution(execution_id)["ledger_id"]
        ledger = TransformationLedger(store).get(ledger_id)
        assert ledger is not None
        assert ledger.ledger_id == ledger.payload_hash

    cleanup = PostgreSQLRuntimeStore(os.environ["CTE_DATABASE_URL"])
    with cleanup.transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM runtime_snapshots WHERE namespace='transformation.lock' AND key=%s",
                (f"{character_id}:1",),
            )
            cur.execute(
                "DELETE FROM runtime_snapshots WHERE namespace='transformation.ledger' "
                "AND payload_json->>'execution_id'=%s",
                (execution_id,),
            )
            cur.execute(
                "DELETE FROM runtime_snapshots WHERE namespace='transformation.certificate' "
                "AND payload_json->>'execution_id'=%s",
                (execution_id,),
            )
            cur.execute(
                "DELETE FROM runtime_snapshots WHERE namespace='state.snapshot' "
                "AND payload_json->>'source_execution_id'=%s",
                (execution_id,),
            )
            cur.execute(
                "DELETE FROM runtime_events WHERE namespace='transformation.journal' "
                "AND payload_json->>'execution_id'=%s",
                (execution_id,),
            )


@pytest.mark.skipif(
    not os.getenv("CTE_DATABASE_URL"),
    reason="CTE_DATABASE_URL is required for live PostgreSQL integration",
)
def test_postgres_science_lab_provenance_rebind_matches_sqlite_after_restore():
    from cte.persistence import SQLiteRuntimeStore
    from cte.contracts.transformation import TransformationContract
    from cte.state_snapshot_store import StateSnapshotStore
    from cte.transformation_ledger import TransformationLedger
    from cte.transformation_provenance import TransformationProvenanceBinder
    from cte.transformation_runtime import TransformationExecutor
    from cte.science_lab import ExperimentMatrix, ScenarioDefinition, ScenarioRun, ScienceLabService
    from cte.graph_registry import GraphRegistry
    from cte.provenance import Provenance, ProvenanceTag
    from cte.evidence_graph import register_node, register_edge
    import copy

    dsn = os.environ["CTE_DATABASE_URL"]
    pg = PostgreSQLRuntimeStore(dsn)
    sqlite = SQLiteRuntimeStore(":memory:")
    suffix = os.urandom(6).hex()
    execution_id = f"pg-sl-durable-{suffix}"
    matrix_id = f"matrix-{suffix}"
    scenario_id = f"scenario-{suffix}"
    run_id = f"run-{suffix}"
    result_id = f"result-{suffix}"
    claim_id = f"claim-{suffix}"

    def seed(store):
        registry = GraphRegistry.empty(store)
        execution = TransformationExecutor(
            StateSnapshotStore(store), TransformationLedger(store)
        ).execute(
            execution_id, f"character-{suffix}", 1, {"tempo": 5},
            TransformationContract("sl-parity-contract", "1", expected_changes={"tempo": 6}),
            lambda state: {"tempo": 6},
        )
        tp = TransformationProvenanceBinder(store).bind_execution(execution_id)
        matrix = ExperimentMatrix(
            matrix_id, f"study-{suffix}", "Parity", "outcome", {},
            (scenario_id,), "ACTIVE", "matrix-hash",
        )
        scenario = ScenarioDefinition(
            scenario_id, matrix_id, "Scenario", "Parity", {},
            ("outcome",), True, "scenario-hash",
        )
        service = object.__new__(ScienceLabService)
        service.registry = registry
        service.store = store
        service.research = None
        service.coordinator = None
        service.transformation_provenance = TransformationProvenanceBinder(store)
        service.matrices = {matrix_id: matrix}
        service.scenarios = {scenario_id: scenario}
        service.runs = {
            run_id: ScenarioRun(
                run_id, matrix_id, scenario_id, execution_id, "COMPLETED",
                (result_id,), {"outcome": 6.0}, "PASS", "output",
                Provenance(ProvenanceTag.EXP, "parity", "1", "input", "test"),
                tp,
            )
        }
        service.replication_assessments = {}
        service.generalization_assessments = {}
        service._put("science_lab.matrix", matrix_id, {
            **matrix.__dict__, "scenario_ids": list(matrix.scenario_ids),
        })
        service._put("science_lab.scenario", scenario_id, {
            **scenario.__dict__, "expected_outcomes": list(scenario.expected_outcomes),
        })
        service._put("science_lab.run", run_id, {
            "run_id": run_id, "matrix_id": matrix_id, "scenario_id": scenario_id,
            "execution_id": execution_id, "status": "COMPLETED",
            "result_ids": [result_id], "estimate_by_outcome": {"outcome": 6.0},
            "safety_status": "PASS", "output_hash": "output",
            "transformation_provenance": tp, "provenance_tag": "EXP",
            "source": "parity", "version": "1", "provenance_input_hash": "input",
            "provenance_note": "test",
        })
        registry.add_node(register_node(
            result_id, "RESULT", result_id, "EXP", "1",
            {"qc_status": "PASS", "validated_descriptive_result": True},
        ))
        registry.add_node(register_node(
            f"analysis-{suffix}", "ANALYSIS", f"analysis-{suffix}", "EXP", "1",
            {"execution_id": execution_id},
        ))
        registry.add_node(register_node(
            f"dataset-{suffix}", "DATASET", f"dataset-{suffix}", "EXP", "1",
            {"execution_id": execution_id, "row_count": 1, "checksum": "dataset"},
        ))
        registry.add_edge(register_edge(
            f"analysis-{suffix}:dataset", registry.nodes[f"analysis-{suffix}"],
            registry.nodes[f"dataset-{suffix}"], "ANALYZED_FROM",
        ))
        registry.add_node(register_node(
            f"transform-{suffix}", "TRANSFORMATION", execution_id, "EXP", "1",
            {"execution_id": execution_id, "ledger_id": tp["ledger_id"], "certificate_id": tp["certificate_id"]},
        ))
        registry.add_edge(register_edge(
            f"analysis-{suffix}:result", registry.nodes[f"analysis-{suffix}"],
            registry.nodes[result_id], "RESULTS_IN",
        ))
        registry.add_edge(register_edge(
            f"run-{suffix}:result", registry.nodes[f"analysis-{suffix}"],
            registry.nodes[result_id], "DERIVED_FROM",
        ))
        registry.add_edge(register_edge(
            f"run-{suffix}:transform", registry.nodes[f"analysis-{suffix}"],
            registry.nodes[f"transform-{suffix}"], "DERIVED_FROM",
        ))
        registry.register_claim(
            claim_id, result_id, "HYPOTHESIS", "REGISTERED", "EXP",
            {"execution_id": execution_id},
        )
        return service.report_bundle(matrix_id), tp

    sqlite_before, sqlite_tp = seed(sqlite)
    pg_before, pg_tp = seed(pg)

    assert pg_before["provenance"]["input_hash"] == sqlite_before["provenance"]["input_hash"]
    assert pg_tp["ledger_id"] == sqlite_tp["ledger_id"]
    assert pg_tp["certificate_id"] == sqlite_tp["certificate_id"]

    backup = build_backup(pg)
    validate_backup(backup)

    cleanup = PostgreSQLRuntimeStore(dsn)
    with cleanup.transaction() as conn:
        with conn.cursor() as cur:
            for namespace in (
                "science_lab.matrix", "science_lab.scenario", "science_lab.run",
                "graph.node", "graph.edge",
                "transformation.ledger", "transformation.certificate",
                "state.snapshot", "transformation.lock",
            ):
                cur.execute(
                    "DELETE FROM runtime_snapshots WHERE namespace=%s AND (key LIKE %s OR payload_json->>'execution_id'=%s)",
                    (namespace, f"%{suffix}%", execution_id),
                )
            cur.execute(
                "DELETE FROM runtime_events WHERE event_id LIKE %s OR payload_json->>'execution_id'=%s",
                (f"%{suffix}%", execution_id),
            )

    restore_backup(pg, copy.deepcopy(backup))
    restored_service = object.__new__(ScienceLabService)
    restored_service.registry = GraphRegistry.empty(pg)
    restored_service.store = pg
    restored_service.research = None
    restored_service.coordinator = None
    restored_service.transformation_provenance = TransformationProvenanceBinder(pg)
    restored_service.matrices = {}
    restored_service.scenarios = {}
    restored_service.runs = {}
    restored_service.replication_assessments = {}
    restored_service.generalization_assessments = {}
    restored_service._hydrate()

    pg_after = restored_service.report_bundle(matrix_id)
    restored_tp = TransformationProvenanceBinder(pg).bind_execution(execution_id)

    assert pg_after["provenance"]["input_hash"] == pg_before["provenance"]["input_hash"]
    assert pg_after["provenance"]["input_hash"] == sqlite_before["provenance"]["input_hash"]
    assert pg_after["claim_validation"] == pg_before["claim_validation"]
    assert pg_after["transformation_provenance"] == pg_before["transformation_provenance"]
    assert restored_tp["validated"] is True
    assert restored_tp["integrity_status"] == "PASS"
    assert restored_tp["ledger_id"] == pg_tp["ledger_id"]
    assert restored_tp["certificate_id"] == pg_tp["certificate_id"]

    tampered = pg.get_snapshot("science_lab.run", run_id)
    assert tampered is not None
    forged = dict(tampered.payload)
    forged["transformation_provenance"] = {
        "execution_id": execution_id,
        "validated": True,
        "integrity_status": "PASS",
        "ledger_id": "forged-ledger",
        "certificate_id": "forged-certificate",
    }
    pg.put_snapshot("science_lab.run", run_id, forged, tampered.version)
    tampered_service = object.__new__(ScienceLabService)
    tampered_service.registry = GraphRegistry.empty(pg)
    tampered_service.store = pg
    tampered_service.research = None
    tampered_service.coordinator = None
    tampered_service.transformation_provenance = TransformationProvenanceBinder(pg)
    tampered_service.matrices = {}
    tampered_service.scenarios = {}
    tampered_service.runs = {}
    tampered_service.replication_assessments = {}
    tampered_service.generalization_assessments = {}
    tampered_service._hydrate()

    tampered_report = tampered_service.report_bundle(matrix_id)
    assert tampered_report["transformation_provenance"]["runs"][0]["ledger_id"] == pg_tp["ledger_id"]
    assert tampered_report["transformation_provenance"]["runs"][0]["certificate_id"] == pg_tp["certificate_id"]
    assert tampered_report["transformation_provenance"]["runs"][0]["ledger_id"] != "forged-ledger"

    # Adversarial graph attack: durable transformation remains valid, but claim
    # validation must fail when the trusted graph lineage is destroyed.
    with cleanup.transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM runtime_snapshots WHERE namespace='graph.node' AND key=%s",
                (f"transform-{suffix}",),
            )

    attacked_service = object.__new__(ScienceLabService)
    attacked_service.registry = GraphRegistry.empty(pg)
    attacked_service.store = pg
    attacked_service.research = None
    attacked_service.coordinator = None
    attacked_service.transformation_provenance = TransformationProvenanceBinder(pg)
    attacked_service.matrices = {}
    attacked_service.scenarios = {}
    attacked_service.runs = {}
    attacked_service.replication_assessments = {}
    attacked_service.generalization_assessments = {}
    attacked_service._hydrate()

    attacked_claim = attacked_service.claim_validation(matrix_id)["claims"][0]
    assert attacked_claim["transformation_support"]["status"] == "NOT_VALIDATED"
    assert attacked_claim["transformation_support"]["graph_lineage_valid"] is False
    assert "RESULT requires TRANSFORMATION lineage" in attacked_claim["transformation_support"]["issues"]

    with cleanup.transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM runtime_events WHERE event_id LIKE %s OR payload_json->>'execution_id'=%s",
                (f"%{suffix}%", execution_id),
            )
            cur.execute(
                "DELETE FROM runtime_snapshots WHERE key LIKE %s OR payload_json->>'execution_id'=%s",
                (f"%{suffix}%", execution_id),
            )


@pytest.mark.skipif(
    not os.getenv("CTE_DATABASE_URL"),
    reason="CTE_DATABASE_URL is required for live PostgreSQL integration",
)
def test_postgres_full_durability_gate_crash_restore_and_adversarial_lineage():
    """Production gate: crash recovery + backup/restore + graph attack must compose."""
    from types import SimpleNamespace
    from cte.contracts.transformation import TransformationContract, TransformationResult
    from cte.state_snapshot_store import StateSnapshotStore
    from cte.transformation_ledger import TransformationLedger, TransformationLedgerEntry
    from cte.transformation_provenance import TransformationProvenanceBinder
    from cte.transformation_runtime import TransformationExecutor
    from cte.transformation_recovery import (
        JournalAttempt, TransformationJournal, TransformationRecoveryService,
    )
    from cte.graph_registry import GraphRegistry
    from cte.evidence_graph import register_node, register_edge
    from cte.science_lab import ExperimentMatrix, ScenarioDefinition, ScenarioRun, ScienceLabService
    from cte.provenance import Provenance, ProvenanceTag, content_hash
    import copy

    dsn = os.environ["CTE_DATABASE_URL"]
    store = PostgreSQLRuntimeStore(dsn)
    suffix = os.urandom(6).hex()
    execution_id = f"full-gate-{suffix}"
    character_id = f"full-gate-character-{suffix}"
    matrix_id = f"full-gate-matrix-{suffix}"
    scenario_id = f"full-gate-scenario-{suffix}"
    run_id = f"full-gate-run-{suffix}"
    result_id = f"full-gate-result-{suffix}"
    claim_id = f"full-gate-claim-{suffix}"

    execution = TransformationExecutor(
        StateSnapshotStore(store), TransformationLedger(store)
    ).execute(
        execution_id, character_id, 1, {"tempo": 5},
        TransformationContract("full-gate-contract", "1", expected_changes={"tempo": 6}),
        lambda state: {"tempo": 6},
    )
    assert execution.result.status == "VALIDATED"
    binder = TransformationProvenanceBinder(store)
    trusted = binder.bind_execution(execution_id)
    assert trusted["validated"] is True

    registry = GraphRegistry.empty(store)
    registry.add_node(register_node(
        result_id, "RESULT", result_id, "EXP", "1",
        {"qc_status": "PASS", "validated_descriptive_result": True},
    ))
    registry.add_node(register_node(
        f"analysis-{suffix}", "ANALYSIS", f"analysis-{suffix}", "EXP", "1",
        {"execution_id": execution_id},
    ))
    registry.add_node(register_node(
        f"transform-{suffix}", "TRANSFORMATION", execution_id, "EXP", "1",
        {"execution_id": execution_id, "ledger_id": trusted["ledger_id"],
         "certificate_id": trusted["certificate_id"]},
    ))
    registry.add_edge(register_edge(
        f"analysis-result-{suffix}", registry.nodes[f"analysis-{suffix}"],
        registry.nodes[result_id], "RESULTS_IN",
    ))
    registry.add_edge(register_edge(
        f"run-result-{suffix}", registry.nodes[f"analysis-{suffix}"],
        registry.nodes[result_id], "DERIVED_FROM",
    ))
    registry.add_edge(register_edge(
        f"run-transform-{suffix}", registry.nodes[f"analysis-{suffix}"],
        registry.nodes[f"transform-{suffix}"], "DERIVED_FROM",
    ))
    registry.register_claim(
        claim_id, result_id, "HYPOTHESIS", "REGISTERED", "EXP",
        {"execution_id": execution_id},
    )

    matrix = ExperimentMatrix(
        matrix_id, f"study-{suffix}", "Full durability gate", "outcome", {},
        (scenario_id,), "ACTIVE", "matrix-hash",
    )
    scenario = ScenarioDefinition(
        scenario_id, matrix_id, "Full durability scenario", "Gate", {},
        ("outcome",), True, "scenario-hash",
    )
    service = object.__new__(ScienceLabService)
    service.registry = registry
    service.store = store
    service.research = None
    service.coordinator = None
    service.transformation_provenance = binder
    service.matrices = {matrix_id: matrix}
    service.scenarios = {scenario_id: scenario}
    service.runs = {
        run_id: ScenarioRun(
            run_id, matrix_id, scenario_id, execution_id, "COMPLETED",
            (result_id,), {"outcome": 6.0}, "PASS", "output",
            Provenance(ProvenanceTag.EXP, "full-gate", "1", "input", "test"),
            trusted,
        )
    }
    service.replication_assessments = {}
    service.generalization_assessments = {}
    service._put("science_lab.matrix", matrix_id, {
        **matrix.__dict__, "scenario_ids": list(matrix.scenario_ids),
    })
    service._put("science_lab.scenario", scenario_id, {
        **scenario.__dict__, "expected_outcomes": list(scenario.expected_outcomes),
    })
    service._put("science_lab.run", run_id, {
        **service.runs[run_id].__dict__, "transformation_provenance": trusted,
        "provenance_tag": "EXP", "source": "full-gate", "version": "1",
        "provenance_input_hash": "input", "provenance_note": "test",
    })
    before = service.report_bundle(matrix_id)
    assert before["claim_validation"]["claims"][0]["transformation_support"]["status"] == "VALIDATED"

    # Simulate the crash window independently: ledger is durable, terminal journal is absent.
    recovery_execution = f"{execution_id}-recovery"
    recovery_attempt = f"{execution_id}-attempt"
    req_hash = content_hash({"execution_id": recovery_execution, "state": {"tempo": 5}})
    snapshots = StateSnapshotStore(store)
    journal = TransformationJournal(store)
    recovery_ledger = TransformationLedger(store)
    from cte.contracts.state import StateSnapshot
    rb = StateSnapshot.capture(f"{recovery_execution}:before", character_id, 10, {"tempo": 5},
                               source_execution_id=recovery_execution)
    ra = StateSnapshot.capture(f"{recovery_execution}:after", character_id, 11, {"tempo": 6},
                               parent_snapshot_id=rb.snapshot_id, source_execution_id=recovery_execution)
    snapshots.save_pair_atomic(rb, ra)
    journal.record(JournalAttempt(
        recovery_attempt, recovery_execution, character_id, 10, req_hash,
        "full-gate-contract", "1", "AFTER_CAPTURED", rb.snapshot_id, ra.snapshot_id,
    ), "AFTER_CAPTURED", after_hash=ra.state_hash)
    recovery_result = TransformationResult(
        "VALIDATED", None, rb.snapshot_id, ra.snapshot_id, rb.state_hash, ra.state_hash,
        ("tempo",), False, {},
    )
    recovery_contract = TransformationContract("full-gate-contract", "1", expected_changes={"tempo": 6})
    recovery_ledger.append(TransformationLedgerEntry.from_execution(
        SimpleNamespace(execution_id=recovery_execution, result=recovery_result, certificate=None),
        character_id, recovery_contract, request_hash=req_hash,
    ))
    recovered = TransformationRecoveryService(
        snapshots, recovery_ledger, journal
    ).recover(recovery_attempt, recovery_contract)
    assert recovered.status == "RECOVERED"

    # Backup and restore the complete durable state.
    backup = build_backup(store)
    validate_backup(backup)
    cleanup = PostgreSQLRuntimeStore(dsn)
    with cleanup.transaction() as conn:
        with conn.cursor() as cur:
            for namespace in (
                "science_lab.matrix", "science_lab.scenario", "science_lab.run",
                "graph.node", "graph.edge", "graph.contradiction", "graph.inference",
                "transformation.ledger", "transformation.certificate",
                "state.snapshot", "transformation.lock",
            ):
                cur.execute(
                    "DELETE FROM runtime_snapshots WHERE namespace=%s AND (key LIKE %s OR payload_json->>'execution_id' IN (%s,%s))",
                    (namespace, f"%{suffix}%", execution_id, recovery_execution),
                )
            cur.execute(
                "DELETE FROM runtime_events WHERE payload_json->>'execution_id' IN (%s,%s)",
                (execution_id, recovery_execution),
            )

    restore_backup(store, copy.deepcopy(backup))
    restored = object.__new__(ScienceLabService)
    restored.registry = GraphRegistry.empty(store)
    restored.store = store
    restored.research = None
    restored.coordinator = None
    restored.transformation_provenance = TransformationProvenanceBinder(store)
    restored.matrices = {}
    restored.scenarios = {}
    restored.runs = {}
    restored.replication_assessments = {}
    restored.generalization_assessments = {}
    restored._hydrate()

    after = restored.report_bundle(matrix_id)
    assert after["provenance"]["input_hash"] == before["provenance"]["input_hash"]
    assert after["claim_validation"] == before["claim_validation"]
    assert TransformationProvenanceBinder(store).bind_execution(execution_id)["validated"] is True

    # Final adversarial mutation: remove the trusted transformation graph node.
    with cleanup.transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM runtime_snapshots WHERE namespace='graph.node' AND key=%s",
                (f"transform-{suffix}",),
            )

    attacked = object.__new__(ScienceLabService)
    attacked.registry = GraphRegistry.empty(store)
    attacked.store = store
    attacked.research = None
    attacked.coordinator = None
    attacked.transformation_provenance = TransformationProvenanceBinder(store)
    attacked.matrices = {}
    attacked.scenarios = {}
    attacked.runs = {}
    attacked.replication_assessments = {}
    attacked.generalization_assessments = {}
    attacked._hydrate()
    claim = attacked.claim_validation(matrix_id)["claims"][0]
    assert claim["transformation_support"]["status"] == "NOT_VALIDATED"
    assert claim["transformation_support"]["graph_lineage_valid"] is False

    with cleanup.transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM runtime_events WHERE event_id LIKE %s OR payload_json->>'execution_id' IN (%s,%s)",
                (f"%{suffix}%", execution_id, recovery_execution),
            )
            cur.execute(
                "DELETE FROM runtime_snapshots WHERE key LIKE %s OR payload_json->>'execution_id' IN (%s,%s)",
                (f"%{suffix}%", execution_id, recovery_execution),
            )
