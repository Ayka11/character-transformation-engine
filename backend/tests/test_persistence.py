import tempfile
from pathlib import Path
from cte.persistence import SQLiteRuntimeStore

def test_snapshot_is_durable_and_immutable():
    with tempfile.TemporaryDirectory() as d:
        path=str(Path(d)/"runtime.sqlite3")
        first=SQLiteRuntimeStore(path)
        first.put_snapshot("graph","node-1",{"x":1},"1")
        second=SQLiteRuntimeStore(path)
        assert second.get_snapshot("graph","node-1").payload=={"x":1}
        try:
            second.put_snapshot("graph","node-1",{"x":2},"1")
        except ValueError as e:
            assert "immutable" in str(e)
        else:
            assert False

def test_event_append_is_durable():
    with tempfile.TemporaryDirectory() as d:
        store=SQLiteRuntimeStore(str(Path(d)/"runtime.sqlite3"))
        store.append_event("e1","orchestrator","START",{"x":1},input_hash="i")
        reopened=SQLiteRuntimeStore(store.path)
        assert reopened.list_events("orchestrator")[0]["event_id"]=="e1"


def test_event_identity_includes_immutable_metadata():
    store=SQLiteRuntimeStore(":memory:")
    store.append_event("e1","ns-a","START",{"x":1},"in","out","prov-a")
    import pytest
    with pytest.raises(ValueError, match="immutable event conflict"):
        store.append_event("e1","ns-b","START",{"x":1},"in","out","prov-a")
    with pytest.raises(ValueError, match="immutable event conflict"):
        store.append_event("e1","ns-a","STOP",{"x":1},"in","out","prov-a")
    with pytest.raises(ValueError, match="immutable event conflict"):
        store.append_event("e1","ns-a","START",{"x":1},"in","out","prov-b")


def test_concurrent_identical_snapshot_writes_are_idempotent():
    import threading
    store=SQLiteRuntimeStore(":memory:")
    barrier=threading.Barrier(2)
    errors=[]

    def writer():
        try:
            barrier.wait(timeout=5)
            store.put_snapshot("race.immutable","same",{"value":1},"1")
        except Exception as exc:
            errors.append(exc)

    threads=[threading.Thread(target=writer) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert all(not thread.is_alive() for thread in threads)
    assert errors == []
    assert store.get_snapshot("race.immutable","same").payload == {"value":1}


def test_concurrent_conflicting_snapshot_writes_report_contract_conflict():
    import threading
    store=SQLiteRuntimeStore(":memory:")
    barrier=threading.Barrier(2)
    errors=[]

    def writer(value):
        try:
            barrier.wait(timeout=5)
            store.put_snapshot("race.immutable","same",{"value":value},"1")
        except Exception as exc:
            errors.append(exc)

    threads=[threading.Thread(target=writer,args=(1,)),threading.Thread(target=writer,args=(2,))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert all(not thread.is_alive() for thread in threads)
    assert len(errors) == 1
    assert isinstance(errors[0], ValueError)
    assert str(errors[0]) == "immutable snapshot conflict"


def test_immutable_snapshot_version_conflict_is_rejected():
    import pytest
    store=SQLiteRuntimeStore(":memory:")
    store.put_snapshot("graph","node-version",{"x":1},"schema-v1")
    with pytest.raises(ValueError, match="immutable snapshot conflict"):
        store.put_snapshot("graph","node-version",{"x":1},"schema-v2")


def test_atomic_snapshot_replay_requires_matching_version():
    import pytest
    store=SQLiteRuntimeStore(":memory:")
    store.put_snapshot("graph","atomic-version",{"x":1},"schema-v1")
    with pytest.raises(ValueError, match="immutable snapshot conflict"):
        store.put_snapshots_atomic([("graph","atomic-version",{"x":1},"schema-v2")])


def test_mutable_snapshot_can_advance_version_without_payload_change():
    store=SQLiteRuntimeStore(":memory:")
    store.put_snapshot("report.run","report-1",{"status":"READY"},"1")
    updated=store.put_snapshot("report.run","report-1",{"status":"READY"},"2")
    assert updated.version == "2"
    assert store.get_snapshot("report.run","report-1").version == "2"

def test_temporary_database_file_is_removed_when_store_is_collected():
    import gc
    import weakref

    store = SQLiteRuntimeStore(":memory:")
    path = Path(store.path)
    store.put_snapshot("test", "temporary", {"value": 1}, "1")
    store_ref = weakref.ref(store)

    assert path.exists()
    del store
    gc.collect()

    assert store_ref() is None
    assert not path.exists()

def test_event_listing_preserves_insertion_order_within_timestamp_bursts():
    store = SQLiteRuntimeStore(":memory:")
    # Reverse lexical order deliberately: event IDs must not be used as a
    # substitute for insertion order when timestamps share the same second.
    store.append_event("z-first", "audit", "FIRST", {"position": 1})
    store.append_event("a-second", "audit", "SECOND", {"position": 2})
    events = store.list_events("audit")

    assert [event["event_id"] for event in events] == ["z-first", "a-second"]
    assert all("." in event["created_at"] for event in events)
