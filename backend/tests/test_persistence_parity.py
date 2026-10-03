import os
import pytest
from cte.persistence import SQLiteRuntimeStore

def _contract_sequence(store):
    store.put_snapshot("parity.immutable", "s1", {"value": 1}, "1.0")
    same = store.put_snapshot("parity.immutable", "s1", {"value": 1}, "1.0")
    with pytest.raises(ValueError, match="immutable snapshot conflict"):
        store.put_snapshot("parity.immutable", "s1", {"value": 2}, "1.0")
    store.append_event("e1", "parity", "CHECK", {"ok": True}, "in", "out", "prov")
    store.append_event("e1", "parity", "CHECK", {"ok": True}, "in", "out", "prov")
    with pytest.raises(ValueError, match="immutable event conflict"):
        store.append_event("e1", "parity", "CHECK", {"ok": False}, "in", "out", "prov")
    batch = store.put_snapshots_atomic([
        ("parity.atomic", "before", {"n": 1}, "1.0"),
        ("parity.atomic", "after", {"n": 2}, "1.0"),
    ])
    return {"snapshot_hash": same.payload_hash, "event": store.get_event("e1"),
            "batch": [(x.key, x.payload_hash) for x in batch]}

def test_sqlite_runtime_contract_is_self_consistent():
    result = _contract_sequence(SQLiteRuntimeStore(":memory:"))
    assert result["event"]["payload"] == {"ok": True}
    assert [x[0] for x in result["batch"]] == ["before", "after"]

@pytest.mark.skipif(not os.getenv("CTE_DATABASE_URL"), reason="CTE_DATABASE_URL is required for live PostgreSQL parity")
def test_postgres_runtime_contract_matches_sqlite():
    from cte.postgres_persistence import PostgreSQLRuntimeStore
    sqlite_result = _contract_sequence(SQLiteRuntimeStore(":memory:"))
    store = PostgreSQLRuntimeStore(os.environ["CTE_DATABASE_URL"])
    result = _contract_sequence(store)
    assert result["snapshot_hash"] == sqlite_result["snapshot_hash"]
    assert result["event"]["payload"] == sqlite_result["event"]["payload"]
    assert result["event"]["input_hash"] == sqlite_result["event"]["input_hash"]
    assert result["event"]["output_hash"] == sqlite_result["event"]["output_hash"]
    assert result["batch"] == sqlite_result["batch"]
    with store.transaction() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM runtime_events WHERE event_id=%s", ("e1",))
            cur.execute("DELETE FROM runtime_snapshots WHERE namespace LIKE 'parity.%'")


def _atomic_rollback_contract(store):
    store.put_snapshot("parity.rollback", "existing", {"value": 1}, "1.0")
    with pytest.raises(ValueError, match="immutable snapshot conflict"):
        store.put_snapshots_atomic([
            ("parity.rollback", "new-before", {"value": 2}, "1.0"),
            ("parity.rollback", "existing", {"value": 999}, "1.0"),
        ])
    assert store.get_snapshot("parity.rollback", "new-before") is None
    assert store.get_snapshot("parity.rollback", "existing").payload == {"value": 1}


def test_sqlite_atomic_snapshot_rollback_contract():
    _atomic_rollback_contract(SQLiteRuntimeStore(":memory:"))


@pytest.mark.skipif(
    not os.getenv("CTE_DATABASE_URL"),
    reason="CTE_DATABASE_URL is required for live PostgreSQL parity",
)
def test_postgres_atomic_snapshot_rollback_matches_sqlite():
    from cte.postgres_persistence import PostgreSQLRuntimeStore

    _atomic_rollback_contract(SQLiteRuntimeStore(":memory:"))
    store = PostgreSQLRuntimeStore(os.environ["CTE_DATABASE_URL"])
    _atomic_rollback_contract(store)
    with store.transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM runtime_snapshots WHERE namespace='parity.rollback'"
            )



def _compare_and_swap_contract(store, namespace, key):
    first = store.put_snapshot_if_hash(
        namespace, key, {"value": 1}, "1.0", expected_hash=None
    )
    second = store.put_snapshot_if_hash(
        namespace, key, {"value": 2}, "1.0", expected_hash=first.payload_hash
    )
    with pytest.raises(ValueError, match="snapshot concurrent update conflict"):
        store.put_snapshot_if_hash(
            namespace, key, {"value": 3}, "1.0", expected_hash=first.payload_hash
        )
    latest = store.get_snapshot(namespace, key)
    assert latest is not None
    assert latest.payload == {"value": 2}
    assert latest.payload_hash == second.payload_hash
    return second.payload_hash


def test_sqlite_snapshot_compare_and_swap_rejects_stale_hash():
    _compare_and_swap_contract(
        SQLiteRuntimeStore(":memory:"), "parity.cas", "stale-writer"
    )


@pytest.mark.skipif(
    not os.getenv("CTE_DATABASE_URL"),
    reason="CTE_DATABASE_URL is required for live PostgreSQL parity",
)
def test_postgres_snapshot_compare_and_swap_matches_sqlite():
    from cte.postgres_persistence import PostgreSQLRuntimeStore

    namespace = "parity.cas"
    key = f"stale-writer-{os.urandom(6).hex()}"
    sqlite_hash = _compare_and_swap_contract(
        SQLiteRuntimeStore(":memory:"), namespace, "sqlite-stale-writer"
    )
    store = PostgreSQLRuntimeStore(os.environ["CTE_DATABASE_URL"])
    postgres_hash = _compare_and_swap_contract(store, namespace, key)
    assert postgres_hash == sqlite_hash
    with store.transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM runtime_snapshots WHERE namespace=%s AND key=%s",
                (namespace, key),
            )
